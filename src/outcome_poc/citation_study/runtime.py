"""Factor-aware serving, immutable closure and stage-local native isolation."""
from dataclasses import asdict, replace, dataclass
from datetime import datetime, timezone
import importlib.abc
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from ..data_runtime import DocumentStore, load_tasks
from ..generation import NativeReaderFactory, Reader, offline_network, prompt_identity, ranking_aliases
from ..schemas import GenerationRequest
from ..storage import append_jsonl, content_hash, atomic_json, read_jsonl
from .study import read, identity, publish, verify, verify_files, selected_jobs, verify_stage, STAGES
from .prompts import render_condition, registry
from .compat import (base_completion, commit, empty_result, ResourceMonitor, resource_check,
    warmup, session_accounting, reconcile_sessions, worker_identity_unknown, stage_lock,
    sandbox_profile, probe_denials, base_verify_import_origins, BaseIsolatedReaderFactory,
    ContinuousBackend, CleanupFailure, continuous_ns, boot_identity, verify_index)
FATAL={'infra_error','timeout','context_overflow'}
DENIED_MODULES=('outcome_poc.scoring','outcome_poc.data','outcome_poc.followup.scoring',
    'outcome_poc.citation_study.scoring','outcome_poc.citation_study.preparation')


class GoldImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if any(fullname==n or fullname.startswith(n+'.') for n in DENIED_MODULES):
            raise ImportError('annotation-enabled module denied during citation serving')


def install_guard(root):
    if any(n==d or n.startswith(d+'.') for n in sys.modules for d in DENIED_MODULES):
        raise RuntimeError('annotation-enabled module already imported during citation serving')
    base_verify_import_origins(root)
    sys.meta_path.insert(0,GoldImportGuard())


def denial_paths(plan,stage):
    paths=list(plan['freeze']['denied_probes'])
    if stage=='diagnosis':paths.append(plan['freeze']['comparison_denied_probe'])
    return paths


@dataclass(frozen=True)
class IsolatedReaderFactory:
    factory: object
    root: Path
    plan_hash: str
    session_start: Path | None = None
    stage: str = 'diagnosis'

    def __call__(self):
        install_guard(self.root)
        plan=read(self.root/'plan.json')
        if plan['plan_hash']!=self.plan_hash or plan['freeze']['boot_id']!=boot_identity():
            raise ValueError('worker plan/boot mismatch')
        if self.session_start is not None:
            state=read(self.session_start)
            if state['plan_hash']!=self.plan_hash or state['boot_id']!=plan['freeze']['boot_id']:
                raise ValueError('worker session plan/boot mismatch')
        if self.stage=='comparison':validate_admission(self.root,plan)
        probe_denials(denial_paths(plan,self.stage))
        return BaseIsolatedReaderFactory(self.factory,self.root,self.plan_hash,self.session_start)()


def validate_admission(root,plan,expected_sha256=None):
    """Read only privileged attestation/decision, never the denied score store."""
    root=Path(root)
    expected_sha256=expected_sha256 or os.environ.get('OUTCOME_CITATION_ADMISSION_SHA256')
    path=root/'comparison-admission.json'
    if not path.exists():raise ValueError('comparison admission missing')
    if os.environ.get('OUTCOME_CITATION_SERVING') and not expected_sha256:
        raise ValueError('comparison admission launcher hash missing')
    if expected_sha256 and identity(path)['sha256']!=expected_sha256:
        raise ValueError('comparison admission identity changed')
    att=read(path);decision=read(root/'comparison-decision.json')
    expected={'kind':'citation-comparison-admission-v1','plan_hash':plan['plan_hash'],
        'boot_id':plan['freeze']['boot_id'],'decision':'admit',
        'decision_identity':identity(root/'comparison-decision.json'),
        'diagnosis_prediction_closure':identity(root/'stages/diagnosis/closed.json'),
        'scorer_closure_identity':decision.get('diagnosis_scores')}
    if att!=expected or decision.get('decision')!='admit' or decision.get('plan_hash')!=plan['plan_hash']:
        raise ValueError('comparison admission binding/decision mismatch')
    return att


def validate_job(root,plan,job):
    if job not in read(Path(root)/'schedule.json'):raise ValueError('unassigned job')
    if (job['bindings_hash']!=plan['freeze']['bindings_hash'] or job['arm']!=job['evidence_arm'] or
        job['system_hash']!=registry()[job['prompt_condition']]['system_hash']):
        raise ValueError('job factor binding mismatch')


def completion(root,plan,job):
    validate_job(root,plan,job)
    result=base_completion(root,plan,job)
    if result and result[0]['calls'] and not result[0].get('interrupted'):
        paid=read(Path(root)/'jobs'/job['job_id']/'paid.json')
        request=paid['request'];settings=plan['freeze']['settings']['reader']
        asset=read(Path(root)/'assets.json')['assets']['reader']
        expected=asdict(GenerationRequest(asset['revision'],asset['snapshot_hash'],result[0]['prompt_hash'],
            plan['freeze']['decoding_hash'],'answer',settings['max_context_tokens'],settings['max_new_tokens'],settings['timeout_seconds'],'none'))
        if request!=expected:raise ValueError('paid generation settings binding mismatch')
    return result


def abort(root,plan,stage,reason,job=None):
    path=Path(root)/'stages'/stage/'aborted.json'
    if not path.exists():publish(path,{'plan_hash':plan['plan_hash'],'stage':stage,'reason':reason,
        'job_id':job['job_id'] if job else None,'continuous_ns':continuous_ns()})


def recover_or_refuse(root,plan,stage,jobs):
    interrupted=False
    for job in jobs:
        directory=root/'jobs'/job['job_id']
        existing=completion(root,plan,job)
        if existing:
            if existing[0]['result']['status'] in FATAL or existing[0].get('cleanup_error'):
                abort(root,plan,stage,'assigned failure preserved',job)
        elif (directory/'started.json').exists():
            # execute_job's recovery branch never touches a backend or evidence.
            task=type('InterruptedTask',(),{'task_id':job['task_id']})()
            execute_job(root,plan,job,task,None,None,None)
            abort(root,plan,stage,'interrupted assigned job',job);interrupted=True
    if (root/'stages'/stage/'aborted.json').exists():
        raise RuntimeError('stage permanently aborted'+('; interrupted job terminalized' if interrupted else ''))


def close_stage(root,plan,stage):
    root=Path(root)
    if (root/'stages'/stage/'aborted.json').exists():raise ValueError('aborted stage cannot close')
    jobs=selected_jobs(root,stage)
    if not jobs:raise ValueError('empty assigned schedule')
    files={}
    for job in jobs:
        if completion(root,plan,job) is None:raise ValueError('stage schedule incomplete')
        for p in (root/'jobs'/job['job_id']).rglob('*'):
            if p.is_file():files[str(p.relative_to(root))]=identity(p)
    all_jobs={j['job_id'] for j in read(root/'schedule.json')}
    if any(p.name not in all_jobs for p in (root/'jobs').iterdir()):raise ValueError('unassigned job directory')
    stage_dir=root/'stages'/stage
    for p in stage_dir.rglob('*'):
        if p.is_file() and p.name!='closed.json':files[str(p.relative_to(root))]=identity(p)
    for p in (root/'ranking-identities').glob('*.json'):
        if read(p)['task_id'] in {j['task_id'] for j in jobs}:files[str(p.relative_to(root))]=identity(p)
    if stage=='comparison':
        for name in ('comparison-decision.json','comparison-admission.json'):files[name]=identity(root/name)
    closure={'plan_hash':plan['plan_hash'],'stage':stage,'assigned_jobs':len(jobs),
        'assigned_unique_questions':len({j['task_id'] for j in jobs}),
        'job_ids_hash':content_hash(sorted(j['job_id'] for j in jobs)),'files':files,
        'session_accounting':session_accounting(root,stage,plan,require_closed=True)}
    publish(stage_dir/'closed.json',closure)
    return closure


def validate_closed_stage(root,stage,*,privileged=True):
    root=Path(root);marker=root/'stages'/stage/'closed.json'
    if not marker.exists():raise ValueError('stage schedule incomplete; scoring forbidden')
    plan=verify(root)
    if stage=='comparison':validate_admission(root,plan)
    closure=read(marker)
    if closure['plan_hash']!=plan['plan_hash']:raise ValueError('closure plan mismatch')
    verify_files({str(root/n):v for n,v in closure['files'].items()})
    if close_stage(root,plan,stage)!=closure:raise ValueError('closure mismatch')
    records=[(j,*completion(root,plan,j)) for j in selected_jobs(root,stage)]
    if privileged:verify(root,privileged=True)
    return plan,records


def execute_job(root, plan, job, task, documents, retrieval, backend, *, clock=continuous_ns,
                active=time.perf_counter_ns, session=None):
    """Execute once, or terminalize an interrupted attempt without semantic retry."""
    root=Path(root); directory=root/'jobs'/job['job_id']
    validate_job(root,plan,job)
    if task.task_id!=job['task_id']:raise ValueError('job/task mismatch')
    existing=completion(root,plan,job)
    if existing:return existing
    directory.mkdir(parents=True,exist_ok=True)
    state_path=directory/'started.json'
    if state_path.exists():
        state=read(state_path)
        if state['job_hash']!=content_hash(job) or state['plan_hash']!=plan['plan_hash'] or state['boot_id']!=boot_identity():
            raise ValueError('interrupted job identity/boot mismatch')
        # Preserve any payload that reached disk, but never adopt it without its receipt.
        if (directory/'terminal.json').exists():
            original=read(directory/'terminal.json')
            publish(directory/'unreceipted-payload.json',original)
            (directory/'terminal.json').unlink()
        progress=read(directory/'progress.json') if (directory/'progress.json').exists() else {}
        result=replace(empty_result('interrupted process; no semantic retry'),raw_output=progress.get('raw_output',''),
            prompt_tokens=len(progress.get('prompt_token_ids',[])),generated_tokens=len(progress.get('generated_token_ids',[])),
            prompt_token_ids=progress.get('prompt_token_ids',[]),generated_token_ids=progress.get('generated_token_ids',[]))
        return commit(root,plan,job,state,{'result':asdict(result),'calls':int((directory/'paid.json').exists()),
            'evidence_ids':[],'ranking':[],'prompt_hash':None,'interrupted':True},clock=clock,active=active)
    backend.synchronize() # resident startup/sync charged in stage setup/lifecycle, outside warm service
    state={'job_hash':content_hash(job),'plan_hash':plan['plan_hash'],'boot_id':boot_identity(),
           'start_ns':clock(),'active_start_ns':active(),'started_utc':datetime.now(timezone.utc).isoformat(),'session':session}
    publish(state_path,state)
    append_jsonl(directory/'attempts.jsonl',{'kind':'start',**state})
    calls=0; evidence=[]; ranking=[]; aliases={}; prompt_hash=None; cleanup=None; result=None; synchronization_error=None; retrieval_pending=True; retrieval_error=None
    try:
        # No ranking or answer reuse: every assigned serving call performs this query encoding.
        ranking=retrieval.rank(task.question,task.candidate_ids)
        if {r.doc_id for r in ranking}!=set(task.candidate_ids) or len(ranking)!=10:
            raise ValueError('ranking does not cover all candidates')
        publish(root/'ranking-identities'/f'{content_hash(task.task_id)}.json',{'task_id':task.task_id,
            'ranking':[asdict(r) for r in ranking]})
        retrieval_pending=False
        aliases=ranking_aliases(ranking)
        if job['arm']=='support-documents':
            support={r['task_id']:r['support_doc_ids'] for r in read_jsonl(root/'inputs'/job['stage']/'support-doc-ids.jsonl')}
            chosen=[r.doc_id for r in ranking if r.doc_id in support[task.task_id]]
        else:chosen=[r.doc_id for r in ranking[:int(job['arm'])]]
        evidence=[documents.get(i) for i in chosen]
        prompt=render_condition(task.question,evidence,aliases,backend.tokenizer,job['prompt_condition'])
        prompt_hash=prompt_identity(prompt,backend.tokenizer)
        settings=plan['freeze']['settings']['reader']; asset=read(root/'assets.json')['assets']['reader']
        request=GenerationRequest(asset['revision'],asset['snapshot_hash'],prompt_hash,
               plan['freeze']['decoding_hash'],
               'answer',settings['max_context_tokens'],settings['max_new_tokens'],settings['timeout_seconds'],'none')
        publish(directory/'paid.json',{'request':asdict(request),'prompt':prompt,
              'ranking_hash':content_hash([asdict(r) for r in ranking]),'aliases':aliases})
        def progress(text,prompt_ids,token_ids):
            atomic_json(directory/'progress.json',{'raw_output':text,'prompt_token_ids':prompt_ids,'generated_token_ids':token_ids})
        backend.progress_callback=progress
        calls=1
        try:generated=backend.generate(prompt,request,rendered=True)
        except CleanupFailure as error:
            generated=error.result;cleanup=f'{type(error.cleanup_error).__name__}: {error.cleanup_error}'
        result=Reader.parse_generated(generated,evidence,aliases)
        if cleanup is None:backend.synchronize()
    except (KeyboardInterrupt,SystemExit):
        raise # resume terminalizes the retained started attempt
    except Exception as error:
        reason=f'{type(error).__name__}: {error}'
        if retrieval_pending:retrieval_error=reason
        if result is not None:synchronization_error=reason
        result=replace(result,status='infra_error',stop_reason=reason) if result is not None else empty_result(reason)
        if calls and (directory/'progress.json').exists() and not result.generated_token_ids:
            partial=read(directory/'progress.json')
            result=replace(result,raw_output=partial['raw_output'],prompt_tokens=len(partial['prompt_token_ids']),
                generated_tokens=len(partial['generated_token_ids']),prompt_token_ids=partial['prompt_token_ids'],
                generated_token_ids=partial['generated_token_ids'])
    payload={'result':asdict(result),'calls':calls,'evidence_ids':[d.doc_id for d in evidence],
             'ranking':[asdict(r) for r in ranking],'aliases':aliases,'prompt_hash':prompt_hash,
             'cleanup_error':cleanup,'synchronization_error':synchronization_error,'retrieval_error':retrieval_error,'resources':getattr(backend,'last_resources',{})}
    committed=commit(root,plan,job,state,payload,clock=clock,active=active)
    if result.status in FATAL or cleanup or synchronization_error or retrieval_error:
        abort(root,plan,job['stage'],'assigned execution failure',job)
    if result.status in FATAL:raise RuntimeError('assigned infrastructure result; stage aborted')
    if retrieval_error:raise RuntimeError(f'retrieval failed; terminal result preserved: {retrieval_error}')
    if cleanup:raise RuntimeError(f'cleanup failed; terminal result preserved: {cleanup}')
    if synchronization_error:raise RuntimeError(f'synchronization failed; terminal result preserved: {synchronization_error}')
    return committed


def run_stage(root, stage, *, backend_factory=None, encoder_factory=None, max_jobs=None):
    """Native entry; injectable dependencies exercise exactly this transaction engine."""
    from ..retrieval import EncoderBackend, Retrieval
    root=Path(root).resolve()
    plan=verify(root,privileged=False)
    if plan['freeze']['boot_id']!=boot_identity():raise ValueError('cross-boot resumption forbidden')
    if stage=='comparison':validate_admission(root,plan)
    verify_index(root/'stages'/stage/'index-setup')
    jobs=selected_jobs(root,stage)
    # Validate every existing completion before loading a model or generating.
    for job in jobs:completion(root,plan,job)
    if (root/'stages'/stage/'closed.json').exists():
        validate_closed_stage(root,stage,privileged=False)
        return {'status':'closed','jobs':len(jobs)}
    assets=read(root/'assets.json')['assets']
    stage_dir=root/'stages'/stage;stage_dir.mkdir(parents=True,exist_ok=True)
    session=uuid.uuid4().hex
    monitor=ResourceMonitor(stage_dir/f'resources-{session}.jsonl')
    backend=None;error=None;reader_acquisition_started=False
    with stage_lock(root):
        reconcile_sessions(root,stage,plan)
        recover_or_refuse(root,plan,stage,jobs)
        setup_start=continuous_ns();active_start=time.perf_counter_ns()
        session_start=stage_dir/f'session-start-{session}.json'
        publish(session_start,{'session':session,'plan_hash':plan['plan_hash'],'boot_id':plan['freeze']['boot_id'],
            'start_ns':setup_start,'active_start_ns':active_start,'parent_pid':os.getpid(),
            'started_utc':datetime.now(timezone.utc).isoformat(),'reader_worker_expected':backend_factory is None})
        monitor.start()
        try:
            with offline_network():
                encoder_start=continuous_ns()
                encoder=(encoder_factory or EncoderBackend)(Path(assets['encoder']['local_path']))
                append_jsonl(stage_dir/'setup.jsonl',{'session':session,'kind':'encoder_load','start_ns':encoder_start,
                    'stop_ns':continuous_ns(),'status':'ok'})
                if encoder.identity != {k:assets['encoder'][k] for k in ('revision','snapshot_hash')}:
                    raise ValueError('loaded encoder identity mismatch')
                docs=DocumentStore(root/'inputs'/stage/'documents.jsonl')
                retrieval=Retrieval(root/'stages'/stage/'index-setup/index',docs,encoder)
                reader_start=continuous_ns()
                factory=IsolatedReaderFactory(NativeReaderFactory(Path(assets['reader']['local_path']),
                    {**plan['freeze']['settings']['reader'],'asset':assets['reader']}),root,plan['plan_hash'],session_start,stage)
                reader_acquisition_started=True
                backend=(backend_factory or ContinuousBackend)(factory)
                monitor.backend=backend
                append_jsonl(stage_dir/'setup.jsonl',{'session':session,'kind':'reader_load',
                    'start_ns':reader_start,'stop_ns':continuous_ns(),'active_start_ns':active_start,'status':'ok'})
                tasks={t.task_id:t for t in load_tasks(root/'inputs'/stage/'tasks.jsonl','fit_extension')}
                gate=resource_check(monitor.sample())
                append_jsonl(stage_dir/'setup.jsonl',{'session':session,'kind':'memory_gate',**gate})
                if not gate['passed']:raise RuntimeError('memory gate failed')
                warmup(root,plan,backend,stage_dir/f'warmup-{session}')
                gate=resource_check(monitor.sample())
                append_jsonl(stage_dir/'setup.jsonl',{'session':session,'kind':'post_warmup_memory_gate',**gate})
                if not gate['passed']:raise RuntimeError('post-warmup memory gate failed')
                done=0
                for job in jobs:
                    if completion(root,plan,job):continue
                    backend.job_owner=job['job_id']
                    execute_job(root,plan,job,tasks[job['task_id']],docs,retrieval,backend,session=session)
                    done+=1
                    if max_jobs is not None and done>=max_jobs:break
        except BaseException as caught:
            error=caught
            append_jsonl(stage_dir/'setup.jsonl',{'session':session,'kind':'stage_failure',
                'start_ns':setup_start,'stop_ns':continuous_ns(),'status':'failed','error':f'{type(caught).__name__}: {caught}'})
        finally:
            close_start=continuous_ns();cleanup_error=None
            if backend:
                try:backend.close()
                except BaseException as caught:
                    error=error or caught;cleanup_error=f'{type(caught).__name__}: {caught}'
                    append_jsonl(stage_dir/'setup.jsonl',{'session':session,'kind':'cleanup_error','error':cleanup_error})
                for row in backend.lifecycle:append_jsonl(stage_dir/'lifecycle.jsonl',{'session':session,**row})
            # A constructor can leave an owned worker even though assignment failed.
            if reader_acquisition_started:
                try:
                    if worker_identity_unknown(stage_dir,read(session_start),plan,require_identity=cleanup_error is not None):
                        raise RuntimeError('owned reader worker identity unknown; quiescence unverified')
                except Exception as caught:
                    error=error or caught
                    cleanup_error=cleanup_error or f'{type(caught).__name__}: {caught}'
                    append_jsonl(stage_dir/'setup.jsonl',{'session':session,'kind':'quiescence_error','error':str(caught)})
            monitor.stop()
            session_stop=continuous_ns()
            publish(stage_dir/f'session-accounting-{session}.json',{'session':session,'plan_hash':plan['plan_hash'],
                'boot_id':plan['freeze']['boot_id'],'start_identity':identity(session_start),'start_ns':setup_start,
                'stop_ns':session_stop if cleanup_error is None else None,'stop_lower_bound_ns':session_stop,
                'stop_upper_bound_ns':session_stop if cleanup_error is None else None,
                'timing_status':'exact' if cleanup_error is None else 'interrupted_stop_unknown',
                'cleanup_error':cleanup_error,'status':'failed' if error else 'ok'})
            append_jsonl(stage_dir/'setup.jsonl',{'session':session,'kind':'session_envelope',
                'start_ns':setup_start,'stop_ns':session_stop,'shutdown_start_ns':close_start,
                'status':'failed' if error else 'ok','timing_status':'parent-finalizer observation only' if cleanup_error else 'exact',
                'overlaps':'service, setup and lifecycle; never sum'})
        if error and any(read(p).get('session')==session for p in (root/'jobs').glob('*/started.json')):
            abort(root,plan,stage,'session failed after assigned work')
    verify(root,privileged=False)
    if error:raise error
    if all(completion(root,plan,j) for j in jobs):
        close_stage(root,plan,stage)
        return {'status':'closed','jobs':len(jobs)}
    return {'status':'incomplete','assigned_jobs':len(jobs)}


def launch_binding(root,stage,plan):
    """Seal one native launch profile independently of the immutable plan."""
    directory=root/'stages'/stage/('launch-'+uuid.uuid4().hex);directory.mkdir(parents=True)
    denied=list(plan['freeze']['denied_paths'])
    if stage=='diagnosis':denied+=plan['freeze']['comparison_denied_paths']
    profile=directory/'native.sb';profile.write_text(sandbox_profile(root,denied))
    publish(directory/'binding.json',{'plan_hash':plan['plan_hash'],'stage':stage,'boot_id':plan['freeze']['boot_id'],
        'profile':identity(profile),'denial_paths':denial_paths(plan,stage)})
    return directory


def native_entry(root,stage):
    root=Path(root).resolve();install_guard(root)
    plan=verify(root)
    if stage=='comparison':validate_admission(root,plan)
    directory=Path(os.environ['OUTCOME_CITATION_LAUNCH']).resolve()
    if directory.parent!=root/'stages'/stage:raise ValueError('native launch outside stage')
    binding=read(directory/'binding.json')
    if binding!={'plan_hash':plan['plan_hash'],'stage':stage,'boot_id':boot_identity(),
        'profile':identity(directory/'native.sb'),'denial_paths':denial_paths(plan,stage)}:
        raise ValueError('native launch binding mismatch')
    denied=plan['freeze']['denied_paths']+(plan['freeze']['comparison_denied_paths'] if stage=='diagnosis' else [])
    if (directory/'native.sb').read_text()!=sandbox_profile(root,denied):
        raise ValueError('native profile differs from frozen isolation policy')
    probe=probe_denials(binding['denial_paths'])
    publish(directory/'denial-probe.json',{'binding':identity(directory/'binding.json'),'profile':binding['profile'],
        'boot_id':boot_identity(),'pid':os.getpid(),**probe})
    return run_stage(root,stage)


def launch(root,stage):
    root=Path(root).resolve();plan=verify(root,privileged=True)
    if (root/'stages'/stage/'closed.json').exists():
        _,records=validate_closed_stage(root,stage)
        return {'status':'closed','stage':stage,'jobs':len(records)}
    admission=None
    if stage=='comparison':
        from .scoring import admit
        if admit(root)['decision']!='admit':raise ValueError('comparison admission deferred')
        validate_admission(root,plan);admission=identity(root/'comparison-admission.json')
    with stage_lock(root):directory=launch_binding(root,stage,plan)
    env={**os.environ,'PYTHONPATH':str(root/'source/src'),'PYTHONDONTWRITEBYTECODE':'1',
        'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false',
        'OUTCOME_CITATION_SERVING':str(root),'OUTCOME_CITATION_LAUNCH':str(directory)}
    if admission:env['OUTCOME_CITATION_ADMISSION_SHA256']=admission['sha256']
    process=subprocess.run(['/usr/bin/sandbox-exec','-f',str(directory/'native.sb'),sys.executable,'-B','-m',
        'outcome_poc.citation_study','_serve','--root',str(root),'--stage',stage],env=env,cwd=root/'source')
    verify(root,privileged=True)
    if admission:verify_files({str(root/'comparison-admission.json'):admission})
    if process.returncode:raise RuntimeError(f'native stage failed: exit {process.returncode}')
    return {'stage':stage,'status':'native process exited successfully'}


def report(root):
    root=Path(root).resolve();plan=verify(root)
    def ledger(p):return list(read_jsonl(p)) if p.exists() else []
    def elapsed(rows):return sum((r['stop_ns']-r['start_ns'])/1e9 for r in rows)
    physical={'preparation_seconds':elapsed(ledger(root/'setup.jsonl')),
        'index_setup_seconds':sum(elapsed(ledger(root/'stages'/s/'index-setup.jsonl')) for s in STAGES),
        'scoring_seconds':elapsed(ledger(root/'scoring-attempts.jsonl')),
        'serving_session_seconds':0.,'serving_session_lower_seconds':0.,'serving_session_upper_seconds':0.,
        'accounting_status':'complete','summing_rule':'Only disjoint preparation, index setup, resident sessions and scoring. Jobs, warmup, load, lifecycle and resources are nested diagnostics.'}
    decision=read(root/'comparison-decision.json') if (root/'comparison-decision.json').exists() else None
    result={'plan_hash':plan['plan_hash'],'planned_generations':1408,'old_24h_window_applies':False,'stages':{},'physical_costs':physical,'admission':decision}
    for stage in STAGES:
        # Schedule metadata is frozen and visible before admission; comparison text is not loaded.
        jobs=[j for j in read(root/'schedule.json') if j['stage']==stage];directory=root/'stages'/stage
        records=[completion(root,plan,j) for j in jobs];completed=sum(r is not None for r in records)
        status='missing' if not completed else 'incomplete'
        if (directory/'aborted.json').exists():status='aborted'
        if stage=='comparison' and ((decision and decision['decision']=='defer') or (root/'stages/diagnosis/aborted.json').exists()):status='deferred'
        summary=None
        if (directory/'closed.json').exists():
            validate_closed_stage(root,stage,privileged=False);status='closed_unscored'
            if (root/'scores'/stage/'closed.json').exists():
                from .scoring import validate_score_seal
                validate_score_seal(root,stage,plan,len(jobs));summary=read(root/'scores'/stage/'summary.json');status='scored'
        sessions=session_accounting(root,stage,plan)
        physical['serving_session_lower_seconds']+=sessions['lower_seconds']
        for key,value in [('serving_session_seconds',sessions['exact_seconds']),('serving_session_upper_seconds',sessions['upper_seconds'])]:
            physical[key]=physical[key]+value if physical[key] is not None and value is not None else None
        if sessions['status']!='complete':physical['accounting_status']='unresolved'
        samples=[r for p in directory.glob('resources-*.jsonl') for r in ledger(p)]
        result['stages'][stage]={'status':status,'assigned_observations':len(jobs),'terminal_observations':completed,
            'assigned_unique_questions':len({j['task_id'] for j in jobs}),'summary':summary,'session_accounting':sessions,
            'assigned_calls':sum(r[0]['calls'] for r in records if r),'authored_warmup_calls':len(list(directory.glob('warmup-*/paid.json'))),
            'warmup_identity':'separate authored baseline, matching settings, historical decoding hash; never an assigned observation',
            'resources':{k:max((r[k] for r in samples if r.get(k) is not None),default=None) for k in ('rss_parent_bytes','rss_children_bytes','peak_mlx_bytes','swap_used_bytes')}}
    base=sum(physical[k] for k in ('preparation_seconds','index_setup_seconds','scoring_seconds'))
    physical['total_seconds']=base+physical['serving_session_seconds'] if physical['accounting_status']=='complete' else None
    physical['total_lower_seconds']=base+physical['serving_session_lower_seconds']
    physical['total_upper_seconds']=base+physical['serving_session_upper_seconds'] if physical['serving_session_upper_seconds'] is not None else None
    result['interpretation']='Private aggregates only. Descriptive costs; engineering, prior assets, review and deployment adaptation excluded. No preservation, routing or business inference.'
    atomic_json(root/'aggregate-report.json',result)
    return result

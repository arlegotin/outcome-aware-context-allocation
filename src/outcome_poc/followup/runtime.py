"""Annotation-free, native sandboxed serving and retained job transactions."""
from contextlib import contextmanager
from dataclasses import asdict, replace, dataclass
from datetime import datetime, timezone
import fcntl
import importlib.abc
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import uuid

from ..data_runtime import DocumentStore, load_tasks
from ..generation import (NativeReaderFactory, Reader, offline_network, render_prompt,
                          prompt_identity, ranking_aliases)
from ..schemas import Document, GenerationRequest, ReaderResult, validate_record
from ..storage import append_jsonl, content_hash, atomic_json, read_jsonl
from .clock import continuous_ns, boot_identity
from .supervisor import ContinuousBackend, CleanupFailure
from .study import (read, identity, publish, verify, verify_files, verify_index,
                    STAGES, ORACLE)


class GoldImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {'outcome_poc.scoring','outcome_poc.data','outcome_poc.followup.scoring'}:
            raise ImportError('annotation-enabled module denied during serving')
        return None



def verify_import_origins(root):
    expected=Path(root)/'source/src/outcome_poc'
    for name,module in list(sys.modules.items()):
        if name.startswith('outcome_poc') and getattr(module,'__file__',None):
            if not Path(module.__file__).resolve().is_relative_to(expected):
                raise RuntimeError(f'non-snapshot import: {name}')
    if any(name in sys.modules for name in ('outcome_poc.scoring','outcome_poc.followup.scoring','outcome_poc.data')):
        raise RuntimeError('annotation-enabled module already imported during serving')


@dataclass(frozen=True)
class IsolatedReaderFactory:
    """Spawn skips package.__main__; enforce the boundary in the worker itself."""
    factory: object
    root: Path
    plan_hash: str
    session_start: Path | None = None

    def __call__(self):
        verify_import_origins(self.root)
        sys.meta_path.insert(0,GoldImportGuard())
        plan=read(self.root/'plan.json')
        if plan['plan_hash']!=self.plan_hash:raise ValueError('reader worker plan mismatch')
        probe_denials(plan['freeze']['denied_probes'])
        if self.session_start is not None:
            import psutil
            state=read(self.session_start)
            publish(self.session_start.parent/f"session-worker-{state['session']}-{os.getpid()}.json",
                {'session':state['session'],'plan_hash':self.plan_hash,'boot_id':state['boot_id'],
                 'pid':os.getpid(),'created':psutil.Process().create_time(),'continuous_ns':continuous_ns()})
            if os.getppid()!=state['parent_pid']:
                raise RuntimeError('reader coordinator exited before model acquisition')
        return self.factory()

def sandbox_profile(root, denied):
    """All writes restricted to new run/tmp; Gold/raw/outcome stores unreadable.

    Seatbelt uses the last matching rule. The root read grant permits the fresh
    run beneath an otherwise denied historical artifacts parent.
    """
    quote=lambda p:json.dumps(str(Path(p).resolve()))
    root=Path(root).resolve()
    lines=['(version 1)','(allow default)','(deny network*)','(deny file-write*)',
           f'(allow file-write* (subpath {quote(root)}))',
           '(allow file-write* (subpath "/private/tmp"))',
           f'(allow file-write* (subpath {quote(os.environ.get("TMPDIR","/private/tmp"))}))',
           '(allow file-write* (literal "/dev/null"))']
    lines.append(f'(allow file-read* (subpath {quote(root)}))')
    for path in sorted(set(str(Path(p).resolve()) for p in denied)):
        if root.is_relative_to(Path(path)):
            lines.append(f'(deny file-read* (require-all (subpath {quote(path)}) (require-not (subpath {quote(root)}))))')
        else:
            lines.append(f'(deny file-read* (subpath {quote(path)}))')
    lines.append(f'(deny file-read* (subpath {quote(root / "scores")}))')
    lines.append('(deny file-read* (regex #"[.]gold[.]jsonl$"))')
    return '\n'.join(lines)+'\n'


def probe_denials(paths):
    """Run inside kernel sandbox, before Python socket guards or paid work."""
    if not paths:
        raise ValueError('no actual denial paths supplied')
    for name in paths:
        try:
            with open(name,'rb') as stream:stream.read(1)
        except PermissionError:
            continue
        raise RuntimeError(f'kernel file denial probe did not deny: {name}')
    connection=socket.socket()
    try:
        try: connection.connect(('127.0.0.1',9))
        except PermissionError: pass
        else: raise RuntimeError('kernel network denial probe did not deny')
    finally:connection.close()
    return {'file_denials':len(paths),'network_denied':True}


@contextmanager
def stage_lock(root):
    with (Path(root)/'writer.lock').open('a+b') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('another follow-up writer is active')
        yield
        fcntl.flock(stream,fcntl.LOCK_UN)


def selected_jobs(root, stage):
    if stage not in STAGES:raise ValueError('unknown stage')
    return [j for j in read(Path(root)/'schedule.json') if j['stage']==stage]


def completion(root, plan, job):
    directory=Path(root)/'jobs'/job['job_id']
    marker=directory/'receipt.json'
    if not marker.exists():return None
    receipt=read(marker)
    if (receipt['plan_hash']!=plan['plan_hash'] or receipt['job_hash']!=content_hash(job) or
            receipt['boot_id']!=plan['freeze']['boot_id'] or receipt['stop_ns']<receipt['start_ns']):
        raise ValueError('mismatched completion receipt')
    actual={str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and p.name!='receipt.json'}
    if set(receipt['files'])!=actual or not {'started.json','terminal.json','attempts.jsonl'}<=actual:
        raise ValueError('completion receipt file inventory incomplete')
    verify_files({str(directory/name):value for name,value in receipt['files'].items()})
    state=read(directory/'started.json')
    attempts=list(read_jsonl(directory/'attempts.jsonl'))
    if (state['job_hash']!=content_hash(job) or state['plan_hash']!=plan['plan_hash'] or
            state['boot_id']!=receipt['boot_id'] or state['start_ns']!=receipt['start_ns'] or
            not attempts or attempts[-1].get('stop_ns')!=receipt['stop_ns']):
        raise ValueError('completion start/attempt binding mismatch')
    payload=read(directory/'terminal.json')
    if payload['job']!=job or payload['plan_hash']!=plan['plan_hash']:
        raise ValueError('mismatched completion payload')
    reconstructed=ReaderResult(**{**payload['result'],'citations':[tuple(c) for c in payload['result']['citations']]})
    validate_record(reconstructed)
    if payload['calls'] not in (0,1) or bool(payload['calls'])!=(directory/'paid.json').exists():
        raise ValueError('completion paid-call binding mismatch')
    if payload['calls'] and not payload.get('interrupted'):
        paid=read(directory/'paid.json')
        if (paid['request']['prompt_hash']!=payload['prompt_hash'] or
                paid['ranking_hash']!=content_hash(payload['ranking']) or paid['aliases']!=payload['aliases']):
            raise ValueError('completion prompt/ranking binding mismatch')
    if (receipt['seconds']!=(receipt['stop_ns']-receipt['start_ns'])/1e9 or
            receipt['calls']!=payload['calls']):
        raise ValueError('invalid completion timing/call count')
    return payload,receipt


def close_stage(root, plan, stage):
    root=Path(root)
    jobs=selected_jobs(root,stage)
    if not jobs:raise ValueError('empty assigned schedule')
    expected={j['job_id'] for j in jobs}
    stage_dir=root/'stages'/stage
    files={}
    for j in jobs:
        if completion(root,plan,j) is None:raise ValueError('stage schedule incomplete')
        directory=root/'jobs'/j['job_id']
        for p in directory.rglob('*'):
            if p.is_file():files[str(p.relative_to(root))]=identity(p)
    if stage=='headroom':
        files['headroom-decision.json']=identity(root/'headroom-decision.json')
        files['headroom-admission.json']=identity(root/'headroom-admission.json')
    all_jobs={j['job_id'] for j in read(root/'schedule.json')}
    if (root/'jobs').exists() and any(p.name not in all_jobs for p in (root/'jobs').iterdir()):
        raise ValueError('unassigned job directory')
    for p in stage_dir.rglob('*'):
        if p.is_file() and p.name!='closed.json': files[str(p.relative_to(root))]=identity(p)
    sessions=session_accounting(root,stage,plan,require_closed=True)
    closure={'session_accounting':sessions,'plan_hash':plan['plan_hash'],'stage':stage,'assigned_jobs':len(jobs),
             'assigned_unique_questions':len({j['task_id'] for j in jobs}),
             'job_ids_hash':content_hash(sorted(expected)),'files':files}
    publish(stage_dir/'closed.json',closure)
    return closure


def validate_closed_stage(root, stage, *, privileged=True):
    root=Path(root)
    marker=root/'stages'/stage/'closed.json'
    if not marker.exists():raise ValueError('stage schedule incomplete; scoring forbidden')
    plan=verify(root,privileged=False)
    closure=read(marker)
    if closure['plan_hash']!=plan['plan_hash']:raise ValueError('stage closure plan mismatch')
    verify_files({str(root/n):v for n,v in closure['files'].items()})
    if close_stage(root,plan,stage)!=closure:raise ValueError('stage closure mismatch')
    records=[(j,*completion(root,plan,j)) for j in selected_jobs(root,stage)]
    if privileged:verify(root,privileged=True)
    return plan,records


def _empty(reason):
    return ReaderResult('',None,[],'infra_error',0,0,[],[],reason)


def _commit(root, plan, job, state, payload, *, clock=continuous_ns, active=time.perf_counter_ns):
    directory=Path(root)/'jobs'/job['job_id']
    payload={**payload,'job':job,'plan_hash':plan['plan_hash']}
    # Payload publication precedes the enclosing stop. The separate receipt follows.
    publish(directory/'terminal.json',payload)
    stop=clock(); active_stop=active()
    append_jsonl(directory/'attempts.jsonl',{'kind':'terminal','stop_ns':stop,'status':payload['result']['status']})
    receipt={'plan_hash':plan['plan_hash'],'job_hash':content_hash(job),'boot_id':state['boot_id'],
         'start_ns':state['start_ns'],'stop_ns':stop,'seconds':(stop-state['start_ns'])/1e9,
         'active_seconds':(active_stop-state['active_start_ns'])/1e9,
         'drift_seconds':((stop-state['start_ns'])-(active_stop-state['active_start_ns']))/1e9,
         'calls':payload['calls'],'files':{str(p.relative_to(directory)):identity(p)
                        for p in directory.rglob('*') if p.is_file() and p.name!='receipt.json'}}
    publish(directory/'receipt.json',receipt)
    return payload,receipt


def execute_job(root, plan, job, task, documents, retrieval, backend, *, clock=continuous_ns,
                active=time.perf_counter_ns, session=None):
    """Execute once, or terminalize an interrupted attempt without semantic retry."""
    root=Path(root); directory=root/'jobs'/job['job_id']
    if job not in read(root/'schedule.json'):raise ValueError('unassigned job')
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
        result=replace(_empty('interrupted process; no semantic retry'),raw_output=progress.get('raw_output',''),
            prompt_tokens=len(progress.get('prompt_token_ids',[])),generated_tokens=len(progress.get('generated_token_ids',[])),
            prompt_token_ids=progress.get('prompt_token_ids',[]),generated_token_ids=progress.get('generated_token_ids',[]))
        return _commit(root,plan,job,state,{'result':asdict(result),'calls':int((directory/'paid.json').exists()),
            'evidence_ids':[],'ranking':[],'prompt_hash':None,'interrupted':True},clock=clock,active=active)
    backend.synchronize() # resident startup/sync charged in stage setup/lifecycle, outside warm service
    state={'job_hash':content_hash(job),'plan_hash':plan['plan_hash'],'boot_id':boot_identity(),
           'start_ns':clock(),'active_start_ns':active(),'started_utc':datetime.now(timezone.utc).isoformat(),'session':session}
    publish(state_path,state)
    append_jsonl(directory/'attempts.jsonl',{'kind':'start',**state})
    calls=0; evidence=[]; ranking=[]; aliases={}; prompt_hash=None; cleanup=None; result=None; synchronization_error=None
    try:
        # No ranking or answer reuse: every assigned serving call performs this query encoding.
        ranking=retrieval.rank(task.question,task.candidate_ids)
        if {r.doc_id for r in ranking}!=set(task.candidate_ids) or len(ranking)!=10:
            raise ValueError('ranking does not cover all candidates')
        publish(root/'ranking-identities'/f'{content_hash(task.task_id)}.json',{'task_id':task.task_id,
            'ranking':[asdict(r) for r in ranking]})
        aliases=ranking_aliases(ranking)
        if job['arm']==ORACLE:
            support={r['task_id']:r['support_doc_ids'] for r in read_jsonl(root/'support-doc-ids.jsonl')}
            chosen=[r.doc_id for r in ranking if r.doc_id in support[task.task_id]]
        else:chosen=[r.doc_id for r in ranking[:int(job['arm'])]]
        evidence=[documents.get(i) for i in chosen]
        prompt=render_prompt(task.question,evidence,aliases,backend.tokenizer)
        prompt_hash=prompt_identity(prompt,backend.tokenizer)
        settings=plan['freeze']['settings']['reader']; asset=read(root/'assets.json')['assets']['reader']
        request=GenerationRequest(asset['revision'],asset['snapshot_hash'],prompt_hash,
               content_hash({'greedy':True,'max_new_tokens':256,'prefill_step_size':512}),
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
        if result is not None:synchronization_error=reason
        result=replace(result,status='infra_error',stop_reason=reason) if result is not None else _empty(reason)
    payload={'result':asdict(result),'calls':calls,'evidence_ids':[d.doc_id for d in evidence],
             'ranking':[asdict(r) for r in ranking],'aliases':aliases,'prompt_hash':prompt_hash,
             'cleanup_error':cleanup,'synchronization_error':synchronization_error,'resources':getattr(backend,'last_resources',{})}
    committed=_commit(root,plan,job,state,payload,clock=clock,active=active)
    if cleanup:raise RuntimeError(f'cleanup failed; terminal result preserved: {cleanup}')
    if synchronization_error:raise RuntimeError(f'synchronization failed; terminal result preserved: {synchronization_error}')
    return committed


def warmup(root,plan,backend,directory):
    """One authored, unscored paid warm-up per resident session, outside schedule."""
    directory.mkdir(exist_ok=False)
    start=continuous_ns();active_start=time.perf_counter_ns()
    publish(directory/'started.json',{'start_ns':start,'active_start_ns':active_start,'calls':0,
        'kind':'authored warmup; never a cohort observation','plan_hash':plan['plan_hash']})
    sentences=['An invented lantern emits violet light.']
    doc=Document(content_hash(['Authored warmup',sentences]),'Authored warmup',sentences,sum(map(len,sentences)))
    backend.synchronize()
    aliases={'D0':doc.doc_id}
    prompt=render_prompt('What light does the invented lantern emit?',[doc],aliases,backend.tokenizer)
    asset=read(Path(root)/'assets.json')['assets']['reader']
    request=GenerationRequest(asset['revision'],asset['snapshot_hash'],prompt_identity(prompt,backend.tokenizer),
        content_hash({'greedy':True,'max_new_tokens':256,'prefill_step_size':512}),'answer',8192,256,120.,'none')
    def progress(text,prompt_ids,token_ids):
        atomic_json(directory/'progress.json',{'raw_output':text,'prompt_token_ids':prompt_ids,'generated_token_ids':token_ids})
    backend.progress_callback=progress
    cleanup=None
    publish(directory/'paid.json',{'request':asdict(request),'prompt':prompt,'calls':1})
    try:result=backend.generate(prompt,request,rendered=True)
    except CleanupFailure as error:
        result=error.result;cleanup=str(error.cleanup_error)
    publish(directory/'result.json',{'result':asdict(result),'cleanup_error':cleanup,'calls':1})
    stop=continuous_ns()
    publish(directory/'receipt.json',{'start_ns':start,'stop_ns':stop,'seconds':(stop-start)/1e9,
        'active_seconds':(time.perf_counter_ns()-active_start)/1e9,'result':identity(directory/'result.json'),
        'plan_hash':plan['plan_hash']})
    if cleanup or result.status in {'infra_error','timeout','context_overflow'}:
        raise RuntimeError('authored warmup failed; paid result retained')


class ResourceMonitor:
    """Separate RSS/MLX/swap observations, with explicit unavailable values."""
    def __init__(self, path, backend=None):
        self.path=path;self.backend=backend;self.stop_event=threading.Event();self.thread=None
    def sample(self):
        values={'continuous_ns':continuous_ns(),'active_ns':time.perf_counter_ns(),
                'rss_parent_bytes':None,'rss_children_bytes':None,'swap_used_bytes':None,
                'peak_mlx_bytes':getattr(self.backend,'peak_mlx_bytes',None),'sampling_seconds':2.}
        try:
            import psutil
            parent=psutil.Process()
            values.update(rss_parent_bytes=parent.memory_info().rss,
                rss_children_bytes=sum(c.memory_info().rss for c in parent.children(recursive=True)),
                swap_used_bytes=psutil.swap_memory().used)
        except Exception as error:values['unavailable']=str(error)
        append_jsonl(self.path,values)
        return values
    def _run(self):
        while not self.stop_event.wait(2.):self.sample()
    def start(self):
        self.sample();self.thread=threading.Thread(target=self._run,daemon=True);self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(3.)
        self.sample()


def resource_check(values):
    from ..environment import resource_gate
    try:physical=int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.memsize'],text=True))
    except Exception:physical=None
    parts=[values['rss_parent_bytes'],values['rss_children_bytes']]
    bound=sum(parts)+(values.get('peak_mlx_bytes') or 0) if all(p is not None for p in parts) else None
    result=resource_gate(physical,bound)
    return {**result,'bound_kind':'conservative overlapping parent+children RSS plus MLX peak'}


def _last_session_observation(root,stage_dir,state):
    """Only durable same-session continuous stamps contribute a lower bound."""
    observations=[state['start_ns']]
    resources=stage_dir/f"resources-{state['session']}.jsonl"
    if resources.exists():observations.extend(r['continuous_ns'] for r in read_jsonl(resources))
    observations.extend(read(p)['continuous_ns'] for p in stage_dir.glob(f"session-worker-{state['session']}-*.json"))
    setup=stage_dir/'setup.jsonl'
    if setup.exists():
        observations.extend(r['stop_ns'] for r in read_jsonl(setup)
            if r.get('session')==state['session'] and 'stop_ns' in r)
    warmup=stage_dir/f"warmup-{state['session']}"
    for name,key in (('started.json','start_ns'),('receipt.json','stop_ns')):
        if (warmup/name).exists():observations.append(read(warmup/name)[key])
    for path in (Path(root)/'jobs').glob('*/started.json'):
        job=read(path)
        if job.get('session')!=state['session']:continue
        observations.append(job['start_ns'])
        receipt=path.parent/'receipt.json'
        if receipt.exists():observations.append(read(receipt)['stop_ns'])
    return max(observations)


def _session_receipt(directory,state):
    original=directory/f"session-accounting-{state['session']}.json"
    reconciled=directory/f"session-reconciliation-{state['session']}.json"
    if reconciled.exists():
        if not original.exists() or read(reconciled)['prior_accounting_identity']!=identity(original):
            raise ValueError('resident reconciliation prior receipt mismatch')
        return reconciled
    return original


def _worker_identity_unknown(directory,state,plan,*,require_identity=False):
    workers=list(directory.glob(f"session-worker-{state['session']}-*.json"))
    unknown=(bool(state.get('reader_worker_expected')) or require_identity) and not workers
    for path in workers:
        import psutil
        worker=read(path)
        if worker['session']!=state['session'] or worker['plan_hash']!=plan['plan_hash'] or worker['boot_id']!=state['boot_id']:
            raise ValueError('owned resident worker identity mismatch')
        if type(worker.get('pid')) is not int or worker['pid']<=0 or type(worker.get('created')) not in (int,float):
            unknown=True
            continue
        try:
            process=psutil.Process(worker['pid'])
            if process.create_time()==worker['created'] and process.is_running() and process.status()!=psutil.STATUS_ZOMBIE:
                raise RuntimeError('owned orphan reader worker still alive; resume forbidden until it stops')
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,KeyError):unknown=True
    return bool(unknown)


def session_accounting(root,stage,plan,*,require_closed=False):
    """Do not turn uncertain interrupted endpoints into an exact physical sum."""
    root=Path(root);directory=root/'stages'/stage
    starts=sorted((read(p) for p in directory.glob('session-start-*.json')),key=lambda r:r['start_ns'])
    lower=upper=0.;exact=0.;open_count=interrupted=0;previous_upper=None
    for state in starts:
        if state['plan_hash']!=plan['plan_hash'] or state['boot_id']!=plan['freeze']['boot_id']:
            raise ValueError('resident session plan/boot mismatch')
        if previous_upper is not None and previous_upper>state['start_ns']:
            raise ValueError('resident session accounting intervals overlap')
        path=_session_receipt(directory,state)
        if not path.exists():
            open_count+=1;exact=None;upper=None;previous_upper=None
            lower+=(_last_session_observation(root,directory,state)-state['start_ns'])/1e9
            continue
        receipt=read(path)
        if (receipt['session']!=state['session'] or receipt['start_identity']!=identity(directory/f"session-start-{state['session']}.json") or
                receipt['plan_hash']!=plan['plan_hash'] or receipt['boot_id']!=state['boot_id'] or
                receipt['start_ns']!=state['start_ns'] or state['start_ns']>receipt['stop_lower_bound_ns'] or
                (receipt['stop_upper_bound_ns'] is not None and receipt['stop_lower_bound_ns']>receipt['stop_upper_bound_ns'])):
            raise ValueError('resident session accounting binding/bounds mismatch')
        if receipt['stop_ns'] is None:
            if receipt['timing_status']!='interrupted_stop_unknown':raise ValueError('invalid interrupted session accounting')
            interrupted+=1;exact=None
        else:
            if (receipt['timing_status']!='exact' or receipt['stop_ns']!=receipt['stop_lower_bound_ns'] or
                    receipt['stop_ns']!=receipt['stop_upper_bound_ns']):raise ValueError('invalid exact session accounting')
            if exact is not None:exact+=(receipt['stop_ns']-state['start_ns'])/1e9
        lower+=(receipt['stop_lower_bound_ns']-state['start_ns'])/1e9
        if receipt['stop_upper_bound_ns'] is None:upper=None
        elif upper is not None:upper+=(receipt['stop_upper_bound_ns']-state['start_ns'])/1e9
        previous_upper=receipt['stop_upper_bound_ns']
    if require_closed and open_count:raise ValueError('resident session lacks accountable closure')
    return {'sessions':len(starts),'open_sessions':open_count,'interrupted_sessions':interrupted,
        'status':'unresolved' if open_count or interrupted else 'complete',
        'exact_seconds':exact,'lower_seconds':lower,'upper_seconds':upper,
        'uncertainty':'interruption or failed reader shutdown has an unknown stop; bounds use durable observations and verified quiescence' if open_count or interrupted else None}


def reconcile_sessions(root,stage,plan):
    """Called under the single-writer lock, before the next session begins."""
    directory=Path(root)/'stages'/stage
    for path in sorted(directory.glob('session-start-*.json')):
        state=read(path)
        if state['plan_hash']!=plan['plan_hash'] or state['boot_id']!=boot_identity():
            raise ValueError('cannot reconcile resident session across plan/boot')
        receipt=_session_receipt(directory,state)
        existing=read(receipt) if receipt.exists() else None
        # Even a finite receipt cannot waive owned-worker quiescence checks.
        unknown=_worker_identity_unknown(directory,state,plan,
            require_identity=existing is not None and existing.get('cleanup_error') is not None)
        if existing is not None:
            if unknown:raise RuntimeError('resident worker identity remains unknown; automatic resume forbidden')
            if existing['stop_upper_bound_ns'] is not None:continue
        stop_upper=continuous_ns()
        stop_lower=_last_session_observation(root,directory,state)
        if existing is not None:stop_lower=max(stop_lower,existing['stop_lower_bound_ns'])
        if stop_lower>stop_upper:raise ValueError('resident session observation follows resume boundary')
        accounting={'session':state['session'],'plan_hash':plan['plan_hash'],'boot_id':state['boot_id'],
            'start_identity':identity(path),'start_ns':state['start_ns'],'stop_ns':None,
            'stop_lower_bound_ns':stop_lower,'stop_upper_bound_ns':None if unknown else stop_upper,
            'timing_status':'interrupted_stop_unknown','cleanup_status':'worker identity unknown' if unknown else 'known owned workers no longer alive'}
        if existing is not None:
            accounting['prior_accounting_identity']=identity(receipt)
            receipt=directory/f"session-reconciliation-{state['session']}.json"
        publish(receipt,accounting)
        if unknown:raise RuntimeError('resident worker identity unknown; automatic resume forbidden')
    return session_accounting(root,stage,plan,require_closed=True)


def attest_headroom(root,plan):
    """Privileged handoff: validate score bytes, publish only closure identities."""
    root=Path(root).resolve()
    validated,records=validate_closed_stage(root,'diagnosis')
    if validated!=plan:raise ValueError('headroom launcher plan mismatch')
    decision=read(root/'headroom-decision.json')
    scores=root/'scores/diagnosis'
    seal=read(scores/'closed.json')
    if (decision.get('plan_hash')!=plan['plan_hash'] or decision.get('decision')!='admit' or
            decision.get('diagnosis_scores')!=identity(scores/'closed.json') or
            seal.get('plan_hash')!=plan['plan_hash'] or seal.get('stage')!='diagnosis' or
            seal.get('assigned_observations')!=len(records) or
            seal.get('prediction_closure')!=identity(root/'stages/diagnosis/closed.json') or
            set(seal.get('files',{}))!={'scores.jsonl','summary.json'}):
        raise ValueError('headroom admission/scorer closure mismatch')
    verify_files({str(scores/name):value for name,value in seal['files'].items()})
    attestation={'kind':'closed-diagnosis-headroom-admission-v1','plan_hash':plan['plan_hash'],
        'boot_id':plan['freeze']['boot_id'],'decision':'admit',
        'decision_identity':identity(root/'headroom-decision.json'),
        'diagnosis_prediction_closure':identity(root/'stages/diagnosis/closed.json'),
        'scorer_closure_identity':identity(scores/'closed.json')}
    publish(root/'headroom-admission.json',attestation)
    return identity(root/'headroom-admission.json')


def validate_headroom_admission(root,plan,expected_sha256):
    """Serving validates the launcher handoff without opening any score file."""
    root=Path(root)
    if not expected_sha256 or identity(root/'headroom-admission.json')['sha256']!=expected_sha256:
        raise ValueError('missing or changed privileged headroom attestation')
    attestation=read(root/'headroom-admission.json')
    decision=read(root/'headroom-decision.json')
    expected={'kind':'closed-diagnosis-headroom-admission-v1','plan_hash':plan['plan_hash'],
        'boot_id':plan['freeze']['boot_id'],'decision':'admit',
        'decision_identity':identity(root/'headroom-decision.json'),
        'diagnosis_prediction_closure':identity(root/'stages/diagnosis/closed.json'),
        'scorer_closure_identity':decision.get('diagnosis_scores')}
    if (attestation!=expected or decision.get('plan_hash')!=plan['plan_hash'] or decision.get('decision')!='admit'):
        raise ValueError('headroom attestation/decision binding mismatch')
    return attestation


def run_stage(root, stage, *, backend_factory=None, encoder_factory=None, max_jobs=None):
    """Native entry; injectable dependencies exercise exactly this transaction engine."""
    from ..retrieval import EncoderBackend, Retrieval
    root=Path(root).resolve()
    plan=verify(root,privileged=False)
    if plan['freeze']['boot_id']!=boot_identity():raise ValueError('cross-boot resumption forbidden')
    verify_index(root/'index-setup')
    jobs=selected_jobs(root,stage)
    # Validate every existing completion before loading a model or generating.
    for job in jobs:completion(root,plan,job)
    if (root/'stages'/stage/'closed.json').exists():
        validate_closed_stage(root,stage,privileged=False)
        return {'status':'closed','jobs':len(jobs)}
    if stage=='diagnosis':validate_closed_stage(root,'calibration',privileged=False)
    if stage=='headroom':
        validate_closed_stage(root,'diagnosis',privileged=False)
        validate_headroom_admission(root,plan,os.environ.get('OUTCOME_FOLLOWUP_ADMISSION_SHA256'))
    assets=read(root/'assets.json')['assets']
    stage_dir=root/'stages'/stage;stage_dir.mkdir(parents=True,exist_ok=True)
    session=uuid.uuid4().hex
    monitor=ResourceMonitor(stage_dir/f'resources-{session}.jsonl')
    backend=None;error=None
    with stage_lock(root):
        reconcile_sessions(root,stage,plan)
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
                docs=DocumentStore(root/'documents.jsonl')
                retrieval=Retrieval(root/'index-setup/index',docs,encoder)
                reader_start=continuous_ns()
                factory=IsolatedReaderFactory(NativeReaderFactory(Path(assets['reader']['local_path']),
                    {**plan['freeze']['settings']['reader'],'asset':assets['reader']}),root,plan['plan_hash'],session_start)
                backend=(backend_factory or ContinuousBackend)(factory)
                monitor.backend=backend
                append_jsonl(stage_dir/'setup.jsonl',{'session':session,'kind':'reader_load',
                    'start_ns':reader_start,'stop_ns':continuous_ns(),'active_start_ns':active_start,'status':'ok'})
                tasks={t.task_id:t for t in load_tasks(root/'tasks.jsonl','fit_extension')}
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
    verify(root,privileged=False)
    if error:raise error
    if all(completion(root,plan,j) for j in jobs):
        close_stage(root,plan,stage)
        return {'status':'closed','jobs':len(jobs)}
    return {'status':'incomplete','assigned_jobs':len(jobs)}


def native_entry(root,stage):
    root=Path(root).resolve()
    # Imports must come from the sealed snapshot, including spawned children.
    verify_import_origins(root)
    sys.meta_path.insert(0,GoldImportGuard())
    plan=verify(root,privileged=False)
    probe=probe_denials(plan['freeze']['denied_probes'])
    append_jsonl(root/'denial-probes.jsonl',{'stage':stage,'profile':identity(root/'native.sb'),**probe})
    return run_stage(root,stage)


def launch(root,stage):
    root=Path(root).resolve()
    plan=verify(root)
    admission=attest_headroom(root,plan) if stage=='headroom' else None
    env={**os.environ,'PYTHONPATH':str(root/'source/src'),'PYTHONDONTWRITEBYTECODE':'1',
         'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false',
         'OUTCOME_FOLLOWUP_SERVING':str(root)}
    if admission:env['OUTCOME_FOLLOWUP_ADMISSION_SHA256']=admission['sha256']
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(root/'native.sb'),sys.executable,'-B','-m',
                          'outcome_poc.followup','_serve','--root',str(root),'--stage',stage],env=env)
    verify(root)
    if admission:verify_files({str(root/'headroom-admission.json'):admission})
    if result.returncode:raise RuntimeError(f'native stage failed: exit {result.returncode}')
    return {'stage':stage,'status':'native process exited successfully'}

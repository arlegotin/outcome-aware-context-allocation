"""Verified annotation-free confirmation orchestration and operational evidence.

Gold and statistical code are intentionally absent from this import closure.
"""
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path

from .data_runtime import Task
from .protocol import verify_protocol, verify_job, materialize_policy, file_hash
from .storage import atomic_json, append_jsonl, content_hash, read_jsonl, canonical_bytes


def immutable_json(path, value):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != canonical_bytes(value):
            raise ValueError('immutable operational artifact changed: '+str(path))
    else:
        atomic_json(path, value)


@dataclass(frozen=True)
class Execution:
    protocol_hash: str
    protocol: dict
    jobs: dict
    settings_hash: str


def initialize_execution(protocol, settings):
    checked = verify_protocol(Path(protocol['output_dir'])/'protocol.json')
    if checked != protocol: raise ValueError('execution protocol differs from frozen file')
    if any(settings.get(k) != v for k,v in protocol['methods']['reader'].items()):
        raise ValueError('runtime settings differ from frozen reader')
    if not protocol['fixture']:
        # The source snapshot is required even when the working tree happens to match.
        import os
        snapshot = Path(os.environ.get('OUTCOME_EXECUTION_SNAPSHOT', '/nonexistent')).resolve()
        if not Path(__file__).resolve().is_relative_to(snapshot):
            raise ValueError('protected native execution requires bound snapshot imports')
        for name,digest in protocol['source']['sha256'].items():
            if file_hash(snapshot/name) != digest: raise ValueError('execution snapshot checksum mismatch')
    return Execution(protocol['protocol_hash'], json.loads(canonical_bytes(protocol)),
                     {j['job_id']:j for j in protocol['schedule']['jobs']}, content_hash(settings))


def authorize_job(task, policy, runtime, job):
    session = getattr(runtime, '_protected_execution', None)
    if not isinstance(session, Execution): raise ValueError('protected serving requires verified execution')
    root=Path(session.protocol['run_dir']).resolve()
    if (root/'predictions.closed.json').exists(): raise ValueError('closed protected session cannot generate')
    if type(job.get('attempt')) is not int or job['attempt']<1:
        raise ValueError('protected serving requires a durable assigned attempt')
    attempt=root/'jobs'/job['job_id']/f"attempt-{job['attempt']}"
    if (job.get('_run_dir')!=root or job.get('_attempt_dir') is None or
        Path(job['_attempt_dir']).resolve()!=attempt or not (attempt/'started.json').is_file()):
        raise ValueError('protected serving requires a durable assigned attempt')
    row = session.jobs.get(job['job_id'])
    if row is None or job.get('protocol_hash') != session.protocol_hash:
        raise ValueError('protected job outside verified schedule')
    verify_job(session.protocol, row, task, runtime.config, job_index=session.jobs)
    expected = getattr(runtime, '_protected_jobs', {}).get(job['job_id'])
    if (expected is None or policy is not expected['policy'] or
        any(job.get(k) != expected.get(k) for k in ('run_id','mode','cache_mode','arm','repetition_id','caller_cap')) or
        content_hash(runtime.config) != session.settings_hash):
        raise ValueError('protected job/runtime changed after verification')


def run(protocol, runtime):
    from .runner import execute_job, close_run
    session = getattr(runtime, '_protected_execution', None)
    if not isinstance(session, Execution):
        session = initialize_execution(protocol, runtime.config)
        runtime._protected_execution = session
    if session.protocol != protocol or content_hash(runtime.config) != session.settings_hash:
        raise ValueError('verified execution runtime/protocol changed')
    tasks = {t.task_id:t for t in runtime.tasks}
    if len(tasks) != len(runtime.tasks) or set(tasks) != set(protocol['sample']['task_ids']):
        raise ValueError('runtime requires exact assigned sampled tasks')
    expected_documents={d for t in protocol['sample']['tasks'] for d in t['candidate_ids']}
    offsets=getattr(runtime.documents,'offsets',None)
    if (offsets is None and not protocol['fixture']) or (offsets is not None and set(offsets)!=expected_documents):
        raise ValueError('runtime requires exact selected document store')
    root = Path(protocol['run_dir'])
    root.mkdir(parents=True, exist_ok=True)
    immutable_json(root/'schedule.json', protocol['schedule'])
    immutable_json(root/'execution.json', {'protocol_hash':protocol['protocol_hash'],
        'digests':protocol['digests'], 'source':protocol['source'], 'runtime_settings':runtime.config})
    jobs=[]
    for row in protocol['schedule']['jobs']:
        task=tasks[row['task_id']]
        verify_job(protocol,row,task,runtime.config,job_index=session.jobs)
        jobs.append({**row, 'task':task, 'policy':materialize_policy(row['method'],runtime.models),
                     'protocol_hash':protocol['protocol_hash'], 'run_id':'confirmation', 'caller_cap':10})
    runtime._protected_jobs={j['job_id']:j for j in jobs}
    if (root/'protected-run.closed.json').exists():
        validate_run(protocol,root)
        return json.loads((root/'protected-run.closed.json').read_text())['result']
    now=getattr(runtime,'utcnow',lambda:datetime.now(timezone.utc).isoformat())
    completed=0; errors=[]
    for job in jobs:
        if datetime.fromisoformat(now()) >= datetime.fromisoformat(protocol['methods']['deadline_utc']):
            errors.append({'reason':'deadline_expired','job_id':job['job_id']});break
        latch=root/'protected-attempt.started.json'
        if not latch.exists():
            immutable_json(latch,{'protocol_hash':protocol['protocol_hash'],'first_job_id':job['job_id'], 'utc':now()})
        elif json.loads(latch.read_text())['protocol_hash'] != protocol['protocol_hash']:
            raise ValueError('protected first-attempt protocol changed')
        try:
            before_attempts=len(list((root/'jobs'/job['job_id']).glob('attempt-*')))
            prediction=execute_job(job,runtime,root)
            if prediction.status=='infra_error':
                # Retry only infrastructure failures, under the identical job/denominator.
                prediction=execute_job({**job,'retry_infrastructure':True},runtime,root)
            if prediction.status=='infra_error':
                errors.append({'reason':'unresolved_infrastructure','job_id':job['job_id']})
            completed+=1
            if prediction.attempt>before_attempts:
                append_jsonl(root/'resources.jsonl', {'job_id':job['job_id'],'attempt':prediction.attempt,
                    'utc':now(), **getattr(runtime.reader.backend,'last_resources',{})})
            append_jsonl(root/'progress.jsonl', {'assigned_jobs':len(jobs),'completed_jobs':completed,
                'job_id':job['job_id'],'status':prediction.status,'utc':now()})
        except (OSError,ValueError,RuntimeError) as error:
            errors.append({'reason':f'{type(error).__name__}:{error}','job_id':job['job_id']})
            append_jsonl(root/'execution-errors.jsonl',errors[-1])
            break
    if not errors and completed==len(jobs):
        try:
            if getattr(runtime.reader.backend,'pending_owner',None):
                from .runner import _consume_worker_lifecycle
                from .timing import TimingLedger
                ledger=TimingLedger(jobs[-1],jobs[-1]['policy'].policy_id,runtime.clock)
                try:
                    runtime.synchronize()
                finally:
                    _consume_worker_lifecycle(runtime,jobs[-1],ledger)
            closure=close_run(root,jobs)
        except (ValueError,OSError) as error:
            errors.append({'reason':f'{type(error).__name__}:{error}'})
    if errors or completed!=len(jobs):
        result={'status':'incomplete','assigned_jobs':len(jobs),'assigned_unique_tasks':protocol['sample']['n'],
                'completed_jobs':completed,'errors':errors,'protocol_hash':protocol['protocol_hash']}
        atomic_json(root/'incomplete.json',result)
        return result
    result={'status':'closed','assigned_jobs':len(jobs),'assigned_unique_tasks':protocol['sample']['n'],
            'completed_jobs':completed,'protocol_hash':protocol['protocol_hash']}
    hashes={name:file_hash(root/name) for name in ('predictions.closed.json','schedule.json','execution.json',
             'protected-attempt.started.json','resources.jsonl','progress.jsonl') if (root/name).exists()}
    immutable_json(root/'protected-run.closed.json',{'result':result,'hashes':hashes,
        'protocol_hash':protocol['protocol_hash'],'scientific_digests':protocol['digests']})
    return result


def validate_run(protocol, root):
    from .protocol import _verify_science
    from .runner import _prediction, validate_closed_accounting
    _verify_science(protocol)
    root=Path(root)
    if root.resolve()!=Path(protocol['run_dir']).resolve(): raise ValueError('protocol run directory mismatch')
    marker=json.loads((root/'protected-run.closed.json').read_text())
    if marker['protocol_hash']!=protocol['protocol_hash'] or marker['scientific_digests']!=protocol['digests']:
        raise ValueError('protected closure protocol mismatch')
    if any(file_hash(root/name)!=digest for name,digest in marker['hashes'].items()):
        raise ValueError('protected closure checksum mismatch')
    if json.loads((root/'schedule.json').read_text())!=protocol['schedule']:
        raise ValueError('protected schedule changed')
    predictions=[_prediction(r) for r in read_jsonl(root/'predictions.jsonl')]
    jobs=protocol['schedule']['jobs']
    if [p.job_id for p in predictions]!=[j['job_id'] for j in jobs]:
        raise ValueError('full assigned schedule required')
    for p,j in zip(predictions,jobs):
        spec=j['method'];family=spec['family']
        expected=(f'FIXED-{spec["k"]}' if family=='FIXED' else
                  f'ADAPTIVE-k-{"published" if family.endswith("published") else "tuned"}-B{spec["buffer"]}'
                  if family.startswith('ADAPTIVE-k') else spec.get('model_name',family))
        if (p.protocol_hash!=protocol['protocol_hash'] or p.task_id!=j['task_id'] or
            p.repetition_id!=j['repetition_id'] or p.policy_id!=expected or p.run_id!='confirmation'):
            raise ValueError('prediction does not match assigned protocol job')
    context=validate_closed_accounting(root,predictions)
    if context.receipt_coverage!='forward_v2': raise ValueError('protected scoring requires forward_v2 coverage')
    if not protocol['fixture']:
        completed=json.loads((root/'launch.completed.json').read_text())
        if completed['protocol_hash']!=protocol['protocol_hash'] or completed['returncode']!=0:
            raise ValueError('native process has not completed')
        for name,digest in completed['hashes'].items():
            if file_hash(root/name)!=digest: raise ValueError('native operational closure changed')
    return predictions,context


def job_evidence(protocol, root, predictions, scores):
    """Export complete attempt ownership; nested components are never summed anew."""
    from .runner import _observed_failure, _owned_reloads
    root=Path(root);byjob={s.job_id:s for s in scores};by_prediction={p.job_id:p for p in predictions}
    shared=list(read_jsonl(root/'shared-costs.jsonl')) if (root/'shared-costs.jsonl').exists() else []
    result=[]
    for job in protocol['schedule']['jobs']:
        p=by_prediction[job['job_id']];attempts=[];event_ids=[]
        for directory in sorted((root/'jobs'/p.job_id).glob('attempt-*'),key=lambda p:int(p.name.split('-')[-1])):
            if (directory/'observed-failure.closed.json').exists():
                _,events=_observed_failure(directory)
            else:
                from .schemas import CostEvent
                events=[CostEvent(**r) for r in read_jsonl(directory/'events.jsonl')]
            events+=_owned_reloads(directory)
            ids=[e.event_id for e in events];event_ids.extend(ids)
            attempts.append({'attempt':int(directory.name.split('-')[-1]),'event_ids':ids,
                'files':{str(path.relative_to(root)):file_hash(path) for path in sorted(directory.rglob('*')) if path.is_file()}})
        allocations=[{'event_id':r['event_id'],'source_id':r['source_id'],
                      'allocated_seconds':r['elapsed_seconds']/len(r['assigned_job_ids'])}
                     for r in shared if p.job_id in r['assigned_job_ids']]
        directory=root/'jobs'/p.job_id/f'attempt-{p.attempt}'
        paid=[json.loads(path.read_text()) for path in sorted(directory.glob('paid-*.finished.json'),key=lambda p:int(p.name.split('-')[1].split('.')[0]))]
        decision=json.loads((directory/'decision.json').read_text())
        final=paid[-1]['result'] if paid else None
        parity={'raw_output':p.raw_output,'answer':p.answer,'citations':p.citations,'status':p.status,
                'evidence_ids':p.evidence_ids,'prompt_hash':p.prompt_hash,
                'action':decision.get('decision'),'action_signature':decision.get('action_signature'),
                'prompt_token_ids':final['prompt_token_ids'] if final else [],
                'generated_token_ids':final['generated_token_ids'] if final else []}
        result.append({'job_id':p.job_id,'task_id':p.task_id,'scope':job['scope'],'arm':job['arm'],
            'config_id':job['method']['config_id'],'repetition_id':p.repetition_id,
            'prediction_hash':content_hash(p),'score_hash':content_hash(byjob[p.job_id]),
            'attempts':attempts,'event_ids':event_ids,'shared_allocations':allocations,
            'output_parity_hash':content_hash(parity),'status':p.status,
            'action_k':(decision.get('decision') or {}).get('action_k'),
            'prompt_tokens':p.prompt_tokens,
            'final_serving_start_ns':next(e.start_ns for e in events if e.role=='serving')})
    return {'protocol_hash':protocol['protocol_hash'],'jobs':result,
            'cost_authority':'ScoredTask complete validated accounting; components are nested'}


def selected_documents(protocol, source_path):
    """Publish only selected annotation-free documents, never full-store Runtime access."""
    import os
    import tempfile
    from .data_runtime import DocumentStore
    expected=sorted({i for t in protocol['sample']['tasks'] for i in t['candidate_ids']})
    if content_hash(expected)!=protocol['sample']['document_ids_hash']:
        raise ValueError('selected document identity changed')
    root=Path(protocol['run_dir']);root.mkdir(parents=True,exist_ok=True)
    path=root/'selected-documents.jsonl'
    if not path.exists():
        source=DocumentStore(Path(source_path))
        with tempfile.NamedTemporaryFile(dir=root,prefix='selected-documents-',delete=False) as stream:
            temporary=Path(stream.name)
            for identity in expected: stream.write(canonical_bytes(source.get(identity))+b'\n')
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    selected=DocumentStore(path)
    if set(selected.offsets)!=set(expected): raise ValueError('selected document projection changed')
    return selected


def realize_index(protocol, documents, encoder):
    """Realize the frozen index algorithm; seal bytes outside scientific manifests."""
    import time
    import sqlite3
    from .retrieval import build_index, _completed_manifest
    from .index_lineage import capture_lineage, reused_sources
    settings=protocol['methods']['retrieval'];index=Path(settings['index_dir'])
    root=Path(protocol['run_dir']);root.mkdir(parents=True,exist_ok=True)
    seal_path=Path(settings['operational_realization_path'])
    selected=sorted({i for t in protocol['sample']['tasks'] for i in t['candidate_ids']})
    if set(documents.offsets)!=set(selected) or content_hash(selected)!=protocol['sample']['document_ids_hash']:
        raise ValueError('sample-only index document identity mismatch')
    if seal_path.exists():
        seal=json.loads(seal_path.read_text())
        if (seal['scientific_digests']!=protocol['digests'] or seal['algorithm']!=settings or
            seal['document_ids_hash']!=protocol['sample']['document_ids_hash'] or
            any(file_hash(name)!=h for name,h in seal['files'].items())):
            raise ValueError('index operational checksum/identity changed')
        if 'index_lineage' not in seal:
            raise ValueError('legacy seal has no recursive lineage; preserve it without rebinding')
        capture_lineage(index,frozen=seal['index_lineage'])
        return _completed_manifest(index)
    if not (index/'manifest.json').exists():
        if index.exists() and any(index.iterdir()):
            # Preserve an interrupted index exactly; rebuild the same selected documents.
            import uuid
            index.rename(index.with_name(index.name+'-failed-'+uuid.uuid4().hex))
        started=time.perf_counter_ns()
        try:
            build_index((documents.get(i) for i in selected),encoder,index,
                        reuse_indexes=settings.get('reuse_indexes',()))
        finally:
            append_jsonl(root/'index-operational-attempts.jsonl',{'start_ns':started,'stop_ns':time.perf_counter_ns(),
                'completed_manifest_exists':(index/'manifest.json').exists(),'index_dir':str(index)})
    manifest=_completed_manifest(index)
    with sqlite3.connect(f'file:{index/"metadata.sqlite3"}?mode=ro',uri=True) as db:
        actual=sorted(r[0] for r in db.execute('SELECT doc_id FROM documents'))
    if actual!=selected: raise ValueError('realized index contains unassigned/missing documents')
    lineage=capture_lineage(index)
    paths=[documents.path,*(Path(p) for p in lineage['files'])]
    seal={'protocol_hash':protocol['protocol_hash'],'scientific_digests':protocol['digests'],
        'algorithm':settings,'document_ids_hash':content_hash(selected),'manifest_hash':content_hash(manifest),
        'files':{str(path):file_hash(path) for path in paths},'index_lineage':lineage,
        'reused_physical_sources':reused_sources(lineage),'new_physical_source_id':'index-attempt:'+manifest['completion']['attempt_id']}
    immutable_json(seal_path,seal)
    return manifest


def sandbox_profile(cwd, prepared):
    profile='(version 1)\n(allow default)\n(deny network*)\n'
    for path in (prepared/'gold',Path('data/gold'),Path('models/pinned/data')):
        profile+='(deny file-read* (subpath '+json.dumps(str((cwd/path).resolve()))+'))\n'
    return profile+'(deny file-read* (regex #".*[.]gold[.]jsonl$"))\n'


def capture_snapshot(protocol):
    import shutil
    root=Path(protocol['run_dir'])/'execution-snapshot';root.mkdir(parents=True,exist_ok=True)
    for name,digest in protocol['source']['sha256'].items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts: raise ValueError('snapshot source must be repository relative')
        destination=root/path
        if not destination.exists():
            if file_hash(path)!=digest: raise ValueError('source checksum changed before snapshot')
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
        if file_hash(destination)!=digest: raise ValueError('execution snapshot checksum mismatch')
    immutable_json(root/'snapshot.json',{'protocol_hash':protocol['protocol_hash'],'source':protocol['source']})
    return root


def launch(protocol_path):
    """Launch only bound code in an OS-restricted separate native process."""
    import os
    import subprocess
    import sys
    import time
    started=time.perf_counter_ns()
    protocol=verify_protocol(Path(protocol_path));root=Path(protocol['run_dir'])
    if protocol['fixture']: raise ValueError('fixture protocol cannot launch native benchmark')
    if (root/'launch.completed.json').exists():
        validate_run(protocol,root)
        return 0
    snapshot=capture_snapshot(protocol)
    profile=root/'native.sb'
    body=sandbox_profile(Path.cwd(),Path(protocol['methods']['retrieval']['prepared_dir']))
    if profile.exists() and profile.read_text()!=body: raise ValueError('native sandbox profile changed')
    profile.write_text(body)
    binding={'protocol_path':str(Path(protocol_path).resolve()),'protocol_hash':protocol['protocol_hash'],
        'source_snapshot':str(snapshot.resolve()),'sandbox_sha256':file_hash(profile)}
    immutable_json(root/'launch-plan.json',binding)
    attempt=len(list(root.glob('launch-*.started.json')))+1
    atomic_json(root/f'launch-{attempt}.started.json',{'start_ns':started,'utc':datetime.now(timezone.utc).isoformat(),
        'protocol_hash':protocol['protocol_hash'],'prepare_seconds':(time.perf_counter_ns()-started)/1e9})
    env={**os.environ,'PYTHONPATH':str((snapshot/'src').resolve()),'OUTCOME_EXECUTION_SNAPSHOT':str(snapshot.resolve()),
        'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}
    command=['/usr/bin/sandbox-exec','-f',str(profile.resolve()),str(Path('.venv/bin/python3.12').absolute()),
             str((snapshot/'tools/task14_native.py').resolve()),str((root/'launch-plan.json').resolve()),str(attempt)]
    print(json.dumps({'stage':'protected-native-launch','assigned_jobs':len(protocol['schedule']['jobs']),
        'assigned_unique_tasks':protocol['sample']['n'],'launch_attempt':attempt}),flush=True)
    with (root/f'launch-{attempt}.log').open('w') as log:
        process=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
    atomic_json(root/f'launch-{attempt}.finished.json',{'returncode':process.returncode,
        'elapsed_seconds':(time.perf_counter_ns()-started)/1e9,'protocol_hash':protocol['protocol_hash'],
        'cost_scope':'outer native envelope including setup/serving/telemetry; not additive'})
    if process.returncode!=0: raise RuntimeError('protected native launch incomplete; all attempts retained')
    names=['protected-run.closed.json','native-summary.json','index-realization.json','os-denials.json',
           'launch-plan.json','native.sb','execution-snapshot/snapshot.json','selected-documents.jsonl']
    names += [str(p.relative_to(root)) for pattern in ('native-*.json','launch-*.started.json','launch-*.finished.json',
              'system-state.jsonl','power.jsonl','index-operational-attempts.jsonl') for p in root.glob(pattern)]
    immutable_json(root/'launch.completed.json',{'protocol_hash':protocol['protocol_hash'],'returncode':0,
        'hashes':{name:file_hash(root/name) for name in sorted(set(names)) if (root/name).exists()}})
    print(json.dumps({'stage':'protected-native-closed','assigned_jobs':len(protocol['schedule']['jobs'])}),flush=True)
    return 0


def native_main(plan_path, launch_attempt):
    """Resident native worker; all setup and failures retain measured envelopes."""
    import os
    import subprocess
    import sys
    import threading
    import time
    import psutil
    from .data_runtime import DocumentStore
    from .environment import discover, resource_gate
    from .generation import NativeReaderFactory, SupervisedBackend, Reader, offline_network
    from .retrieval import EncoderBackend, Retrieval
    from .train import load_gate
    from .runner import Runtime, record_shared_cost
    start=time.perf_counter_ns();plan=json.loads(Path(plan_path).read_text())
    protocol=json.loads(Path(plan['protocol_path']).read_text());root=Path(protocol['run_dir'])
    from outcome_poc.reader_recipes import require_native_allocation_support
    require_native_allocation_support(protocol['methods']['reader'])
    stop=threading.Event();observer=None;charged_until=start;assigned=[j['job_id'] for j in protocol['schedule']['jobs']]
    setup_finished=False;startup_receipt={}
    def charge(role,begin,end,label):
        if end>begin: record_shared_cost(root,role,begin,end,assigned,source_id=f'task14-launch-{launch_attempt}:'+label)
    try:
        if protocol['protocol_hash']!=plan['protocol_hash']: raise ValueError('native launch protocol changed')
        if file_hash(root/'native.sb')!=plan['sandbox_sha256']: raise ValueError('native sandbox checksum changed')
        settings={**protocol['methods']['reader'],'source_binding':content_hash(protocol['source'])}
        session=initialize_execution(protocol,settings)
        probe="import errno,json,socket,sys\nr={}\nfor i,p in enumerate(sys.argv[1:]):\n try: open(p,'rb').read(1)\n except PermissionError: r[str(i)]=True\n else: r[str(i)]=False\ns=socket.socket();s.settimeout(.1)\ntry: s.connect(('1.1.1.1',443))\nexcept OSError as e: r['network']=e.errno in (errno.EPERM,errno.EACCES)\nelse: r['network']=False\nprint(json.dumps(r))"
        denied=['data/prepared/gold/gold.jsonl','models/pinned/data/hotpot_train_v1.1.json',
            'models/pinned/data/hotpot_dev_distractor_v1.json','artifacts/runs/task10-fit256/scores.gold.jsonl',
            'artifacts/runs/task12-tune128-retry/scores.gold.jsonl']
        denials=json.loads(subprocess.run([sys.executable,'-c',probe,*denied],capture_output=True,text=True,check=True).stdout)
        immutable_json(root/'os-denials.json',denials)
        if not all(denials.values()): raise ValueError('independent OS raw/gold/projection/network denial failed')
        environment=discover(root/f'environment-{launch_attempt}')
        if not environment['native_supported'] or not environment['resource_gate']['passed']: raise ValueError('native prerequisites')
        process=psutil.Process();peak=[process.memory_info().rss]
        def monitor():
            count=0
            while not stop.wait(2):
                try:
                    rss=process.memory_info().rss+sum(p.memory_info().rss for p in process.children(recursive=True) if p.is_running())
                    peak[0]=max(peak[0],rss)
                    append_jsonl(root/'system-state.jsonl',{'utc':datetime.now(timezone.utc).isoformat(),
                        'launch_attempt':launch_attempt,'process_tree_rss_bytes':rss,
                        'swap_used_bytes':psutil.swap_memory().used,'load_average':list(os.getloadavg())})
                    if count%30==0:
                        measures={}
                        for name,cmd in [('battery',['/usr/bin/pmset','-g','batt']),('thermal',['/usr/bin/pmset','-g','therm'])]:
                            result=subprocess.run(cmd,capture_output=True,text=True,timeout=5)
                            measures[name]={'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
                        append_jsonl(root/'power.jsonl',{'utc':datetime.now(timezone.utc).isoformat(),**measures})
                    count+=1
                except (psutil.NoSuchProcess,psutil.AccessDenied,subprocess.TimeoutExpired): pass
        observer=threading.Thread(target=monitor,daemon=True);observer.start()
        documents=selected_documents(protocol,Path(protocol['methods']['retrieval']['prepared_dir'])/'documents.jsonl')
        tasks=[Task(**t) for t in protocol['sample']['tasks']]
        models={name:load_gate(manifest) for name,manifest in protocol['methods']['models'].items()}
        manifests=[Path(p) for p in protocol['artifact_sha256'] if p.endswith('asset-manifest.json')]
        if len(manifests)!=1: raise ValueError('unique bound asset manifest required')
        assets=json.loads(manifests[0].read_text())['assets']
        with offline_network() as attempts:
            encoder=EncoderBackend(Path(assets['encoder']['local_path']))
            before_index=time.perf_counter_ns();charge('cold_setup',charged_until,before_index,'pre-index-setup');charged_until=before_index
            try:
                manifest=realize_index(protocol,documents,encoder)
            finally:
                after_index=time.perf_counter_ns();charge('offline',charged_until,after_index,'selected-index-build-or-load');charged_until=after_index
            retrieval=Retrieval(Path(protocol['methods']['retrieval']['index_dir']),documents,encoder)
            asset=assets['reader']
            reader_config={**protocol['methods']['reader'],'asset':asset}
            owner=pending_restart_owner(root)
            with resident_backend(NativeReaderFactory(Path(asset['local_path']),reader_config),owner,startup_receipt) as backend:
                if startup_receipt:
                    charge('cold_setup',charged_until,startup_receipt['start_ns'],'before-causal-restart')
                    charged_until=startup_receipt['stop_ns']
                settings={**settings,'index_manifest_hash':content_hash(manifest)}
                # The operational index identity is added once before admitting jobs.
                session=Execution(session.protocol_hash,session.protocol,session.jobs,content_hash(settings))
                runtime=Runtime(retrieval,documents,Reader(backend),settings)
                runtime.models=models;runtime.tasks=tasks;runtime._protected_execution=session
                runtime._lifecycle_seen=len(backend.lifecycle)
                ready=time.perf_counter_ns();charge('cold_setup',charged_until,ready,'post-index-runtime-setup');charged_until=ready;setup_finished=True
                result=run(protocol,runtime)
                if result['status']!='closed': raise RuntimeError('frozen confirmation remains incomplete')
        stop.set();observer.join()
        resources=list(read_jsonl(root/'resources.jsonl'))
        measured=[r['peak_mlx_bytes'] for r in resources if r.get('peak_mlx_bytes') is not None]
        peak_mlx=max(measured) if measured else None
        summary={'protocol_hash':protocol['protocol_hash'],'launch_attempt':launch_attempt,
            'elapsed_seconds':(time.perf_counter_ns()-start)/1e9,'os_denials':denials,'network_attempts':len(attempts),
            'sampled_peak_process_tree_rss_bytes':peak[0],'peak_mlx_bytes':peak_mlx,
            'resource_bound_kind':'sampled recursive process RSS plus overlapping MLX conservative bound',
            'resource_gate':resource_gate(environment['physical_memory_bytes'],peak[0]+peak_mlx) if peak_mlx is not None else None,
            'status':'closed','assigned_jobs':len(assigned)}
        immutable_json(root/'native-summary.json',summary)
        if attempts or summary['resource_gate'] is None or not summary['resource_gate']['passed']:
            raise ValueError('native network/resource validity failed')
        return summary
    except BaseException as error:
        stopped=time.perf_counter_ns()
        if not setup_finished and not (root/'predictions.closed.json').exists():
            if startup_receipt and charged_until<startup_receipt['start_ns']:
                charge('cold_setup',charged_until,startup_receipt['start_ns'],'before-failed-causal-restart')
                charged_until=startup_receipt['stop_ns']
            charge('cold_setup',charged_until,stopped,'failed-setup-remainder')
        atomic_json(root/f'native-{launch_attempt}.failure.json',{'protocol_hash':protocol.get('protocol_hash'),
            'elapsed_seconds':(stopped-start)/1e9,'error':f'{type(error).__name__}:{error}',
            'cost_scope':'observed native envelope, nested setup/attempt costs; never silently zero'})
        raise
    finally:
        stop.set()
        if observer is not None: observer.join(timeout=7)


def pending_restart_owner(root):
    from .runner import _check_recovery_settled
    root=Path(root);pending=[]
    for path in sorted(root.glob('jobs/*/attempt-*/recovery-pending.json')):
        record=json.loads(path.read_text());owner=record['owner']
        if (owner['run_dir']!=str(root.resolve()) or owner['job_id']!=path.parent.parent.name or
            owner['attempt']!=int(path.parent.name.split('-')[-1]) or record['recovery_id']!=content_hash(owner)):
            raise ValueError('persisted restart owner mismatch')
        try: _check_recovery_settled(path.parent)
        except ValueError:
            pending.append(owner)
    if len(pending)>1: raise ValueError('multiple unresolved causal worker owners require explicit incomplete accounting')
    return pending[0] if pending else None


def record_restart_load(owner, start_ns, stop_ns, success):
    from .schemas import CostEvent, validate_record
    root=Path(owner['run_dir'])
    if (root/'predictions.closed.json').exists(): raise ValueError('closed origin cannot receive restart costs')
    identity=content_hash({'owner':owner,'restart_load_start_ns':start_ns,'stop_ns':stop_ns,'success':success})
    event=CostEvent(identity,owner['run_id'],owner['task_id'],owner['policy_id'],'worker_reload',
        start_ns,stop_ns,(stop_ns-start_ns)/1e9,0,0,'none',None,None,None,None,owner['attempt'],'ok' if success else 'infra_error')
    validate_record(event)
    immutable_json(root/'jobs'/owner['job_id']/f'attempt-{owner["attempt"]}'/'reloads'/f'{identity}.json',
        {'job_id':owner['job_id'],'recovery_id':content_hash(owner),'event':event,'resolved':success})


@contextmanager
def resident_backend(factory, owner, startup_receipt):
    """Observe restarted worker loading even if its constructor fails."""
    import time
    from .generation import SupervisedBackend
    started=time.perf_counter_ns()
    try:
        backend=SupervisedBackend(factory)
    except BaseException:
        stopped=time.perf_counter_ns()
        if owner:
            record_restart_load(owner,started,stopped,False)
            startup_receipt.update(start_ns=started,stop_ns=stopped)
        raise
    stopped=time.perf_counter_ns()
    if owner:
        record_restart_load(owner,started,stopped,True)
        startup_receipt.update(start_ns=started,stop_ns=stopped)
    with backend as active:
        yield active

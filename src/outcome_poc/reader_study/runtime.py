"""One resident reader at a time, durable leaf transactions and paired closure."""
from dataclasses import dataclass
import importlib
import importlib.abc
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from ..data_runtime import DocumentStore, load_tasks
from ..generation import NativeReaderFactory, offline_network
from ..storage import append_jsonl, content_hash, read_jsonl
from ..followup.clock import continuous_ns, boot_identity
from ..followup.runtime import (close_stage as close_leaf, reconcile_sessions, session_accounting,
    warmup, probe_denials, sandbox_profile, verify_import_origins, _worker_identity_unknown)
from ..followup.supervisor import ContinuousBackend
from ..citation_study.runtime import execute_job, completion, recover_or_refuse, abort, FATAL
from ..reader_probe.profile import ProfileFactory
from ..reader_probe.runtime import AvailabilityMonitor, gate, _launch_ownership, _run_ownership, WRITER_FD
from .study import (read, publish, identity, verify, verify_leaf, leaf_root,
    READERS, STAGES, ADMISSION)

from ..followup.study import verify_files

SLOT = 'diagnosis'


def denial_paths(plan, stage, *, probes=False):
    key = 'denied_probes' if probes else 'denied_paths'
    result = list(plan['freeze'][key]) + list(plan['freeze']['source_files'])
    if stage == 'development':
        result += plan['freeze']['confirmation_'+key]
    return result


class ImportGuard(importlib.abc.MetaPathFinder):
    def __init__(self, names): self.names = names
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == n or fullname.startswith(n+'.') for n in self.names):
            raise ImportError('reader study annotation import denied')


def isolation(root, stage, plan):
    verify_import_origins(root)
    names = plan['freeze']['denied_modules']
    if any(n == d or n.startswith(d+'.') for n in sys.modules for d in names):
        raise RuntimeError('annotation-enabled module already imported')
    guard = ImportGuard(names)
    sys.meta_path.insert(0, guard)
    for name in names:
        try: importlib.import_module(name)
        except ImportError as error:
            if 'reader study annotation import denied' in str(error): continue
            guard.find_spec(name)
        raise RuntimeError('annotation import probe failed')
    if boot_identity() != plan['freeze']['boot_id']: raise ValueError('plan boot mismatch')
    return {**probe_denials(denial_paths(plan, stage, probes=True)), 'import_denials':names,
        'snapshot_origins':True, 'plan_hash':plan['plan_hash'], 'scientific_stage':stage}


@dataclass(frozen=True)
class IsolatedReaderFactory:
    factory: object
    root: Path
    stage: str
    reader_id: str
    plan_hash: str
    session_start: Path

    def __call__(self):
        import psutil
        state = read(self.session_start)
        # Generic supervisor/reconciliation identity deliberately binds the leaf.
        publish(self.session_start.parent/f"session-worker-{state['session']}-{os.getpid()}.json",
            {'session':state['session'], 'plan_hash':self.plan_hash, 'boot_id':boot_identity(),
             'pid':os.getpid(), 'created':psutil.Process().create_time(), 'continuous_ns':continuous_ns()})
        plan = verify(self.root, stage=self.stage)
        leaf = verify_leaf(self.root, self.stage, self.reader_id, plan)
        if leaf['plan_hash'] != self.plan_hash or state['plan_hash'] != self.plan_hash:
            raise ValueError('worker leaf/session binding mismatch')
        if state['reader_id'] != self.reader_id or state['scientific_stage'] != self.stage:
            raise ValueError('worker reader/stage mismatch')
        probes = isolation(self.root, self.stage, plan)
        expected = {**leaf['freeze']['settings']['reader'],
                    'asset':read(leaf_root(self.root,self.stage,self.reader_id)/'assets.json')['assets']['reader']}
        factory_type = ProfileFactory if self.reader_id == 'qwen14b-nonthinking' else NativeReaderFactory
        if (not isinstance(self.factory, factory_type) or self.factory.config != expected or
            self.factory.snapshot.resolve() != Path(expected['asset']['local_path']).resolve()):
            raise ValueError('worker reader factory/profile mismatch')
        if os.getppid() != state['parent_pid'] or psutil.Process(os.getppid()).create_time() != state['parent_created']:
            raise RuntimeError('coordinator process identity changed')
        publish(self.session_start.parent/f"worker-probes-{state['session']}.json",
            {**probes, 'reader_id':self.reader_id, 'leaf_plan_hash':self.plan_hash,
             'profile':leaf['freeze']['leaf_binding'], 'session':state['session'], 'pid':os.getpid()})
        return self.factory()


def validate_admission(root, plan=None):
    """Annotation-free attestation check; launcher also verifies scorer files."""
    root=Path(root).resolve();plan=plan or verify(root)
    path=root/'confirmation-admission.json'
    if not path.exists(): raise ValueError('confirmation admission missing')
    expected_hash=os.environ.get('OUTCOME_READER_STUDY_ADMISSION')
    if os.environ.get('OUTCOME_READER_STUDY_SERVING') and not expected_hash:
        raise ValueError('confirmation admission launcher identity missing')
    if expected_hash and identity(path)['sha256'] != expected_hash:
        raise ValueError('confirmation admission identity changed')
    att=read(path);decision=read(root/'confirmation-decision.json')
    expected={'kind':'reader-quality-confirmation-admission-v1','plan_hash':plan['plan_hash'],
        'boot_id':plan['freeze']['boot_id'],'rule':ADMISSION,'decision':'admit',
        'decision_identity':identity(root/'confirmation-decision.json'),
        'development_closure':identity(root/'stages/development/closed.json'),
        'score_attestation':identity(root/'development-score-attestation.json')}
    score=read(root/'development-score-attestation.json')
    counts=decision.get('natural_counts',{})
    old=counts.get('qwen4b-instruct',{});new=counts.get('qwen14b-nonthinking',{})
    if (att!=expected or decision.get('decision')!='admit' or decision.get('plan_hash')!=plan['plan_hash'] or
        decision.get('rule')!=ADMISSION or decision.get('healthy') is not True or
        decision.get('assigned_observations')!=96 or decision.get('development_closure')!=expected['development_closure'] or
        decision.get('score_seal_hash')!=content_hash(score) or score.get('prediction_closure')!=expected['development_closure'] or
        score.get('plan_hash')!=plan['plan_hash'] or score.get('scientific_stage')!='development' or
        score.get('assigned_observations')!=96 or not all(a in old and a in new for a in ('2','10')) or
        new['10']['joint_em']<=old['10']['joint_em'] or
        any(new[a]['answer_em']<old[a]['answer_em'] for a in ('2','10'))):
        raise ValueError('confirmation admission binding/rule mismatch')
    return att


def _jobs(root,stage):
    if stage not in STAGES: raise ValueError('unknown scientific stage')
    if {p.name for p in (root/'leaves'/stage).iterdir()}!=set(READERS):
        raise ValueError('unknown or missing reader leaf')
    return [j for j in read(root/'schedule.json') if j['scientific_stage']==stage]


def _inventory(directory, root, *, exclude=()):
    return {str(p.relative_to(root)):identity(p) for p in sorted(directory.rglob('*'))
            if p.is_file() and p not in exclude}


def _stage_contents(root,stage,plan):
    jobs=_jobs(root,stage);records=[];leaves={};parity={}
    for reader in dict.fromkeys(j['reader_id'] for j in jobs):
        leaf=leaf_root(root,stage,reader);lp=verify_leaf(root,stage,reader,plan)
        directory=leaf/'stages'/SLOT
        if (directory/'aborted.json').exists(): raise ValueError('aborted stage cannot close')
        if not (directory/'closed.json').exists(): raise ValueError('leaf schedule incomplete')
        closure=read(directory/'closed.json')
        verify_files({str(leaf/n):v for n,v in closure['files'].items()})
        if close_leaf(leaf,lp,SLOT)!=closure: raise ValueError('leaf closure changed')
        if closure['session_accounting']['upper_seconds'] is None: raise ValueError('unknown quiescence')
        for path in directory.glob('session-start-*.json'):
            state=read(path)
            if _worker_identity_unknown(directory,state,lp,require_identity=state.get('native_execution',False) and (directory/f"acquisition-{state['session']}.json").exists()):
                raise ValueError('unknown worker identity at closure')
        leaves[reader]=identity(directory/'closed.json')
        for job in [j for j in jobs if j['reader_id']==reader]:
            completed=completion(leaf,lp,job)
            if completed is None: raise ValueError('assigned schedule incomplete')
            payload,receipt=completed;records.append((job,payload,receipt))
            if job['arm'] in ('2','10'):
                key=(job['task_id'],job['arm'])
                matched={k:payload[k] for k in ('ranking','evidence_ids','aliases')}
                if key in parity and parity[key]!=matched: raise ValueError('matched ranking/evidence parity mismatch')
                parity[key]=matched
    records.sort(key=lambda r:r[0]['ordinal'])
    envelope=root/'stages'/stage/'index-envelope.json'
    if not envelope.exists(): raise ValueError('shared index missing')
    closure={'plan_hash':plan['plan_hash'],'scientific_stage':stage,'assigned_observations':len(records),
        'job_ids_hash':content_hash(sorted(j['job_id'] for j in jobs)), 'leaf_closures':leaves,
        'input_identities':plan['stage_files'][stage], 'index_envelope':identity(envelope),
        'admission_identities':{name:identity(root/name) for name in ('confirmation-admission.json',
            'confirmation-decision.json','development-score-attestation.json')} if stage=='confirmation' else None,
        'parity_hash':content_hash([[list(k),v] for k,v in sorted(parity.items())]),
        'files':{**_inventory(root/'leaves'/stage,root),
                 **_inventory(root/'stages'/stage,root,exclude=(root/'stages'/stage/'closed.json',))}}
    return closure,records


def validate_closed_stage(root, stage):
    root=Path(root).resolve();marker=root/'stages'/stage/'closed.json'
    if not marker.exists(): raise ValueError('stage schedule incomplete; scoring forbidden')
    plan=verify(root,stage=stage)
    closure,records=_stage_contents(root,stage,plan)
    if read(marker)!=closure: raise ValueError('outer stage closure mismatch')
    return {'plan':plan,'closure':closure,'records':records}


def _close(root,stage,plan):
    closure,_=_stage_contents(root,stage,plan)
    publish(root/'stages'/stage/'closed.json',closure)
    return {'status':'closed','scientific_stage':stage,'assigned_observations':closure['assigned_observations']}


def _session(root,stage,reader,plan,jobs,backend_factory,encoder_factory,max_jobs):
    """Lifecycle adapter; all per-attempt work remains in the existing engine."""
    from ..retrieval import EncoderBackend, Retrieval
    import psutil
    leaf=leaf_root(root,stage,reader);lp=verify_leaf(root,stage,reader,plan)
    directory=leaf/'stages'/SLOT;directory.mkdir(parents=True,exist_ok=True)
    session=uuid.uuid4().hex;start=continuous_ns();active=time.perf_counter_ns()
    state={'session':session,'plan_hash':lp['plan_hash'],'boot_id':boot_identity(),
        'start_ns':start,'active_start_ns':active,'parent_pid':os.getpid(),
        'parent_created':psutil.Process().create_time(),'reader_worker_expected':False,
        'native_execution':backend_factory is None,'reader_id':reader,'scientific_stage':stage}
    path=directory/f'session-start-{session}.json';publish(path,state)
    monitor=AvailabilityMonitor(directory/f'resources-{session}.jsonl')
    gate_dir=directory/f'gates-{session}';gate_dir.mkdir()
    backend=None;error=cleanup=None;done=0;acquisition=False
    try:
        if backend_factory is None:
            if os.environ.get('OUTCOME_READER_STUDY_SERVING')!=str(root): raise RuntimeError('native run requires sandbox launch')
            publish(directory/f'coordinator-probes-{session}.json',
                {**isolation(root,stage,plan),'reader_id':reader,'leaf_plan_hash':lp['plan_hash'],
                 'profile':lp['freeze']['leaf_binding'],'session':session,'pid':os.getpid()})
        monitor.start();gate(monitor,gate_dir,'before_acquisition')
        assets=read(leaf/'assets.json')['assets']
        with offline_network():
            loaded=continuous_ns()
            encoder=(encoder_factory or EncoderBackend)(Path(assets['encoder']['local_path']))
            append_jsonl(directory/'setup.jsonl',{'session':session,'kind':'encoder_load','start_ns':loaded,'stop_ns':continuous_ns()})
            if encoder.identity!={k:assets['encoder'][k] for k in ('revision','snapshot_hash')}: raise ValueError('encoder identity mismatch')
            docs=DocumentStore(leaf/'inputs'/SLOT/'documents.jsonl')
            envelope=read(root/'stages'/stage/'index-envelope.json')
            retrieval=Retrieval(Path(envelope['index_path']),docs,encoder)
            kind=ProfileFactory if reader=='qwen14b-nonthinking' else NativeReaderFactory
            factory=IsolatedReaderFactory(kind(Path(assets['reader']['local_path']),
                {**lp['freeze']['settings']['reader'],'asset':assets['reader']}),root,stage,reader,lp['plan_hash'],path)
            loaded=continuous_ns();acquisition=True
            publish(directory/f'acquisition-{session}.json',{'continuous_ns':loaded,'active_ns':time.perf_counter_ns()})
            constructor=backend_factory or ContinuousBackend
            if isinstance(constructor,type):
                backend=constructor.__new__(constructor);constructor.__init__(backend,factory)
            else: backend=constructor(factory)
            monitor.backend=backend
            append_jsonl(directory/'setup.jsonl',{'session':session,'kind':'reader_load','start_ns':loaded,'stop_ns':continuous_ns()})
            gate(monitor,gate_dir,'after_acquisition',acquired=True)
            gate(monitor,gate_dir,'before_warmup',acquired=True)
            try: warmup(leaf,lp,backend,directory/f'warmup-{session}')
            finally: gate(monitor,gate_dir,'after_warmup',acquired=True)
            publish(directory/f'warmup-profile-{session}.json',{'reader_id':reader,'scientific_stage':stage,
                'profile':lp['freeze']['leaf_binding'],'settings':lp['freeze']['settings']['reader'],
                'paid':identity(directory/f'warmup-{session}'/'paid.json')})
            tasks={t.task_id:t for t in load_tasks(leaf/'inputs'/SLOT/'tasks.jsonl','fit_extension')}
            for job in jobs:
                if completion(leaf,lp,job): continue
                gate(monitor,gate_dir,'before_'+job['job_id'],acquired=True)
                backend.job_owner=job['job_id']
                try: execute_job(leaf,lp,job,tasks[job['task_id']],docs,retrieval,backend,session=session)
                finally: gate(monitor,gate_dir,'after_'+job['job_id'],acquired=True)
                done+=1
                if max_jobs is not None and done>=max_jobs: break
    except BaseException as caught: error=caught
    finally:
        if backend is not None:
            try: backend.close()
            except BaseException as caught: cleanup=f'{type(caught).__name__}: {caught}';error=error or caught
            for row in getattr(backend,'lifecycle',[]): append_jsonl(directory/'lifecycle.jsonl',{'session':session,**row})
        if acquisition:
            try:
                if _worker_identity_unknown(directory,state,lp,require_identity=backend_factory is None):
                    raise RuntimeError('owned worker identity unknown; quiescence unverified')
            except BaseException as caught: cleanup=cleanup or str(caught);error=error or caught
        try: monitor.stop()
        except BaseException as caught: error=error or caught
        stop=continuous_ns()
        publish(directory/f'session-accounting-{session}.json',{'session':session,'plan_hash':lp['plan_hash'],
            'boot_id':state['boot_id'],'start_identity':identity(path),'start_ns':start,
            'stop_ns':None if cleanup else stop,'stop_lower_bound_ns':stop,'stop_upper_bound_ns':None if cleanup else stop,
            'active_start_ns':active,'active_stop_ns':time.perf_counter_ns(),
            'timing_status':'interrupted_stop_unknown' if cleanup else 'exact','cleanup_error':cleanup,
            'status':'failed' if error else 'ok','error':str(error) if error else None})
        paid_warmup=(directory/f'warmup-{session}'/'paid.json').exists()
        if cleanup or (error and (paid_warmup or any(read(p).get('session')==session for p in (leaf/'jobs').glob('*/started.json')))):
            abort(leaf,lp,SLOT,'session failure or unknown quiescence')
    if error: raise error
    if all(completion(leaf,lp,j) for j in jobs): close_leaf(leaf,lp,SLOT)
    return done


def run_stage(root, stage, *, backend_factory=None, encoder_factory=None, max_jobs=None):
    root=Path(root).resolve()
    if max_jobs is not None and (type(max_jobs) is not int or max_jobs<1): raise ValueError('max_jobs must be positive')
    with _run_ownership(root):
        plan=verify(root,stage=stage)
        if (root/'stages'/stage/'closed.json').exists():
            closed=validate_closed_stage(root,stage)['closure']
            return {'status':'closed','scientific_stage':stage,'assigned_observations':closed['assigned_observations']}
        if boot_identity()!=plan['freeze']['boot_id']: raise ValueError('cross-boot resumption forbidden')
        if not (root/'stages'/stage/'index-envelope.json').exists(): raise ValueError('shared index missing')
        jobs=_jobs(root,stage)
        # Reconcile both readers before acquiring either. An aborted later block cannot hide.
        for reader in READERS:
            leaf=leaf_root(root,stage,reader);lp=verify_leaf(root,stage,reader,plan)
            reconcile_sessions(leaf,SLOT,lp)
            for warm in (leaf/'stages'/SLOT).glob('warmup-*'):
                if warm.is_dir() and (warm/'paid.json').exists() and not (warm/'receipt.json').exists():
                    abort(leaf,lp,SLOT,'interrupted paid warmup; no semantic retry')
            recover_or_refuse(leaf,lp,SLOT,[j for j in jobs if j['reader_id']==reader])
        done=0
        for reader in dict.fromkeys(j['reader_id'] for j in jobs):
            leaf=leaf_root(root,stage,reader);lp=verify_leaf(root,stage,reader,plan)
            selected=[j for j in jobs if j['reader_id']==reader]
            if all(completion(leaf,lp,j) for j in selected):
                close_leaf(leaf,lp,SLOT);continue
            done+=_session(root,stage,reader,plan,selected,backend_factory,encoder_factory,
                None if max_jobs is None else max_jobs-done)
            if max_jobs is not None and done>=max_jobs: break
        if all((leaf_root(root,stage,r)/'stages'/SLOT/'closed.json').exists() for r in READERS):
            # Launcher seals its logs only after the child and streams have closed.
            if os.environ.get('OUTCOME_READER_STUDY_SERVING')==str(root): return {'status':'ready_to_close'}
            return _close(root,stage,plan)
        return {'status':'incomplete','scientific_stage':stage,'assigned_observations':len(jobs)}


def launch_binding(root,stage,plan):
    directory=root/'stages'/stage/('launch-'+uuid.uuid4().hex);directory.mkdir(parents=True)
    (directory/'native.sb').write_text(sandbox_profile(root,denial_paths(plan,stage)))
    publish(directory/'binding.json',{'plan_hash':plan['plan_hash'],'scientific_stage':stage,
        'boot_id':plan['freeze']['boot_id'],'profile':identity(directory/'native.sb'),
        'denial_probes':denial_paths(plan,stage,probes=True)})
    return directory


def native_entry(root,stage):
    root=Path(root).resolve();verify_import_origins(root);plan=verify(root,stage=stage)
    directory=Path(os.environ['OUTCOME_READER_STUDY_LAUNCH']).resolve()
    if directory.parent!=root/'stages'/stage: raise ValueError('native launch outside stage')
    expected={'plan_hash':plan['plan_hash'],'scientific_stage':stage,'boot_id':boot_identity(),
        'profile':identity(directory/'native.sb'),'denial_probes':denial_paths(plan,stage,probes=True)}
    if read(directory/'binding.json')!=expected or (directory/'native.sb').read_text()!=sandbox_profile(root,denial_paths(plan,stage)):
        raise ValueError('native launch profile mismatch')
    isolation(root,stage,plan)
    return run_stage(root,stage)


def launch(root, stage):
    root=Path(root).resolve()
    with _launch_ownership(root) as descriptor:
        plan=verify(root,stage=stage)
        if (root/'stages'/stage/'closed.json').exists():
            closed=validate_closed_stage(root,stage)['closure']
            return {'status':'closed','scientific_stage':stage,'assigned_observations':closed['assigned_observations']}
        admission=None
        if stage=='confirmation':
            from .scoring import validate_score_seal
            validate_score_seal(root,'development',plan)
            validate_admission(root,plan);admission=identity(root/'confirmation-admission.json')['sha256']
        directory=launch_binding(root,stage,plan)
        env={**os.environ,'PYTHONPATH':str(root/'source/src'),'PYTHONDONTWRITEBYTECODE':'1',
            'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_DATASETS_OFFLINE':'1',
            'OUTCOME_READER_PROBE_SERVING':str(root),WRITER_FD:str(descriptor),
            'OUTCOME_READER_STUDY_SERVING':str(root),'OUTCOME_READER_STUDY_LAUNCH':str(directory)}
        if admission: env['OUTCOME_READER_STUDY_ADMISSION']=admission
        command=['/usr/bin/sandbox-exec','-f',str(directory/'native.sb'),sys.executable,'-B','-m',
                 'outcome_poc.reader_study','_serve','--root',str(root),'--stage',stage]
        publish(directory/'launch.json',{'command':command,'start_ns':continuous_ns(),'binding':identity(directory/'binding.json')})
        with (directory/'stdout.txt').open('w') as stdout,(directory/'stderr.txt').open('w') as stderr:
            process=subprocess.run(command,cwd=root/'source',env=env,stdout=stdout,stderr=stderr,pass_fds=(descriptor,))
        publish(directory/'exit.json',{'returncode':process.returncode,'stop_ns':continuous_ns()})
        if process.returncode: raise RuntimeError(f'native stage failed: exit {process.returncode}; logs: {directory}')
        plan=verify(root,stage=stage)
        return _close(root,stage,plan)

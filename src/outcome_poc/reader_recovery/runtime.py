"""New diagnostic adapter over existing supervisor, transaction and cost primitives.

There is deliberately no confirmation launcher or automatic resumption. An
interrupted group stays incomplete/unscored; its starts/progress/costs survive.
"""
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import importlib.abc
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from ..data_runtime import DocumentStore
from ..generation import NativeReaderFactory, offline_network, ranking_aliases, prompt_identity
from ..schemas import GenerationRequest, ReaderResult
from ..storage import append_jsonl, atomic_json, content_hash, read_jsonl
from ..followup.clock import continuous_ns, clock_identity, boot_identity
from ..followup.supervisor import ContinuousBackend, CleanupFailure
from ..followup.runtime import (_commit, completion, ResourceMonitor, resource_check, stage_lock,
    sandbox_profile, probe_denials, _worker_identity_unknown, session_accounting, warmup)
from ..followup.study import verify_index
from .study import verify, read, identity, publish, jobs,group_arms,is_fresh_validation,is_validation
from .evidence import render_view, parse_view
from .prompts import render_condition
from .action_study_v4 import is_action
from .learning_study_v5 import is_learning

DENIED_MODULES = ('outcome_poc.data','outcome_poc.scoring','outcome_poc.followup.scoring',
    'outcome_poc.citation_study.preparation','outcome_poc.citation_study.scoring',
    'outcome_poc.reader_study.preparation','outcome_poc.reader_study.scoring',
    'outcome_poc.reader_recovery.preparation','outcome_poc.reader_recovery.scoring',
    'outcome_poc.reader_recovery.validation','outcome_poc.reader_recovery.fresh',
    'outcome_poc.reader_recovery.preparation_v3','outcome_poc.reader_recovery.precision',
    'outcome_poc.reader_recovery.action_preparation_v4','outcome_poc.reader_recovery.action_analysis_v4',
    'outcome_poc.reader_recovery.learning_preparation_v5','outcome_poc.heldout')


def remaining_window(plan, required_seconds):
    remaining = (datetime.fromisoformat(plan['config']['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()
    if remaining < required_seconds:
        raise TimeoutError('insufficient authorized window for bounded startup/request and cleanup')
    return remaining


class WindowedBackend:
    """Check at every actual paid-call boundary, including shared warmup."""
    def __init__(self,backend,plan,admission=None):
        object.__setattr__(self,'_backend',backend)
        object.__setattr__(self,'_plan',plan)
        object.__setattr__(self,'_admission',admission)

    def __getattr__(self,name):
        return getattr(self._backend,name)

    def __setattr__(self,name,value):
        setattr(self._backend,name,value)

    def generate(self,prompt,request,**kwargs):
        # The request and following synchronization each have independent
        # continuous bounds; leave a further ten seconds for normal cleanup.
        remaining_window(self._plan,request.timeout_seconds+getattr(self._backend,'startup_timeout',120.)+10.)
        budget_deadline=getattr(self,'_budget_deadline',None)
        if budget_deadline is not None and continuous_ns()+int((request.timeout_seconds+getattr(self._backend,'startup_timeout',120.)+10.)*1e9)>budget_deadline:
            raise TimeoutError('frozen continuous native study compute budget exhausted')
        if self._admission is not None:
            self._admission()
        return self._backend.generate(prompt,request,**kwargs)


class ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname in DENIED_MODULES:
            raise ImportError('privileged module denied in recovery serving')


def isolation(root,group):
    plan = verify(root,group=group)
    if boot_identity()!=plan['freeze']['boot_id'] or clock_identity()!=plan['freeze']['clock']:
        raise ValueError('recovery boot/clock domain mismatch')
    expected = Path(root)/'source/src/outcome_poc'
    for name,module in list(sys.modules.items()):
        if name in DENIED_MODULES:
            raise RuntimeError('privileged module already loaded in serving')
        if name.startswith('outcome_poc') and getattr(module,'__file__',None):
            if not Path(module.__file__).resolve().is_relative_to(expected):
                raise RuntimeError(f'non-snapshot serving import: {name}')
    sys.meta_path.insert(0,ImportGuard())
    paths = list(plan['denied_probes'])
    if group=='natural':
        paths.append(str(Path(root)/'support-view.json'))
    return plan,probe_denials(paths)


@dataclass(frozen=True)
class IsolatedFactory:
    factory: object
    root: Path
    group: str
    state_path: Path

    def __call__(self):
        import psutil
        plan,probes = isolation(self.root,self.group)
        state = read(self.state_path)
        if os.getppid()!=state['parent_pid']:
            raise RuntimeError('recovery parent disappeared before acquisition')
        publish(self.state_path.parent/f"session-worker-{state['session']}-{os.getpid()}.json",
            {'session':state['session'],'plan_hash':plan['plan_hash'],'boot_id':boot_identity(),
             'pid':os.getpid(),'created':psutil.Process().create_time(),'continuous_ns':continuous_ns(),
             'clock':clock_identity(),'probes':probes})
        return self.factory()


def forecast_prompts(roster,tasks,documents,retrieval,tokenizer,max_context,max_new):
    forecasts = {}
    for job in roster:
        task = tasks[job['task_id']]
        ranking = retrieval.rank(task['question'],task['candidate_ids'])
        aliases = ranking_aliases(ranking)
        budget = job.get('budget',len(ranking))
        if type(budget) is not int or not 0 < budget <= len(ranking):
            raise ValueError('forecast budget outside available packet')
        evidence = [documents.get(r.doc_id) for r in ranking[:budget]]
        view = {d.doc_id:list(range(len(d.sentences))) for d in evidence}
        prompt = render_condition(task['question'],evidence,aliases,tokenizer,view,job['reader_condition'])
        tokens = len(tokenizer.encode(prompt,add_special_tokens=False))
        if tokens+max_new>max_context:
            raise ValueError('frozen prompt plus output exceeds caller cap; no assigned generation admitted')
        forecasts[job['job_id']] = {'prompt_tokens':tokens,'prompt_hash':prompt_identity(prompt,tokenizer)}
    return {'jobs':forecasts,'maximum_input_tokens':max(v['prompt_tokens'] for v in forecasts.values()),
            'max_context_tokens':max_context,'max_new_tokens':max_new,'assigned_generations_so_far':0}


def execute(root,plan,job,task,documents,retrieval,backend,session, *, clock=continuous_ns,admission=None):
    from .study_v3 import is_scientific
    if is_scientific(plan['config']) or is_action(plan['config']) or is_learning(plan['config']):
        from .allocation_study import execute as allocation_execute
        return allocation_execute(root,plan,job,task,documents,retrieval,backend,session,clock=clock,admission=admission)
    request_start,active_start = clock(),time.perf_counter_ns()
    if job not in jobs(root,job['group']) or task['task_id']!=job['task_id']:
        raise ValueError('unassigned recovery job')
    directory = Path(root)/'jobs'/job['job_id']
    directory.mkdir(parents=True,exist_ok=False)
    state = {'job_hash':content_hash(job),'plan_hash':plan['plan_hash'],'boot_id':boot_identity(),
             'start_ns':request_start,'active_start_ns':active_start,'session':session}
    publish(directory/'started.json',state)
    append_jsonl(directory/'attempts.jsonl',{'kind':'start',**state})
    ranking,aliases,evidence,view = [],{},[],{}
    calls,prompt_hash,fatal,result = 0,None,None,None
    try:
        if admission is not None:
            admission()
        backend.synchronize()
        ranking = retrieval.rank(task['question'],task['candidate_ids'])
        if len(ranking)!=10 or {r.doc_id for r in ranking}!=set(task['candidate_ids']):
            raise ValueError('ranking does not cover complete assigned packet')
        publish(Path(root)/'ranking-identities'/f"{content_hash(task['task_id'])}.json",
                {'task_id':task['task_id'],'ranking':[asdict(r) for r in ranking]})
        aliases = ranking_aliases(ranking)
        if job['group']=='natural':
            chosen = [r.doc_id for r in ranking[:(job['budget'] if 'budget' in job else int(job['arm']))]]
        else:
            projected = read(Path(root)/'support-view.json')[task['task_id']]
            chosen = [r.doc_id for r in ranking if r.doc_id in projected]
        evidence = [documents.get(d) for d in chosen]
        view = {d.doc_id:(projected[d.doc_id] if job['arm']=='support-sentences' else list(range(len(d.sentences)))) for d in evidence}
        prompt = render_condition(task['question'],evidence,aliases,backend.tokenizer,view,job.get('reader_condition','baseline'))
        prompt_hash = prompt_identity(prompt,backend.tokenizer)
        if plan['config']['protocol_id']=='reader-evidence-first-v1':
            expected = read(Path(root)/'stages/natural/render-forecast.json')['jobs'][job['job_id']]
            if expected['prompt_hash']!=prompt_hash:
                raise ValueError('paid prompt differs from frozen forecast')
        asset = read(Path(root)/'assets.json')['assets']['reader']
        settings = plan['config']['reader']
        request = GenerationRequest(asset['revision'],asset['snapshot_hash'],prompt_hash,
            content_hash({'greedy':True,'max_new_tokens':settings['max_new_tokens'],'prefill_step_size':settings['prefill_step_size']}),
            'answer',settings['max_context_tokens'],settings['max_new_tokens'],settings['timeout_seconds'],'none')
        publish(directory/'paid.json',{'request':asdict(request),'prompt':prompt,
                'ranking_hash':content_hash([asdict(r) for r in ranking]),'aliases':aliases,'view':view})
        def progress(text,prompt_ids,token_ids):
            atomic_json(directory/'progress.json',{'raw_output':text,'prompt_token_ids':prompt_ids,'generated_token_ids':token_ids})
        backend.progress_callback = progress
        calls = 1
        try:
            generated = backend.generate(prompt,request,rendered=True)
        except CleanupFailure as error:
            generated = error.result
            fatal = str(error.cleanup_error)
        result = parse_view(generated,evidence,aliases,view)
        if not fatal:
            backend.synchronize()
        if result.status in {'timeout','infra_error','context_overflow'}:
            fatal = fatal or result.status
    except (KeyboardInterrupt,SystemExit):
        raise
    except Exception as error:
        fatal = f'{type(error).__name__}: {error}'
        if result is not None:
            result = replace(result,status='infra_error',stop_reason=fatal)
        else:
            progress = read(directory/'progress.json') if (directory/'progress.json').exists() else {}
            prompt_ids,token_ids = progress.get('prompt_token_ids',[]),progress.get('generated_token_ids',[])
            result = ReaderResult(progress.get('raw_output',''),None,[],'infra_error',len(prompt_ids),len(token_ids),prompt_ids,token_ids,fatal)
    payload = {'result':asdict(result),'calls':calls,'evidence_ids':[d.doc_id for d in evidence],
        'ranking':[asdict(r) for r in ranking],'aliases':aliases,'view':view,'prompt_hash':prompt_hash,'fatal':fatal}
    committed = _commit(root,plan,job,state,payload,clock=clock)
    # Receipt publication is part of a complete durable response. This outer
    # interval includes validation, initial synchronization and both fsyncs.
    # Publishing the measuring record itself is post-response telemetry.
    stop,active_stop = clock(),time.perf_counter_ns()
    publish(Path(root)/'stages'/job['group']/'requests'/f"{job['job_id']}.json",
        {'start_ns':request_start,'stop_ns':stop,'seconds':(stop-request_start)/1e9,
         'active_seconds':(active_stop-active_start)/1e9,'boot_id':state['boot_id'],
         'clock_domain':'mach_continuous_time','receipt':identity(directory/'receipt.json')})
    if fatal:
        raise RuntimeError('recovery assigned failure retained; group incomplete: '+fatal)
    return committed


def run_group(root,group):
    from ..retrieval import EncoderBackend, Retrieval
    root = Path(root).resolve()
    if is_fresh_validation(verify(root,group=group)['config']):
        raise ValueError('fresh v2 is preparation-only; scientific execution disabled')
    plan,probes = isolation(root,group)
    from .index_budget import validate_index_budget
    validate_index_budget(root,plan)
    roster = jobs(root,group)
    remaining_window(plan,250.)
    verify_index(root/'index-setup')
    directory = root/'stages'/group
    if directory.exists():
        raise ValueError('group already attempted; preserve it without automatic resume')
    directory.mkdir(parents=True)
    session = uuid.uuid4().hex
    state_path = directory/f'session-start-{session}.json'
    state = {'session':session,'plan_hash':plan['plan_hash'],'boot_id':boot_identity(),'start_ns':continuous_ns(),
             'active_start_ns':time.perf_counter_ns(),'parent_pid':os.getpid(),'reader_worker_expected':True}
    backend,error,cleanup = None,None,None
    monitor = ResourceMonitor(directory/'resources.jsonl')
    with stage_lock(root):
        publish(state_path,state)
        publish(directory/'denials.json',probes)
        monitor.start()
        try:
            with offline_network():
                if not resource_check(monitor.sample())['passed']:
                    raise RuntimeError('pre-acquisition memory reserve failed')
                assets = read(root/'assets.json')['assets']
                encoder = EncoderBackend(Path(assets['encoder']['local_path']))
                if encoder.identity!={k:assets['encoder'][k] for k in ('revision','snapshot_hash')}:
                    raise ValueError('encoder identity mismatch')
                docs = DocumentStore(root/'documents.jsonl')
                retrieval = Retrieval(root/'index-setup/index',docs,encoder)
                factory = IsolatedFactory(NativeReaderFactory(Path(assets['reader']['local_path']),
                    {**plan['config']['reader'],'asset':assets['reader']}),root,group,state_path)
                remaining_window(plan,250.)
                backend = WindowedBackend(ContinuousBackend(factory,clock=continuous_ns),plan)
                if plan['config'].get('schema_version') in (3,4,5):
                    object.__setattr__(backend,'_budget_deadline',state['start_ns']+int(plan['config']['native_budget_seconds']*1e9))
                monitor.backend = backend
                def paid_admission():
                    gate = resource_check(monitor.sample())
                    append_jsonl(directory/'paid-memory-gates.jsonl',{'continuous_ns':continuous_ns(),**gate})
                    if not gate['passed']:
                        raise RuntimeError('resource reserve violated after acquisition; paid generation denied')
                object.__setattr__(backend,'_admission',paid_admission)
                workers = list(directory.glob(f'session-worker-{session}-*.json'))
                if len(workers)!=1:
                    raise RuntimeError('worker domain identity unavailable')
                worker = read(workers[0])
                if not state['start_ns']<=worker['continuous_ns']<=continuous_ns() or worker['clock']!=plan['freeze']['clock']:
                    raise ValueError('parent/worker continuous domains disagree')
                remaining_window(plan,130.)
                warmup(root,plan,backend,directory/'warmup')
                tasks = {t['task_id']:t for t in read_jsonl(root/'tasks.jsonl')}
                validation = is_validation(plan['config']) or is_action(plan['config']) or is_learning(plan['config'])
                if validation:
                    settings = plan['config']['reader']
                    forecast_start = continuous_ns()
                    forecast = forecast_prompts(roster,tasks,docs,retrieval,
                        backend.tokenizer,settings['max_context_tokens'],settings['max_new_tokens'])
                    publish(directory/'render-forecast.json',{**forecast,'start_ns':forecast_start,'stop_ns':continuous_ns(),
                            'boot_id':state['boot_id'],'clock_domain':'mach_continuous_time'})
                for job in roster:
                    def admit():
                        remaining_window(plan,130.)
                        gate = resource_check(monitor.sample())
                        append_jsonl(directory/'memory-gates.jsonl',gate)
                        if not gate['passed']:
                            raise RuntimeError('project memory reserve failed')
                        backend.job_owner = job['job_id']
                    if not validation:
                        admit()
                    execute(root,plan,job,tasks[job['task_id']],docs,retrieval,backend,session,
                            admission=admit if validation else None)
        except BaseException as caught:
            error = caught
        finally:
            if backend is not None:
                try:backend.close()
                except BaseException as caught:
                    cleanup = str(caught)
                    error = error or caught
                for row in backend.lifecycle:
                    append_jsonl(directory/'lifecycle.jsonl',row)
            try:
                if _worker_identity_unknown(directory,state,plan,require_identity=True):
                    raise RuntimeError('worker quiescence unknown')
            except BaseException as caught:
                cleanup = cleanup or str(caught)
                error = error or caught
            monitor.stop()
            stop = continuous_ns()
            publish(directory/f'session-accounting-{session}.json',{'session':session,'plan_hash':plan['plan_hash'],
                'boot_id':state['boot_id'],'start_identity':identity(state_path),'start_ns':state['start_ns'],
                'stop_ns':None if cleanup else stop,'stop_lower_bound_ns':stop,'stop_upper_bound_ns':None if cleanup else stop,
                'timing_status':'interrupted_stop_unknown' if cleanup else 'exact','cleanup_error':cleanup,
                'error':str(error) if error else None,'active_stop_ns':time.perf_counter_ns()})
    if error:
        raise error
    from ..reader_probe.study import inventory
    for job in roster:
        if completion(root,plan,job) is None:
            raise ValueError('incomplete assigned group')
    publish(directory/'closed.json',{'plan_hash':plan['plan_hash'],'assigned_jobs':len(roster),
        'job_ids_hash':content_hash([j['job_id'] for j in roster]),'session_accounting':session_accounting(root,group,plan,require_closed=True),
        'jobs':{j['job_id']:inventory(root/'jobs'/j['job_id']) for j in roster},'stage_files':inventory(directory)})
    return {'status':'closed','assigned_jobs':len(roster)}


def launch(root,group):
    root = Path(root).resolve()
    if is_fresh_validation(verify(root)['config']):
        raise ValueError('fresh v2 is preparation-only; scientific execution disabled')
    plan = verify(root)
    from .index_budget import validate_index_budget
    validate_index_budget(root,plan)
    remaining_window(plan,250.)
    if group not in group_arms(plan['config']):
        raise ValueError('group is not assigned by this protocol')
    if group=='oracle' and not (root/'stages/natural/closed.json').is_file():
        raise ValueError('natural assignment must close before Gold-assisted diagnosis')
    if group=='natural' and (root/'stages/oracle').exists():
        raise ValueError('natural serving cannot follow Gold-assisted outputs')
    denied = list(plan['denied_paths'])
    if group=='natural':denied.append(str(root/'support-view.json'))
    other = 'oracle' if group=='natural' else 'natural'
    denied.append(str(root/'stages'/other))
    denied.extend(str(root/'jobs'/j['job_id']) for j in jobs(root,other))
    path = root/f'{group}.sb'
    text = sandbox_profile(root,denied)
    if path.exists() and path.read_text()!=text:
        raise ValueError('native profile changed')
    if not path.exists():path.write_text(text)
    env = {**os.environ,'PYTHONPATH':str(root/'source/src'),'PYTHONDONTWRITEBYTECODE':'1',
           'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}
    interpreter=plan['config'].get('native_interpreter',sys.executable)
    command = ['/usr/bin/sandbox-exec','-f',str(path),interpreter,'-B','-m','outcome_poc.reader_recovery',
               '_serve','--root',str(root),'--group',group]
    start = continuous_ns()
    if plan['config'].get('schema_version') in (3,4,5):
        from .allocation_study import run_bounded_process
        process=run_bounded_process(command,env,root,plan['config']['native_budget_seconds']+30.,
            binding={'plan_hash':plan['plan_hash'],'group':group,'boot_id':plan['freeze']['boot_id'],'clock':plan['freeze']['clock']})
    else:process = subprocess.run(command,env=env)
    append_jsonl(root/'launches.jsonl',{'group':group,'command':command,'profile':identity(path),
        'start_ns':start,'stop_ns':continuous_ns(),'returncode':process.returncode,'clock_domain':'mach_continuous_time',
        **({'parent_closure':identity(root/'native-parent-closure.json')} if plan['config'].get('schema_version') in (3,4,5) else {})})
    if process.returncode:
        raise RuntimeError(f'native recovery group failed: exit {process.returncode}')
    return {'status':'native group exited','group':group}

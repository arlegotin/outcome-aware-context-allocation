"""NEW serving-only bridge: recovery isolation, actual allocation runner, receipts."""
from dataclasses import asdict,replace
from pathlib import Path
import time

from ..allocation_authorization import FrozenStage
from ..continuous_serving import make_runtime
from ..data_runtime import Task
from ..generation import Reader,render_prompt,prompt_identity,ranking_aliases
from ..policies import FixedPolicy
from ..runner import execute_job,close_run,_read,accounting
from ..schemas import ReaderResult
from ..storage import append_jsonl,content_hash
from ..followup.clock import continuous_ns,boot_identity
from ..followup.runtime import _commit
from .study import jobs,read,publish,identity


class ObservedRetrieval:
    def __init__(self,retrieval):self.retrieval,self.ranking=retrieval,None
    def rank(self,*args):
        self.ranking=self.retrieval.rank(*args)
        return self.ranking


def execute(root,plan,job,task,documents,retrieval,backend,session,*,clock=continuous_ns,admission=None):
    start,active=clock(),time.perf_counter_ns()
    if job not in jobs(root,job['group']) or task['task_id']!=job['task_id'] or task['split']!='fit_extension':
        raise ValueError('scientific allocation exact assignment/split mismatch')
    root=Path(root);directory=root/'jobs'/job['job_id'];directory.mkdir(parents=True,exist_ok=False)
    state={'job_hash':content_hash(job),'plan_hash':plan['plan_hash'],'boot_id':boot_identity(),
           'start_ns':start,'active_start_ns':active,'session':session}
    publish(directory/'started.json',state);append_jsonl(directory/'attempts.jsonl',{'kind':'start',**state})
    if admission is not None:admission()
    asset=read(root/'assets.json')['assets']['reader'];reader=plan['config']['reader']
    recipe=job['reader_condition']+'-v1'
    settings={'model_revision':asset['revision'],'model_hash':asset['snapshot_hash'],
              'decoding_hash':content_hash({'greedy':True,'max_new_tokens':reader['max_new_tokens'],'prefill_step_size':reader['prefill_step_size']}),
              **{k:reader[k] for k in ('max_context_tokens','max_new_tokens','timeout_seconds')},
              'reader_recipe':recipe,'request_timing':plan['config']['request_timing'],
              'request_clock':{'boot_id':plan['freeze']['boot_id'],'clock':plan['freeze']['clock']},
              'source_binding':plan['plan_hash'],'backend':'continuous-supervised-native-mlx-v3'}
    observed=ObservedRetrieval(retrieval)
    runtime=make_runtime(observed,documents,Reader(backend,recipe=recipe),settings)
    inner={'run_id':plan['config']['protocol_id'],'task':Task(**task),'policy':FixedPolicy(job['budget']),
           'job_id':job['job_id'],'protocol_hash':plan['plan_hash'],'stage':job['stage'],
           'mode':'direct','cache_mode':'none','repetition_id':0,'caller_cap':job['budget']}
    runtime._fresh_execution=FrozenStage.bind(plan['plan_hash'],job['stage'],[inner],runtime.config)
    leaf=directory/'allocation'
    prediction=execute_job(inner,runtime,leaf)
    close_run(leaf,[inner])
    ranking=observed.ranking
    if len(ranking)!=10 or {r.doc_id for r in ranking}!=set(task['candidate_ids']):
        raise ValueError('allocation ranking does not preserve the full assigned packet')
    publish(root/'ranking-identities'/f"{content_hash(task['task_id'])}.json",{'task_id':task['task_id'],'ranking':[asdict(r) for r in ranking]})
    aliases=ranking_aliases(ranking);evidence=[documents.get(i) for i in prediction.evidence_ids]
    view={d.doc_id:list(range(len(d.sentences))) for d in evidence}
    prompt=render_prompt(task['question'],evidence,aliases,backend.tokenizer,recipe=recipe)
    if prediction.prompt_hash!=prompt_identity(prompt,backend.tokenizer):raise ValueError('actual allocation paid-prompt identity drift')
    expected=read(root/'stages/natural/render-forecast.json')['jobs'][job['job_id']]
    if prediction.prompt_hash!=expected['prompt_hash']:raise ValueError('actual allocation differs from prospective forecast')
    paid=_read(leaf/'jobs'/job['job_id']/'attempt-1/paid-1.started.json')
    publish(directory/'paid.json',{'request':paid['request'],'prompt':prompt,'aliases':aliases,'view':view,
            'ranking_hash':content_hash([asdict(r) for r in ranking])})
    result=replace(runtime.last_paid_result,answer=prediction.answer,citations=prediction.citations,status=prediction.status)
    payload={'result':asdict(result),'calls':prediction.generation_calls,'evidence_ids':prediction.evidence_ids,
             'ranking':[asdict(r) for r in ranking],'aliases':aliases,'view':view,'prompt_hash':prediction.prompt_hash,
             'fatal':None,'actual_allocation_runner':True,'recipe':recipe,
             'core_complete_seconds':accounting(leaf,prediction)['total_serving_seconds']}
    committed=_commit(root,plan,job,state,payload,clock=clock)
    stop=clock()
    publish(root/'stages'/job['group']/'requests'/f"{job['job_id']}.json",{'start_ns':start,'stop_ns':stop,'seconds':(stop-start)/1e9,
            'active_seconds':(time.perf_counter_ns()-active)/1e9,'boot_id':state['boot_id'],'clock_domain':'mach_continuous_time',
            'receipt':identity(directory/'receipt.json')})
    if result.status in {'timeout','infra_error','context_overflow'}:
        raise RuntimeError('assigned allocation failure retained; fixed study incomplete: '+result.status)
    return committed


def run_bounded_process(command,env,root,seconds,*,clock=continuous_ns,binding=None):
    """Own a new group; coordinator exit is never proof of child quiescence."""
    import os,signal,subprocess,psutil
    launched=time.time()
    process=subprocess.Popen(command,env=env,cwd=root,start_new_session=True)
    group=process.pid;deadline=clock()+int(seconds*1e9)
    def members():
        found=[]
        for candidate in psutil.process_iter(['pid','create_time','status']):
            try:
                if os.getpgid(candidate.pid)==group and candidate.info['status']!=psutil.STATUS_ZOMBIE:
                    if candidate.info['create_time']<launched-1.:raise RuntimeError('native process group ownership unknown')
                    found.append(candidate.pid)
            except (ProcessLookupError,psutil.NoSuchProcess):pass
        return found
    reason=None
    try:
        while process.poll() is None:
            if clock()>=deadline:
                reason='continuous native stage deadline exhausted';break
            time.sleep(.05)
        if reason is None and members():reason='lingering native child after coordinator exit'
    except BaseException as error:
        reason=f'parent interrupted: {type(error).__name__}: {error}'
    if reason is not None:
        cleanup_error=None
        try:
            for sig,grace in ((signal.SIGTERM,2.),(signal.SIGKILL,2.)):
                if not members():break
                os.killpg(group,sig)
                end=clock()+int(grace*1e9)
                while members() and clock()<end:
                    process.poll();time.sleep(.05)
            quiescent=not members()
        except BaseException as error:
            quiescent=False;cleanup_error=f'{type(error).__name__}: {error}'
        process.poll()
        publish(Path(root)/'native-stage-timeout.json',{'status':'incomplete','reason':reason,
                'continuous_deadline_ns':deadline,'stop_lower_bound_ns':clock(),'returncode':process.returncode,
                'group_quiescent':quiescent,'cleanup_error':cleanup_error,'complete_assignment_scoring_allowed':False})
        if not quiescent:raise RuntimeError('native group cleanup unknown: '+str(cleanup_error))
        if 'deadline' in reason:raise TimeoutError(reason+'; all evidence retained')
        raise RuntimeError(reason+'; owned group cleaned; assignment remains incomplete')
    attestation={**(binding or {}),'command_hash':content_hash(command),'process_group':group,'returncode':process.returncode,
            'group_quiescent':True,'stop_ns':clock(),'complete_assignment_scoring_allowed':process.returncode==0}
    if binding and process.returncode==0:
        attestation['stage_closure']=identity(Path(root)/'stages'/binding['group']/'closed.json')
    publish(Path(root)/'native-parent-closure.json',attestation)
    return process


def validate_parent(root,plan):
    root=Path(root);value=read(root/'native-parent-closure.json')
    from ..storage import read_jsonl
    launches=list(read_jsonl(root/'launches.jsonl'))
    if len(launches)!=1:raise ValueError('scientific study requires exactly one closed native launch')
    launch=launches[0]
    if (value.get('plan_hash')!=plan['plan_hash'] or value.get('group')!='natural' or
            value.get('boot_id')!=plan['freeze']['boot_id'] or value.get('clock')!=plan['freeze']['clock'] or
            value.get('group_quiescent') is not True or value.get('complete_assignment_scoring_allowed') is not True or
            value.get('returncode')!=0 or value.get('command_hash')!=content_hash(launch['command']) or
            launch.get('group')!='natural' or launch.get('returncode')!=0 or
            launch.get('parent_closure')!=identity(root/'native-parent-closure.json') or
            not launch['start_ns']<=value['stop_ns']<=launch['stop_ns'] or
            value.get('stage_closure')!=identity(root/'stages/natural/closed.json')):
        raise ValueError('native parent/owned-group closure binding mismatch')
    if plan['config'].get('schema_version') in (4,5):
        envelope=(launch['stop_ns']-launch['start_ns'])/1e9
        resident=read(root/'stages/natural/closed.json')['session_accounting']['exact_seconds']
        if not 0<=resident<=envelope<=plan['config']['native_budget_seconds']:
            raise ValueError('registered complete native envelope cap exceeded')
    return value

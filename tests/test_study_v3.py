"""NEW v3 science path over the actual durable allocation runner; invented text."""
from dataclasses import asdict
from pathlib import Path
import json,shutil
from types import SimpleNamespace
import pytest


def config(n=2):
    from outcome_poc.reader_recovery.study import READER
    return dict(schema_version=3,study_kind='allocation-reader-admission-v3',protocol_id='authored-native-v3',
                purpose='authored-native-smoke',execution_mode='frozen-native',reader=READER,validation_n=n,
                seed=7,arms=['baseline','evidence-first'],repetitions=1,cache_mode='none',semantic_retries=0,
                reuse_indexes=[],request_timing='complete-continuous-v3',native_generation_budget_calls=2*n+1,native_budget_seconds=600)


def test_v3_has_explicit_independent_schedule_and_does_not_unlock_v2():
    from outcome_poc.reader_recovery.study import group_arms,make_schedule,is_fresh_validation
    cfg=config();cohorts={'validation':['authored-a','authored-b']}
    schedule=make_schedule(cfg,cohorts)
    assert len(schedule)==4 and [j['arm'] for j in schedule[::2]]==['baseline','evidence-first']
    assert group_arms(cfg)=={'natural':('baseline','evidence-first')} and not is_fresh_validation(cfg)
    for changed in ({**cfg,'protocol_id':'reader-recovery-v1'},{**cfg,'study_kind':'renamed'},
                    {**cfg,'native_generation_budget_calls':99}):
        with pytest.raises(ValueError):make_schedule(changed,cohorts)
    with pytest.raises(ValueError):make_schedule(cfg,{'validation':['authored-a']})


def test_actual_allocation_runner_closes_v3_paid_jobs_before_scoring(tmp_path,monkeypatch):
    actual_bridge_fixture(tmp_path,monkeypatch,config(),'validation')


def actual_bridge_fixture(tmp_path,monkeypatch,cfg,cohort_name):
    from outcome_poc.reader_recovery import runtime,scoring,allocation_study
    from outcome_poc import continuous_serving
    from outcome_poc.reader_recovery.study import make_schedule,verify
    from outcome_poc.reader_recovery.prompts import registry
    from outcome_poc.followup.study import publish,identity,build_new_index
    from outcome_poc.reader_probe.study import inventory
    from outcome_poc.followup.runtime import session_accounting
    from outcome_poc.storage import canonical_bytes,content_hash,append_jsonl
    from outcome_poc.retrieval import Retrieval
    from retrieval_helpers import document,store,Encoder
    from followup_helpers import Backend
    import outcome_poc
    root=tmp_path/'run';root.mkdir()
    docs=[document(f'Authored {i}',['Iris is violet.']) for i in range(10)];documents=store(root,docs)
    tasks=[dict(task_id=i,split='fit_extension',question='Which colour?',candidate_ids=[d.doc_id for d in docs]) for i in ('authored-a','authored-b')]
    for task in tasks:append_jsonl(root/'tasks.jsonl',task)
    cohorts={cohort_name:[t['task_id'] for t in tasks],**({'learning_holdout':[]} if cfg.get('schema_version')==5 else {})}
    publish(root/'cohorts.json',{**cohorts,'eligibility_count':100})
    publish(root/'support-view.json',{});publish(root/'assets.json',{'assets':{'reader':{'revision':'authored','snapshot_hash':'authored'}}})
    publish(root/'prompt-conditions.json',registry());publish(root/'schedule.json',make_schedule(cfg,cohorts))
    setup=root/'index-setup';setup.mkdir();start=runtime.continuous_ns();build_new_index(setup,docs,Encoder())
    append_jsonl(root/'setup-attempts.jsonl',{'start_ns':start,'stop_ns':runtime.continuous_ns()})
    retrieval=Retrieval(setup/'index',documents,Encoder());first=retrieval.rank(tasks[0]['question'],tasks[0]['candidate_ids'])[0].doc_id
    gold=tmp_path/'private-gold.jsonl'
    for task in tasks:append_jsonl(gold,dict(task_id=task['task_id'],answer='violet',supporting_facts=[[documents.get(first).title,0]]))
    shutil.copytree(Path(outcome_poc.__file__).parent,root/'source/src/outcome_poc',ignore=shutil.ignore_patterns('__pycache__'))
    domain={'name':'authored-continuous','unit':'nanoseconds'}
    plan={'root':str(root),'config':cfg,'freeze':{'boot_id':'authored','clock':domain},'source_commit':'authored',
          'prompt_conditions':registry(),'gold_input':{'path':str(gold),'identity':identity(gold)},
          'source_snapshot_hash':content_hash(inventory(root/'source')),
          'files':{k:v for k,v in inventory(root).items() if not k.startswith('index-setup/') and k!='setup-attempts.jsonl'}}
    plan['plan_hash']=content_hash(plan);publish(root/'plan.json',plan);verify(root)
    monkeypatch.setattr(runtime,'boot_identity',lambda:'authored');monkeypatch.setattr(allocation_study,'boot_identity',lambda:'authored')
    monkeypatch.setattr(continuous_serving,'boot_identity',lambda:'authored');monkeypatch.setattr(continuous_serving,'clock_identity',lambda:domain)
    class Tokens(type(Backend.tokenizer)):
        def encode(self,text,**kwargs):return [1,2]
    class CoherentBackend(Backend):
        def generate(self,*args,**kwargs):
            callback=self.progress_callback
            self.progress_callback=lambda *args:None
            try:result=super().generate(*args,**kwargs)
            finally:self.progress_callback=callback
            callback(result.raw_output,result.prompt_token_ids,result.generated_token_ids)
            return result
    backend=CoherentBackend();backend.tokenizer=Tokens();backend.clock=continuous_serving.continuous_ns
    stage=root/'stages/natural';stage.mkdir(parents=True);session='authored-session';start=runtime.continuous_ns()
    state_path=stage/f'session-start-{session}.json';publish(state_path,{'session':session,'plan_hash':plan['plan_hash'],'boot_id':'authored','start_ns':start})
    roster=json.loads((root/'schedule.json').read_text());byid={t['task_id']:t for t in tasks}
    forecast_start=runtime.continuous_ns();forecast=runtime.forecast_prompts(roster,byid,documents,retrieval,backend.tokenizer,8192,256)
    publish(stage/'render-forecast.json',{**forecast,'start_ns':forecast_start,'stop_ns':runtime.continuous_ns(),'boot_id':'authored','clock_domain':'mach_continuous_time'})
    for job in roster:runtime.execute(root,plan,job,byid[job['task_id']],documents,retrieval,backend,session)
    assert backend.calls==cfg['native_generation_budget_calls']-1
    with pytest.raises(FileNotFoundError):scoring.score(root)
    assert not (root/'scores').exists()
    stop=runtime.continuous_ns();publish(stage/f'session-accounting-{session}.json',{'session':session,'plan_hash':plan['plan_hash'],'boot_id':'authored',
        'start_identity':identity(state_path),'start_ns':start,'stop_ns':stop,'stop_lower_bound_ns':stop,'stop_upper_bound_ns':stop,'timing_status':'exact'})
    publish(stage/'closed.json',{'plan_hash':plan['plan_hash'],'assigned_jobs':len(roster),'job_ids_hash':content_hash([j['job_id'] for j in roster]),
        'session_accounting':session_accounting(root,'natural',plan,require_closed=True),
        'jobs':{j['job_id']:inventory(root/'jobs'/j['job_id']) for j in roster},'stage_files':inventory(stage)})
    parent={'plan_hash':plan['plan_hash'],'group':'natural','boot_id':'authored','clock':domain,
            'group_quiescent':True,'returncode':0,'complete_assignment_scoring_allowed':True,
            'command_hash':content_hash(['authored-fixture']),'stop_ns':stop,
            'stage_closure':identity(stage/'closed.json')}
    publish(root/'native-parent-closure.json',parent)
    append_jsonl(root/'launches.jsonl',{'command':['authored-fixture'],'group':'natural','returncode':0,
            'start_ns':start,'stop_ns':stop,'parent_closure':identity(root/'native-parent-closure.json')})
    if cfg.get('schema_version') in (4,5):
        from test_index_budget_v4 import authored_proof
        authored_proof(root,plan)
    summary=scoring.score(root)
    assert summary['assigned_jobs']==cfg['native_generation_budget_calls']-1 and summary['assigned_questions']==2
    assert all(arm['strict_successes']==2 for arm in summary['arms'].values())
    assert all((root/'jobs'/j['job_id']/'allocation/request-timing.json').is_file() for j in roster)
    return summary


def test_native_parent_reaps_entire_owned_group_on_timeout(tmp_path):
    import os,sys,time,signal
    from outcome_poc.reader_recovery.allocation_study import run_bounded_process
    code="""import os,signal,time
pid=os.fork()
if pid==0:
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 while True:time.sleep(.05)
open('child.pid','w').write(str(pid))
while True:time.sleep(.05)
"""
    with pytest.raises(TimeoutError):run_bounded_process([sys.executable,'-c',code],os.environ.copy(),tmp_path,.3)
    marker=json.loads((tmp_path/'native-stage-timeout.json').read_text())
    assert marker['group_quiescent'] and not marker['complete_assignment_scoring_allowed']


def test_native_parent_does_not_accept_lingering_child_as_complete(tmp_path):
    import os,sys
    from outcome_poc.reader_recovery.allocation_study import run_bounded_process
    code="import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])"
    with pytest.raises(RuntimeError,match='lingering'):run_bounded_process([sys.executable,'-c',code],os.environ.copy(),tmp_path,5)
    assert (tmp_path/'native-stage-timeout.json').exists()

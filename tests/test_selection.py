from dataclasses import replace

import pytest

try:
    from outcome_poc import select
except ImportError:
    select = None
from outcome_poc import runner
from outcome_poc.schemas import GoldRecord
from outcome_poc.scoring import Scorer
from serving_helpers import fixture_runtime


def row(identity, family, q=0.5, answer=0.75, seconds=2., ratio=4.):
    return {'config_id':identity,'family':family,'Q':q,'answer_em':answer,
            'mean_time':seconds,'R':ratio,'task_ids':['t1','t2'],'split':'tune'}


def test_common_rule_keeps_quality_losers_and_simple_winner():
    assert select is not None, "common selection module missing"
    anchor=row('FIXED-10','FIXED')
    rows=[anchor,row('gbm','PRE-OUTCOME-GBM',seconds=1.5,ratio=3.),
          row('rf','PRE-RF',seconds=1.,ratio=2.),row('loser','PRE-LINEAR',q=.4,ratio=1.),
          row('answer-loser','POST-OUTCOME',answer=.5,ratio=.5),
          row('shuffle','SHUFFLED-LABEL-GBM',seconds=.1,ratio=.2)]
    result=select.select_configuration(rows,anchor)
    assert result['A*']['config_id']=='gbm'
    assert result['B*']['config_id']=='rf'
    assert not next(r for r in result['configurations'] if r['config_id']=='loser')['eligible']
    assert not next(r for r in result['configurations'] if r['config_id']=='answer-loser')['eligible']
    assert len(result['configurations'])==6
    assert result['families']['POST-OUTCOME']['representative']['config_id']=='answer-loser'
    assert result['families']['POST-OUTCOME']['representative']['eligible'] is False


@pytest.mark.parametrize('family',['PRE-LINEAR','PRE-RF','POST-OUTCOME'])
def test_every_simple_or_post_family_can_win_comparator(family):
    assert select is not None, "common selection module missing"
    anchor=row('FIXED-10','FIXED')
    result=select.select_configuration([anchor,row('gbm','PRE-OUTCOME-GBM'),
                                         row('winner',family,ratio=1.)],anchor)
    assert result['B*']['config_id']=='winner'


def test_ties_zero_success_and_fixed_aliases():
    assert select is not None, "common selection module missing"
    anchor=row('FIXED-10','FIXED')
    rows=[anchor,row('a','PRE-OUTCOME-GBM'),row('z','PRE-RF',q=.75,ratio=4.),
          row('b','PRE-LINEAR',q=.75,seconds=1.5,ratio=4.),
          row('c','QUERY-ONLY',q=.75,seconds=1.5,ratio=4.),
          row('zero','PROXY-LABEL',q=0,ratio=None)]
    result=select.select_configuration(rows,anchor)
    assert result['B*']['config_id']=='b'
    assert select.configuration_sort_key(rows[-1])[0]==float('inf')


def test_tuning_rejects_protected_or_mismatched_populations():
    assert select is not None, "common selection module missing"
    anchor=row('FIXED-10','FIXED')
    for bad in [{**row('gbm','PRE-OUTCOME-GBM'),'split':'protected'},
                {**row('gbm','PRE-OUTCOME-GBM'),'task_ids':['protected-id']}]:
        with pytest.raises(ValueError): select.select_configuration([anchor,bad],anchor)


def test_metrics_join_assigned_rows_and_all_paid_costs(tmp_path):
    assert select is not None, "common selection module missing"
    runtime,job,_=fixture_runtime(tmp_path)
    p=runner.execute_job(job,runtime,tmp_path)
    score=Scorer().score(p,GoldRecord('task','blue',[('Lamp 0',0)]),runtime.documents,run_dir=tmp_path)
    result=select.configuration_metrics([p],[score],runner.load_events(tmp_path))
    assert result['Q']==1. and result['answer_em']==1.
    assert result['mean_time']==11. and result['R']==11.
    failed=replace(score,joint_em=0)
    result=select.configuration_metrics([p],[failed],runner.load_events(tmp_path))
    assert result['R'] is None and result['reason']=='zero_successes'
    with pytest.raises(ValueError): select.configuration_metrics([p],[],[])


def test_pre_endpoints_alias_fixed_and_post_reconstruction_keeps_draft(tmp_path):
    from outcome_poc.policies import PostOutcomePolicy
    runtime,job,clock=fixture_runtime(tmp_path)
    small=runner.execute_job(job,runtime,tmp_path/'small')
    small_events=runner.load_events(tmp_path/'small')
    class RoutingPost(PostOutcomePolicy):
        def choose(self,*args,**kwargs):
            clock.advance(4)
            return super().choose(*args,**kwargs)
    post=runner.execute_job({**job,'policy':RoutingPost(None,{'threshold_mode':'always_ten','threshold':None})},runtime,tmp_path/'post')
    post_events=runner.load_events(tmp_path/'post')
    assert select.reconstructed_seconds('PRE-OUTCOME-GBM','always_ten',post.elapsed_seconds,post_events,4.)==post.elapsed_seconds
    assert select.reconstructed_seconds('POST-OUTCOME','numeric',post.elapsed_seconds,post_events,2.)==23.
    assert select.reconstructed_seconds('POST-OUTCOME','numeric',small.elapsed_seconds,small_events,2.)==13.


def test_tune_collects_every_budget_paid_post_and_judge_without_gold(tmp_path):
    from outcome_poc.schemas import Task
    runtime,job,_=fixture_runtime(tmp_path)
    task=replace(job['task'],split='tune')
    result=select.tune({'tasks':[task],'assigned_ids':['task'],'run_dir':str(tmp_path/'tune'),
                        'models':{},'test_fixture':True},runtime)
    assert result['assigned_jobs']==12
    assert result['generation_calls']==14
    assert result['all_k']==list(range(1,11))
    assert (tmp_path/'tune/predictions.closed.json').exists()
    assert not (tmp_path/'tune/scores.jsonl').exists()
    for split in ['fit','protected']:
        with pytest.raises(ValueError):
            select.tune({'tasks':[replace(task,split=split)],'assigned_ids':['task'],
                         'run_dir':str(tmp_path/'bad'),'models':{}},runtime)


def test_closed_tuning_analysis_keeps_paid_post_and_all_family_rows(tmp_path):
    import json
    from types import SimpleNamespace
    from outcome_poc.scoring import main as score_main
    from outcome_poc.storage import append_jsonl, atomic_json
    from outcome_poc.schemas import Document, RankedDocument
    from outcome_poc.policies import ThresholdPolicy, PostOutcomePolicy, AdaptiveKPolicy
    from retrieval_helpers import document
    runtime,job,_=fixture_runtime(tmp_path)
    task=replace(job['task'],split='tune')
    # Observable empty-model acquisition still exercises real durable serving and scoring.
    root=tmp_path/'run'
    select.tune({'tasks':[task],'assigned_ids':['task'],'run_dir':str(root),'models':{}},runtime)
    docs=[runtime.documents.get(i) for i in task.candidate_ids]
    documents=tmp_path/'documents.jsonl'
    for doc in docs: append_jsonl(documents,doc)
    gold=tmp_path/'gold.jsonl';append_jsonl(gold,GoldRecord('task','blue',[('Lamp 0',0)]))
    score_main(SimpleNamespace(predictions=str(root/'predictions.jsonl'),gold=str(gold),
                              documents=str(documents),output=str(root/'scores.jsonl'),run_dir=str(root)))
    # Inject a real learned policy through an independently declared config/routing receipt.
    schedule=json.loads((root/'schedule.json').read_text())
    schedule['configurations'].append({'config_id':'gbm:endpoint','family':'PRE-OUTCOME-GBM',
                                      'model_name':'PRE-OUTCOME-GBM','threshold_mode':'always_ten','threshold':None})
    atomic_json(root/'schedule.json',schedule)
    source=next(j for j in schedule['jobs'] if j['arm']=='k=10')
    from outcome_poc.schemas import CostEvent
    for identity,role,start,stop in [('test-route','routing',0,20_000_000),('test-payload','payload',20_000_000,30_000_000)]:
        append_jsonl(root/'routing-events.jsonl',CostEvent(identity,'run','task','PRE-OUTCOME-GBM',role,start,stop,(stop-start)/1e9,0,0,'none',None,None,None,None,1,'ok'))
    append_jsonl(root/'routes.jsonl',{'config_id':'gbm:endpoint','task_id':'task','decision':{'action_k':10},
        'source_prediction_id':source['job_id'],'routing_seconds':.02,'payload_seconds':.01,'event_ids':['test-route','test-payload']})
    closure=json.loads((root/'tuning-acquisition.closed.json').read_text())
    from outcome_poc.runner import _digest
    closure['hashes'].update({n:_digest(root/n) for n in ['schedule.json','routes.jsonl','routing-events.jsonl']})
    atomic_json(root/'tuning-acquisition.closed.json',closure)
    result=select.analyze_tuning(root,['task'],require_roster=False)
    assert result['A*']['Q']==1.
    assert result['A*']['mean_time']==next(r['mean_time'] for r in result['configurations'] if r['config_id']=='FIXED-10')
    assert len([r for r in result['configurations'] if r['family']=='FIXED'])==10
    assert result['families']['LLM-SUFFICIENCY']['config_count']==1
    assert result['published_adaptive_k']['config_id']=='ADAPTIVE-k-published-B5'


def test_native_profile_denies_all_scorer_projection_suffixes(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    profile_builder=getattr(select,'native_sandbox_profile',None)
    assert callable(profile_builder), 'sandbox profile requires an executable projection denial contract'
    if sys.platform!='darwin': pytest.skip('macOS sandbox-exec contract')
    gold=tmp_path/'example.gold.jsonl';gold.write_text('fixture')
    other=tmp_path/'example.gold.jsonl.other';other.write_text('fixture')
    profile=tmp_path/'test.sb';profile.write_text(profile_builder(tmp_path,tmp_path/'prepared'))
    probe="import json,sys\nr=[]\nfor p in sys.argv[1:]:\n try: open(p).read()\n except PermissionError:r.append('denied')\n else:r.append('allowed')\nprint(json.dumps(r))"
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),sys.executable,'-c',probe,str(gold),str(other)],capture_output=True,text=True)
    if 'sandbox_init: Operation not permitted' in result.stderr:
        pytest.skip('outer sandbox disallows nested sandbox; run this test with authorized escalation')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==['denied','allowed']

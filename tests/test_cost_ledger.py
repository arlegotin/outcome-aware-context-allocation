from dataclasses import replace

import pytest

from outcome_poc import runner
from outcome_poc.schemas import Decision, PaidDraft
from serving_helpers import fixture_runtime


def test_warm_boundary_charges_each_component_and_payload_once(tmp_path):
    runtime, job, clock = fixture_runtime(tmp_path)
    prediction = runner.execute_job(job, runtime, tmp_path)
    assert prediction.elapsed_seconds == 11.  # retrieval 2 + evidence 1 + generation 5 + payload 3
    events = runner.load_events(tmp_path)
    assert sum(e.elapsed_seconds for e in events if e.role != 'serving') == 11.
    assert [e.elapsed_seconds for e in events if e.role == 'generation:answer'] == [5.]
    assert all(e.peak_mlx_bytes is None for e in events)
    assert len([e for e in events if e.role == 'retrieval']) == 1
    assert len([e for e in events if e.role == 'telemetry']) == 1


def test_post_answer_two_paid_calls_retrieve_once(tmp_path):
    runtime, job, clock = fixture_runtime(tmp_path)
    class Post:
        policy_id = 'POST-OUTCOME'
        requires_draft = True
        def choose(self, question, ranking, paid_draft=None, *, caller_cap=10):
            assert isinstance(paid_draft, PaidDraft)
            clock.advance(4)
            return Decision('POST-OUTCOME',10,1.,'numeric',0.,'threshold','f',10,10)
    job['policy'] = Post()
    prediction = runner.execute_job(job,runtime,tmp_path)
    assert prediction.generation_calls == 2
    assert prediction.elapsed_seconds == 25.  # 2 + draft evidence1 + 5 + route4 + full evidence5 + 5 + payload3
    events = runner.load_events(tmp_path)
    assert len([e for e in events if e.role == 'retrieval']) == 1
    assert [e.role for e in events if e.role.startswith('generation:')] == ['generation:draft','generation:answer']


def test_direct_refuses_replay_and_repetitions_execute_fresh(tmp_path):
    runtime, job, _ = fixture_runtime(tmp_path)
    runner.execute_job(job,runtime,tmp_path)
    second = {**job,'job_id':'second','repetition_id':1}
    runner.execute_job(second,runtime,tmp_path)
    assert runtime.reader.backend.calls == 2
    with pytest.raises(ValueError,match='direct'):
        runner.serve(job['task'],job['policy'],runtime,{**job,'cache_mode':'development_replay'})


def test_replay_retains_source_costs(tmp_path):
    runtime, job, _ = fixture_runtime(tmp_path)
    source = runner.execute_job(job,runtime,tmp_path / 'source')
    source_events = runner.load_events(tmp_path / 'source')
    replay = {**job,'job_id':'replayed','mode':'replay','cache_mode':'development_replay',
              'replay_prediction':source,'replay_events':source_events,
              'replay_signature':runtime.decision_payload['action_signature']}
    result = runner.execute_job(replay,runtime,tmp_path / 'replay')
    assert result.elapsed_seconds == 11.
    assert runtime.reader.backend.calls == 1
    events = runner.load_events(tmp_path / 'replay')
    assert all(e.source_event_id for e in events if e.role != 'telemetry')
    assert [e.elapsed_seconds for e in events if e.role == 'generation:answer'] == [5.]


def test_identity_binds_prompt_backend_cache_and_repetitions(tmp_path):
    runtime, job, _ = fixture_runtime(tmp_path)
    task, config = job['task'],runtime.config
    sig = runner.action_signature(task,config,task.candidate_ids[:2],'answer','none')
    for changes in [{'prompt_version':'v2'},{'backend':'other'},{'model_hash':'other'}]:
        assert runner.action_signature(task,{**config,**changes},task.candidate_ids[:2],'answer','none') != sig
    assert runner.action_signature(task,config,task.candidate_ids[:2],'answer','development_replay') != sig
    assert runner.job_id(sig,'direct',0) != runner.job_id(sig,'direct',1)


def test_exhausted_core_cannot_generate_but_named_context_zero_can(tmp_path):
    runtime, job, _ = fixture_runtime(tmp_path)
    result = runner.execute_job({**job,'caller_cap':0},runtime,tmp_path / 'exhausted')
    assert result.status == 'budget_exhausted' and result.generation_calls == 0
    class Zero:
        policy_id = 'NO-CONTEXT-DIAGNOSTIC'
        def choose(self,*args,**kwargs):
            return Decision(self.policy_id,0,None,None,None,'diagnostic','f',0,0)
    result = runner.execute_job({**job,'policy':Zero(),'allow_no_context_diagnostic':True},runtime,tmp_path / 'zero')
    assert result.generation_calls == 1 and result.evidence_ids == []
    with pytest.raises(ValueError, match='opt'):
        runner.serve(job['task'],Zero(),runtime,job)


def test_prompt_routing_parse_and_ledger_overhead_are_measured_separately(tmp_path,monkeypatch):
    from outcome_poc.generation import Reader
    from outcome_poc.policies import FixedPolicy
    runtime,job,clock=fixture_runtime(tmp_path)
    original_template=runtime.reader.backend.tokenizer.apply_chat_template
    def template(*args,**kwargs):
        clock.advance(1)
        return original_template(*args,**kwargs)
    runtime.reader.backend.tokenizer.apply_chat_template=template
    original_parse=Reader.parse_generated
    def parse(*args):
        clock.advance(2)
        return original_parse(*args)
    monkeypatch.setattr(Reader,'parse_generated',staticmethod(parse))
    class Routing(FixedPolicy):
        def choose(self,*args,**kwargs):
            clock.advance(4)
            return super().choose(*args,**kwargs)
    job['policy']=Routing(2)
    original_append=runner.append_jsonl
    def append(path,value):
        if path.name == 'events.jsonl': clock.advance(.25)
        return original_append(path,value)
    monkeypatch.setattr(runner,'append_jsonl',append)
    result=runner.execute_job(job,runtime,tmp_path)
    assert result.elapsed_seconds == 18.  # original11 + prompt1 + parse2 + routing4
    events=runner.load_events(tmp_path)
    assert [e.elapsed_seconds for e in events if e.role == 'telemetry'] == [2.]  # eight events appended
    assert runner.accounting(tmp_path,result) == {'total_serving_seconds':18.,'total_experiment_seconds':20.}


def test_same_job_cannot_skip_after_config_or_question_change(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    runner.execute_job(job,runtime,tmp_path)
    runtime.config={**runtime.config,'prompt_version':'v2'}
    with pytest.raises(ValueError,match='identity'):
        runner.execute_job(job,runtime,tmp_path)


def test_score_joins_all_attempts_without_diagnostic_fallback(tmp_path):
    from outcome_poc.scoring import Scorer
    from outcome_poc.schemas import GoldRecord
    runtime,job,_=fixture_runtime(tmp_path,['INFRA','{"answer":"blue","citations":[{"doc_id":"D0","sentence_index":0}]}'])
    runner.execute_job(job,runtime,tmp_path)
    result=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    gold=GoldRecord('task','blue',[('Lamp 0',0)])
    scored=Scorer().score(result,gold,runtime.documents,run_dir=tmp_path)
    assert scored.joint_em == 1
    assert scored.total_serving_seconds == 22. and scored.total_experiment_seconds == 22.
    assert result.elapsed_seconds == 11.


def test_identical_actions_in_distinct_direct_arms_never_skip_each_other(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    sig=runner.action_signature(job['task'],runtime.config,job['task'].candidate_ids[:2],'answer','none')
    a={**job,'arm':'A*','job_id':runner.job_id(sig,'direct:A*',0)}
    b={**job,'arm':'B*','job_id':runner.job_id(sig,'direct:B*',0)}
    assert a['job_id'] != b['job_id']
    runner.execute_job(a,runtime,tmp_path)
    runner.execute_job(b,runtime,tmp_path)
    assert runtime.reader.backend.calls==2
    assert runner.close_run(tmp_path,[a,b])['record_count']==2


def test_shared_setup_and_offline_costs_join_experiment_once(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    a=runner.execute_job(job,runtime,tmp_path)
    b=runner.execute_job({**job,'job_id':'second'},runtime,tmp_path)
    runner.record_shared_cost(tmp_path,'cold_setup',0,9_000_000_000,['job','second'])
    runner.record_shared_cost(tmp_path,'offline',10_000_000_000,14_000_000_000,['job','second'],source_id='index-attempt')
    assert runner.accounting(tmp_path,a)=={'total_serving_seconds':11.,'total_experiment_seconds':17.5}
    assert runner.accounting(tmp_path,b)=={'total_serving_seconds':11.,'total_experiment_seconds':17.5}
    runner.close_run(tmp_path,[job,{**job,'job_id':'second'}])


@pytest.mark.parametrize('decision',[
    Decision('FIXED-2',2,None,None,None,'fixed','f',2,10),
    Decision('FIXED-2',2,None,None,None,'fixed','f',2,0),
])
def test_invalid_effective_decision_cannot_bypass_budget_or_call_reader(tmp_path,decision):
    runtime,job,_=fixture_runtime(tmp_path)
    class Broken:
        policy_id='FIXED-2'
        def choose(self,*args,**kwargs): return decision
    result=runner.execute_job({**job,'policy':Broken()},runtime,tmp_path)
    assert result.status=='infra_error' and result.generation_calls==0


def test_named_zero_schema_does_not_extend_any_other_policy():
    from outcome_poc.schemas import validate_record
    allowed=Decision('NO-CONTEXT-DIAGNOSTIC',0,None,None,None,'diagnostic','f',0,0)
    validate_record(allowed)
    for changes in [{'policy_id':'FIXED-2'},{'policy_id':'no-context-diagnostic'},
                    {'requested_budget':2},{'effective_budget':1},{'threshold_mode':'always_two'},
                    {'predicted_delta':0.}]:
        with pytest.raises(ValueError): validate_record(replace(allowed,**changes))


def test_replay_rejects_original_action_signature_mismatch(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    original=runner.execute_job(job,runtime,tmp_path / 'source')
    events=runner.load_events(tmp_path / 'source')
    replay={**job,'job_id':'replay','mode':'replay','cache_mode':'development_replay',
            'replay_prediction':original,'replay_events':events,'replay_signature':'wrong'}
    with pytest.raises(ValueError,match='signature'):
        runner.execute_job(replay,runtime,tmp_path / 'target')


def test_resume_rejects_changed_installed_template(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    runner.execute_job(job,runtime,tmp_path)
    runtime.reader.backend.tokenizer.chat_template='changed-template'
    with pytest.raises(ValueError,match='identity'):
        runner.execute_job(job,runtime,tmp_path)


def test_closed_snapshot_matches_retry_shared_costs_and_validates_supplement_once(tmp_path,monkeypatch):
    runtime,job,_=fixture_runtime(tmp_path,['INFRA','{"answer":"blue","citations":[{"doc_id":"D0","sentence_index":0}]}'])
    runner.execute_job(job,runtime,tmp_path)
    p=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    second={**job,'job_id':'second'}
    q=runner.execute_job(second,runtime,tmp_path)
    runner.record_shared_cost(tmp_path,'offline',0,4_000_000_000,['job','second'])
    runner.close_run(tmp_path,[job,second])
    expected=[runner.accounting(tmp_path,x) for x in [p,q]]
    calls=[]
    original=runner._supplement_hashes
    def counted(path): calls.append(path);return original(path)
    monkeypatch.setattr(runner,'_supplement_hashes',counted)
    snapshot=runner.validate_closed_accounting(tmp_path,[p,q])
    assert [snapshot.costs(x) for x in [p,q]]==expected
    assert expected==[{'total_serving_seconds':22.,'total_experiment_seconds':24.},
                      {'total_serving_seconds':11.,'total_experiment_seconds':13.}]
    assert len(calls)==1
    with pytest.raises(ValueError): snapshot.costs(replace(p,answer='changed'))


@pytest.mark.parametrize('corruption',['event','completion','shared','extra-job','missing-job','extra-attempt'])
def test_closed_snapshot_rejects_corruption_before_gold(tmp_path,corruption):
    runtime,job,_=fixture_runtime(tmp_path)
    p=runner.execute_job(job,runtime,tmp_path)
    runner.record_shared_cost(tmp_path,'offline',0,1_000_000_000,['job'])
    runner.close_run(tmp_path,[job])
    if corruption=='event': (tmp_path/'jobs/job/attempt-1/events.jsonl').write_text('{}\n')
    if corruption=='completion': (tmp_path/'jobs/job/completion.json').write_text('{}')
    if corruption=='shared': (tmp_path/'shared-costs.jsonl').write_text('{}\n')
    if corruption=='extra-job': (tmp_path/'jobs/extra').mkdir()
    if corruption=='missing-job': (tmp_path/'jobs/job').rename(tmp_path/'jobs/missing')
    if corruption=='extra-attempt': (tmp_path/'jobs/job/attempt-99').mkdir()
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):
        runner.validate_closed_accounting(tmp_path,[p])


def test_snapshot_cannot_accept_files_changed_after_validation(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    p=runner.execute_job(job,runtime,tmp_path)
    runner.close_run(tmp_path,[job])
    snapshot=runner.validate_closed_accounting(tmp_path,[p])
    (tmp_path/'jobs/job/attempt-1/events.jsonl').write_text('{}\n')
    with pytest.raises(ValueError): snapshot.verify_unchanged()


def test_separate_scorer_uses_one_global_validation_and_retains_zero_success(tmp_path,monkeypatch):
    from outcome_poc import scoring
    from outcome_poc.storage import append_jsonl
    from outcome_poc.schemas import GoldRecord
    from types import SimpleNamespace
    runtime,job,_=fixture_runtime(tmp_path,['malformed'])
    p=runner.execute_job(job,runtime,tmp_path)
    second={**job,'job_id':'second'}
    q=runner.execute_job(second,runtime,tmp_path)
    runner.close_run(tmp_path,[job,second])
    gold=tmp_path/'gold.jsonl';append_jsonl(gold,GoldRecord('task','blue',[('Lamp 0',0)]))
    calls=[];original=runner._supplement_hashes
    def counted(path): calls.append(path);return original(path)
    monkeypatch.setattr(runner,'_supplement_hashes',counted)
    monkeypatch.setattr(scoring,'DocumentStore',lambda path:runtime.documents)
    scoring.main(SimpleNamespace(predictions=str(tmp_path/'predictions.jsonl'),gold=str(gold),
        documents='unused',output=str(tmp_path/'scores.jsonl'),run_dir=str(tmp_path)))
    assert len(calls)==1
    scores=list(runner.read_jsonl(tmp_path/'scores.jsonl'))
    assert len(scores)==2 and [s['joint_em'] for s in scores]==[0,0]
    assert [s['total_serving_seconds'] for s in scores]==[11.,11.]


@pytest.mark.parametrize('target',['payload','prior-attempt','supplement','extra-job','missing-job'])
def test_any_closed_ledger_corruption_stops_scorer_before_gold(tmp_path,monkeypatch,target):
    from outcome_poc import scoring
    from types import SimpleNamespace
    runtime,job,_=fixture_runtime(tmp_path,['INFRA','{"answer":"blue","citations":[]}'])
    runner.execute_job(job,runtime,tmp_path)
    p=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    runner.close_run(tmp_path,[job])
    if target=='payload': (tmp_path/'jobs/job/attempt-2/payload.json').write_text('{}')
    if target=='prior-attempt':
        path=tmp_path/'jobs/job/attempt-1/events.jsonl';path.write_bytes(path.read_bytes()+b'\n')
    if target=='supplement': runner.atomic_json(tmp_path/'jobs/job/attempt-1/recovery-pending.json',{'owner':'late'})
    if target=='extra-job': (tmp_path/'jobs/extra').mkdir()
    if target=='missing-job': (tmp_path/'jobs/job').rename(tmp_path/'jobs/missing')
    accessed=[];original=scoring.read_jsonl
    def read(path):
        if path.name=='gold.jsonl': accessed.append(path)
        return original(path)
    monkeypatch.setattr(scoring,'read_jsonl',read)
    with pytest.raises((ValueError,KeyError,FileNotFoundError)):
        scoring.main(SimpleNamespace(predictions=str(tmp_path/'predictions.jsonl'),gold=str(tmp_path/'gold.jsonl'),
            documents='missing',output='missing',run_dir=str(tmp_path)))
    assert accessed==[]

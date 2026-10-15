"""Authored contracts for the one-candidate validation continuation."""
import json
import pytest
from retrieval_helpers import document
from test_reader_recovery import Template


def test_evidence_first_uses_authored_examples_and_same_schema_original_indices():
    from outcome_poc.reader_recovery.prompts import render_condition,registry
    from outcome_poc.generation import render_prompt,parse_answer
    doc = document('Authored original',['Noise.','The badge is violet.'])
    args = ('What colour is the badge?',[doc],{'D8':doc.doc_id},Template(),{doc.doc_id:[0,1]})
    assert render_condition(*args,'baseline')==render_prompt(*args[:4])
    rendered = json.loads(render_condition(*args,'evidence-first'))
    system = rendered[0]['content']
    assert 'Kite' in system and 'Elm Gallery' in system
    assert system.index('"citations"') < system.index('"answer"')
    assert 'D8 | Authored original' in rendered[1]['content'] and '[1] The badge is violet.' in rendered[1]['content']
    parsed = parse_answer('{"citations":[{"doc_id":"D8","sentence_index":1}],"answer":"violet"}',[doc],{'D8':doc.doc_id})
    assert parsed.status=='ok' and parsed.citations==[(doc.doc_id,1)]
    assert set(registry())=={'baseline','evidence-first'}
    with pytest.raises(ValueError):render_condition(*args,'chain')


def test_validation_schedule_pairs_questions_with_balanced_first_condition():
    from outcome_poc.reader_recovery.study import make_schedule
    ids = [f'authored-{i}' for i in range(64)]
    schedule = make_schedule({'protocol_id':'reader-evidence-first-v1','seed':20261015},{'validation':ids})
    assert len(schedule)==128 and len({j['job_id'] for j in schedule})==128
    for offset in range(0,128,16):
        block = schedule[offset:offset+16]
        assert [j['arm'] for j in block[::2]].count('baseline')==4
        for first,second in zip(block[::2],block[1::2]):
            assert first['task_id']==second['task_id'] and first['arm']!=second['arm']
            assert first['group']==second['group']=='natural'
            assert first['reader_condition']==first['arm'] and first['budget']==10
    assert make_schedule({'protocol_id':'reader-evidence-first-v1','seed':20261015},{'validation':ids})==schedule


def test_validation_admission_rejects_identical_and_all_zero_outcomes():
    from outcome_poc.reader_recovery.analysis import validation_admission
    def observations(joint,answer):
        return [dict(task_id=str(i),arm=arm,joint_em=joint,answer_em=answer,status='ok')
                for i in range(64) for arm in ('baseline','evidence-first')]
    for values in (observations(0,0),observations(1,1)):
        gate=validation_admission(values,88459)
        assert gate['admitted'] is False and gate['strict_lower_bound']<0
    with pytest.raises(ValueError):validation_admission(observations(0,0)[:-1],88459)


def test_forecast_uses_real_rendered_conditions_and_rejects_caps_before_generation():
    from types import SimpleNamespace
    from outcome_poc.reader_recovery.runtime import forecast_prompts
    doc = document('Authored badge',['The badge is violet.'])
    class Tokens(Template):
        def encode(self,text,**kwargs):
            assert kwargs=={'add_special_tokens':False}
            return list(text)
    ranking = [SimpleNamespace(doc_id=doc.doc_id)]
    retrieval = SimpleNamespace(rank=lambda *args:ranking)
    documents = SimpleNamespace(get=lambda _:doc)
    tasks = {'a':{'question':'Badge colour?','candidate_ids':[doc.doc_id]}}
    roster = [{'job_id':arm,'task_id':'a','reader_condition':arm} for arm in ('baseline','evidence-first')]
    measured = forecast_prompts(roster,tasks,documents,retrieval,Tokens(),10000,256)
    assert measured['jobs']['evidence-first']['prompt_tokens']>measured['jobs']['baseline']['prompt_tokens']
    with pytest.raises(ValueError,match='cap'):
        forecast_prompts(roster,tasks,documents,retrieval,Tokens(),100,256)


def test_reservation_handoff_uses_only_the_original_untouched_validation_pool():
    from outcome_poc.reader_recovery.validation import validation_cohorts
    prior = {'diagnosis':[f'd{i}' for i in range(32)],'validation_reserved':[f'v{i}' for i in range(64)],
             'evaluation_reserved':[f'f{i}' for i in range(128)],'eligibility_count':88459}
    got = validation_cohorts(prior)
    assert got['validation']==prior['validation_reserved'] and got['evaluation_reserved']==prior['evaluation_reserved']
    assert got['eligibility_count']==88427 and got['prior_diagnosis']==prior['diagnosis']
    prior['evaluation_reserved'][0]=prior['validation_reserved'][0]
    with pytest.raises(ValueError,match='reservation'):
        validation_cohorts(prior)


def test_large_strict_gain_does_not_certify_cost_acceptability():
    from outcome_poc.reader_recovery.analysis import validation_admission
    values=[dict(task_id=str(i),arm=arm,joint_em=int(arm=='evidence-first'),
                 answer_em=int(arm=='evidence-first'),status='ok')
            for i in range(64) for arm in ('baseline','evidence-first')]
    gate=validation_admission(values,88427)
    assert gate['admitted'] and gate['strict_benchmark_quality_improvement']
    assert gate['cost_acceptability'] is None and gate['reader_improvement_claim'] is False


def test_resource_admission_blocks_every_paid_entry_including_warmup():
    from datetime import datetime,timedelta,timezone
    from types import SimpleNamespace
    from outcome_poc.reader_recovery.runtime import WindowedBackend
    class Uncalled:
        startup_timeout=120.
        def generate(self,*args,**kwargs):raise AssertionError('reserve violation reached paid generation')
    def reject():raise RuntimeError('resource reserve violated')
    plan={'config':{'deadline_utc':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}}
    backend=WindowedBackend(Uncalled(),plan,admission=reject)
    with pytest.raises(RuntimeError,match='reserve'):
        backend.generate('authored warmup',SimpleNamespace(timeout_seconds=120))


def test_completed_protocol_registry_preserves_used_and_unexecuted_reservations(tmp_path):
    from outcome_poc.reader_recovery.reservations import preparation_reservations
    from outcome_poc.followup.study import publish,identity
    cohorts=tmp_path/'private-cohorts.json'
    publish(cohorts,{'used':['consumed'],'reserved':['unopened']})
    registry=tmp_path/'experiments/reservation-manifests.json'
    publish(registry,{'format_version':1,'protocols':[{'protocol_id':'completed',
        'status':'complete','cohorts_path':str(cohorts),'cohorts_identity':identity(cohorts),
        'groups':{'used':1,'reserved':1}}]})
    got=preparation_reservations(tmp_path,'genuinely-new-protocol')
    assert got['reserved_ids']=={'consumed','unopened'}
    with pytest.raises(ValueError,match='completed protocol'):
        preparation_reservations(tmp_path,'completed')
    cohorts.write_text('{}')
    with pytest.raises(ValueError,match='reservation'):
        preparation_reservations(tmp_path,'genuinely-new-protocol')


def test_missing_reservation_registry_fails_closed(tmp_path):
    from outcome_poc.reader_recovery.reservations import preparation_reservations
    with pytest.raises(ValueError,match='reservation'):
        preparation_reservations(tmp_path,'new')

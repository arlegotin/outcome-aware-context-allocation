from dataclasses import replace
from pathlib import Path
import json

import pytest

from outcome_poc import runner, scoring, statistics
from outcome_poc.schemas import GoldRecord, ScoredTask
from outcome_poc.storage import append_jsonl, read_jsonl
from test_protected_run import protected_fixture


def closed_fixture(tmp_path, outputs=None):
    frozen, runtime, _ = protected_fixture(tmp_path, outputs)
    assert hasattr(runner, 'run'), 'protected scheduler missing'
    runner.run(frozen, runtime)
    gold = tmp_path/'gold.jsonl'
    for task in runtime.tasks:
        append_jsonl(gold, GoldRecord(task.task_id, 'blue', [('Lamp 0',0)]))
    return frozen, runtime, gold


def test_closed_score_exact_assigned_rows_and_hash_bound_job_mapping(tmp_path):
    frozen, runtime, gold = closed_fixture(tmp_path)
    assert hasattr(scoring, 'score_run'), 'protocol scorer missing'
    rows = scoring.score_run(frozen, Path(frozen['run_dir']), gold, documents_path=runtime.document_path)
    assert len(rows) == 36
    assert {r.job_id for r in rows} == {j['job_id'] for j in frozen['schedule']['jobs']}
    mapping = json.loads((Path(frozen['run_dir'])/'job-evidence.json').read_text())
    assert len(mapping['jobs']) == 36
    assert all(j['attempts'] and j['event_ids'] and j['score_hash'] for j in mapping['jobs'])
    assert mapping['cost_authority'] == 'ScoredTask complete validated accounting; components are nested'
    result = statistics.analyze_run(frozen, rows, runner.load_events(Path(frozen['run_dir'])))
    assert result['assigned_unique_tasks'] == 2
    assert result['primary']['n'] == 2 and result['primary']['repetitions'] == 2
    assert len(result['quality_guards']) == 4
    assert result['primary']['recorded_flags']['timing_stationary'] is None
    assert result['primary']['recorded_flags']['single_dominant'] is None
    assert result['primary']['status'] == 'inconclusive'


def test_score_refuses_missing_receipt_before_any_gold_access(tmp_path, monkeypatch):
    frozen, runtime, gold = closed_fixture(tmp_path)
    assert hasattr(scoring, 'score_run'), 'protocol scorer missing'
    next(Path(frozen['run_dir']).glob('jobs/*/attempt-*/paid-1.finished.json')).unlink()
    old = scoring.read_jsonl
    opened=[]
    def guarded(path):
        if Path(path) == gold: opened.append(path)
        return old(path)
    monkeypatch.setattr(scoring, 'read_jsonl', guarded)
    with pytest.raises((ValueError, FileNotFoundError)):
        scoring.score_run(frozen, Path(frozen['run_dir']), gold, documents_path=runtime.document_path)
    assert opened == []


def test_semantic_failures_stay_in_unique_quality_denominator(tmp_path):
    frozen, runtime, gold = closed_fixture(tmp_path, ['malformed'])
    assert hasattr(scoring, 'score_run'), 'protocol scorer missing'
    rows = scoring.score_run(frozen, Path(frozen['run_dir']), gold, documents_path=runtime.document_path)
    result = statistics.analyze_run(frozen, rows, runner.load_events(Path(frozen['run_dir'])))
    assert result['assigned_unique_tasks'] == 2
    assert result['primary']['arm_a']['ratio'] is None
    assert result['primary']['arm_a']['reason'] == 'zero_successes'
    assert len(rows) == 36 and sum(r.joint_em for r in rows) == 0
    with pytest.raises(ValueError, match='assigned|schedule'):
        statistics.analyze_run(frozen, rows[:-1], runner.load_events(Path(frozen['run_dir'])))


@pytest.mark.parametrize('change',['tokens','raw'])
def test_repeated_output_or_token_mismatch_invalidates_primary(tmp_path,change):
    frozen, runtime, _ = protected_fixture(tmp_path)
    original=runtime.reader.backend.generate
    def varying(*args,**kwargs):
        value=original(*args,**kwargs)
        if change=='tokens':
            return replace(value,generated_token_ids=[runtime.reader.backend.calls]*value.generated_tokens)
        return replace(value,raw_output='malformed '+str(runtime.reader.backend.calls))
    runtime.reader.backend.generate=varying
    runner.run(frozen,runtime)
    gold=tmp_path/'gold.jsonl'
    for task in runtime.tasks: append_jsonl(gold,GoldRecord(task.task_id,'blue',[('Lamp 0',0)]))
    rows=scoring.score_run(frozen,Path(frozen['run_dir']),gold,documents_path=runtime.document_path)
    result=statistics.analyze_run(frozen,rows,runner.load_events(Path(frozen['run_dir'])))
    assert result['primary']['status']=='invalid'
    assert result['primary']['recorded_flags']['deterministic_outputs'] is False
    assert result['quality_claim_valid'] is False
    assert len(result['repeated_output_mismatches'])==4


def test_scored_values_cannot_be_changed_after_score_closure(tmp_path):
    frozen, runtime, gold = closed_fixture(tmp_path)
    assert hasattr(scoring, 'score_run'), 'protocol scorer missing'
    rows = scoring.score_run(frozen, Path(frozen['run_dir']), gold, documents_path=runtime.document_path)
    rows[0] = replace(rows[0], total_serving_seconds=rows[0].total_serving_seconds+1)
    with pytest.raises(ValueError, match='score|closure'):
        statistics.analyze_run(frozen, rows, runner.load_events(Path(frozen['run_dir'])))


def test_validity_assessment_binds_actual_evidence_and_requires_rationale(tmp_path):
    frozen,runtime,gold=closed_fixture(tmp_path)
    rows=scoring.score_run(frozen,Path(frozen['run_dir']),gold,documents_path=runtime.document_path)
    events=runner.load_events(Path(frozen['run_dir']))
    initial=statistics.analyze_run(frozen,rows,events)
    assert 'assessment_binding' in initial, 'reviewed validity assessment path missing'
    receipt={**initial['assessment_binding'],'reviewer':'fixture independent review',
        'timing_stationary':False,'single_dominant':None,
        'timing_rationale':'Fixture deliberately represents unequal order blocks; instability observed.',
        'influence_rationale':'Leave-one-out evidence unresolved.'}
    assessed=statistics.analyze_run(frozen,rows,events,validity_assessment=receipt)
    assert assessed['primary']['status']=='invalid'
    assert assessed['primary']['recorded_flags']['timing_stationary'] is False
    assert assessed['validity_assessment']['timing_rationale']==receipt['timing_rationale']
    with pytest.raises(ValueError,match='assessment|evidence'):
        statistics.analyze_run(frozen,rows,events,validity_assessment={**receipt,'timing_evidence_hash':'changed'})
    with pytest.raises(ValueError,match='rationale'):
        statistics.analyze_run(frozen,rows,events,validity_assessment={**receipt,'timing_rationale':''})
    assert initial['timing_diagnostics']['chronological_blocks']
    assert initial['timing_diagnostics']['length_strata']


def test_job_mapping_preserves_failed_attempts_and_shared_allocations(tmp_path):
    frozen,runtime,_=protected_fixture(tmp_path,['INFRA','malformed'])
    root=Path(frozen['run_dir']);root.mkdir()
    assigned=[j['job_id'] for j in frozen['schedule']['jobs']]
    runner.record_shared_cost(root,'offline',0,36_000_000_000,assigned,source_id='original-index-attempt')
    runner.run(frozen,runtime)
    gold=tmp_path/'gold.jsonl'
    for t in runtime.tasks: append_jsonl(gold,GoldRecord(t.task_id,'blue',[('Lamp 0',0)]))
    rows=scoring.score_run(frozen,root,gold,documents_path=runtime.document_path)
    mapping=json.loads((root/'job-evidence.json').read_text())
    first=mapping['jobs'][0]
    assert len(first['attempts'])==2
    assert len(first['event_ids'])>len(runner._complete(root/'jobs'/first['job_id']).event_ids)
    assert first['shared_allocations']==[{'event_id':json.loads((root/'shared-costs.jsonl').read_text())['event_id'],
        'source_id':'original-index-attempt','allocated_seconds':1.0}]
    assert rows[0].total_experiment_seconds==rows[0].total_serving_seconds+1

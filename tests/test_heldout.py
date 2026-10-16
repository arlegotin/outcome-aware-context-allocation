"""Invented offline pairs; no native acquisition or benchmark Gold."""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from outcome_poc.features import build_features
from outcome_poc.schemas import GoldRecord, PairedActionRow, RankedDocument
from outcome_poc.train import FEATURE_NAMES


def invented_pairs(n=48):
    rows, gold = [], {}
    for i in range(n):
        signal = i % 4
        question = f'Which invented lantern {i} glows' + '?' * (signal + 1)
        ranked = [RankedDocument(f'doc-{j}', 1. - j * (.01 + signal * .015), j,
                                 40 + signal * 15 + j, 2, f'Invented title {j}') for j in range(10)]
        # The ten action rescues only the two highest observable gap groups.
        small = int(signal == 0)
        full = int(signal != 1)
        identity = f'invented-{i}'
        rows.append(PairedActionRow(identity, question, ranked,
            dict(zip(FEATURE_NAMES, map(float, build_features(question, ranked)))),
            f'{identity}-2', f'{identity}-10', small, full, 1, 1,
            [f'{identity}-event2'], [f'{identity}-event10'], 1., 4., 'ok', 'ok'))
        gold[identity] = GoldRecord(identity, 'invented answer', [('Invented title 3' if signal >= 2 else 'Invented title 0', 0)])
    return rows, gold


@pytest.fixture
def fast_estimators(monkeypatch):
    # Explicit test-only estimator override; research code retains the baseline recipe.
    from outcome_poc import train
    monkeypatch.setattr(train, 'GBM_PARAMS', {**train.GBM_PARAMS, 'n_estimators': 5, 'min_samples_leaf': 2})
    monkeypatch.setattr(train, 'RF_PARAMS', {**train.RF_PARAMS, 'n_estimators': 7, 'min_samples_leaf': 2})


def run_fixture(tmp_path, fast_estimators, *, holdout_mutation=False):
    from outcome_poc.heldout import evaluate
    rows, gold = invented_pairs()
    fit_ids = [r.task_id for r in rows[:32]]
    holdout_ids = [r.task_id for r in rows[32:]]
    if holdout_mutation:
        rows[32:] = [replace(r, small_joint_em=1-r.small_joint_em, full_joint_em=1-r.full_joint_em,
                             small_answer_em=1, full_answer_em=1,
                             small_cost_seconds=9., full_cost_seconds=90.) for r in rows[32:]]
    summary = evaluate(rows, {i: gold[i] for i in fit_ids}, fit_ids, holdout_ids,
                       tmp_path, fit_sizes=(16, 32))
    return summary


def test_holdout_outcomes_cannot_change_selection_or_fitted_state(tmp_path, fast_estimators):
    # A learner fitted or tuned on any holdout label/cost changes this locked state.
    first = run_fixture(tmp_path/'original', fast_estimators)
    second = run_fixture(tmp_path/'perturbed', fast_estimators, holdout_mutation=True)
    a = json.loads((tmp_path/'original/private/fit-only-state.json').read_text())
    b = json.loads((tmp_path/'perturbed/private/fit-only-state.json').read_text())
    assert a == b
    assert first['curves'][-1]['methods']['FIXED-10']['S'] == 12
    assert second['curves'][-1]['methods']['FIXED-10']['S'] == 4
    assert a['curves'][-1]['selected_A']['family'] == 'PRE-OUTCOME-GBM'
    assert a['curves'][-1]['selected_B']['family'] != 'PRE-OUTCOME-GBM'


def test_actual_heldout_decisions_and_every_membership_are_recorded(tmp_path, fast_estimators):
    summary = run_fixture(tmp_path/'evaluation', fast_estimators)
    private = tmp_path/'evaluation/private'
    membership = json.loads((private/'memberships.json').read_text())
    assert membership['holdout_ids'] == [f'invented-{i}' for i in range(32, 48)]
    assert [c['fit_size'] for c in membership['curves']] == [16, 32]
    for curve in membership['curves']:
        validations = []
        for fold in curve['folds']:
            assert set(fold['train_ids']).isdisjoint(fold['validation_ids'])
            assert set(fold['train_group_hashes']).isdisjoint(fold['validation_group_hashes'])
            assert set(fold['train_ids']).isdisjoint(membership['holdout_ids'])
            validations.extend(fold['validation_ids'])
        assert sorted(validations) == sorted(curve['fit_ids'])
    decisions = [json.loads(line) for line in (private/'heldout-decisions.jsonl').read_text().splitlines()]
    assert decisions
    assert {d['task_id'] for d in decisions} == set(membership['holdout_ids'])
    assert all(d['task_id'] not in membership['fit_ids'] for d in decisions)
    assert all(d['reconstructed_seconds'] >= d['observed_action_seconds'] for d in decisions)
    assert all(d['policy_choose_seconds'] >= 0 for d in decisions)
    assert summary['evaluation'] == 'heldout_development_research'
    assert all(c['holdout_n'] == 16 for c in summary['curves'])
    assert 'invented-' not in (tmp_path/'evaluation/public-summary.json').read_text()
    assert summary['screen']['final_efficiency_claim'] is False


def test_duplicate_normalized_question_cannot_cross_fit_holdout(tmp_path, fast_estimators):
    from outcome_poc.heldout import evaluate
    rows, gold = invented_pairs(12)
    rows[-1] = replace(rows[-1], question='  ' + rows[0].question.upper() + '  ')
    with pytest.raises(ValueError, match='duplicate group'):
        evaluate(rows, {r.task_id: gold[r.task_id] for r in rows[:8]},
                 [r.task_id for r in rows[:8]], [r.task_id for r in rows[8:]], tmp_path/'bad', fit_sizes=(8,))
    assert not (tmp_path/'bad').exists()


def test_duplicate_fit_group_is_kept_in_one_inner_fold(tmp_path, fast_estimators):
    from outcome_poc.heldout import evaluate
    rows, gold = invented_pairs(16)
    # Identical observable rows with different IDs remain a single CV group.
    rows[1] = replace(rows[1], question=rows[0].question, ranked_documents=rows[0].ranked_documents,
                      features=rows[0].features)
    evaluate(rows, {r.task_id: gold[r.task_id] for r in rows[:12]},
             [r.task_id for r in rows[:12]], [r.task_id for r in rows[12:]], tmp_path/'groups', fit_sizes=(12,))
    folds = json.loads((tmp_path/'groups/private/memberships.json').read_text())['curves'][0]['folds']
    assert next(i for i,f in enumerate(folds) if 'invented-0' in f['validation_ids']) == next(
        i for i,f in enumerate(folds) if 'invented-1' in f['validation_ids'])


def test_no_success_has_no_ratio_and_failures_keep_costs(tmp_path, fast_estimators):
    from outcome_poc.heldout import evaluate
    rows, gold = invented_pairs(16)
    rows = [replace(r, small_joint_em=0, full_joint_em=0, small_answer_em=0, full_answer_em=0,
                    small_status='parse_error', full_status='abstain') for r in rows]
    summary = evaluate(rows, {r.task_id: gold[r.task_id] for r in rows[:12]},
                       [r.task_id for r in rows[:12]], [r.task_id for r in rows[12:]], tmp_path/'zero', fit_sizes=(12,))
    fixed = summary['curves'][0]['methods']['FIXED-10']
    assert fixed['S'] == 0 and fixed['R'] is None
    assert fixed['total_T'] >= 16.
    assert fixed['statuses'] == {'abstain': 4}
    assert summary['screen']['continue_to_common_tuning'] is False


def test_endpoint_policies_skip_model_and_numeric_cost_is_conservative():
    from outcome_poc.heldout import _inner_seconds, _threshold_rule
    from outcome_poc.policies import ThresholdPolicy
    class FailingModel:
        def predict(self, _):
            raise AssertionError('endpoint must not evaluate estimator')
    rows, _ = invented_pairs(4)
    endpoint = ThresholdPolicy(FailingModel(), {'policy_id':'PRE-OUTCOME-GBM', **_threshold_rule('always_two', [0., 1.])})
    assert endpoint.choose(rows[0].question, rows[0].ranked_documents).action_k == 2
    assert _inner_seconds(rows[0], 2, 'always_two') == 1.
    assert _inner_seconds(rows[0], 10, 'always_ten') == 4.
    assert _inner_seconds(rows[0], 2, 'numeric') == 1.02
    assert _threshold_rule(.5, [0., 2.]) == {'threshold_mode':'numeric', 'threshold':1.}


def test_rate_random_uses_question_hash_and_fit_probability_only():
    from outcome_poc.heldout import _random_action
    decisions = [_random_action(f'Invented question {i}', .5, 20261018) for i in range(100)]
    assert set(decisions) == {2, 10}
    assert decisions == [_random_action(f'Invented question {i}', .5, 20261018) for i in range(100)]
    assert _random_action('Invented question', 0., 3) == 2
    assert _random_action('Invented question', 1., 3) == 10
    assert _random_action(' invented QUESTION ', .5, 3) == _random_action('Invented question', .5, 3)


def cli_module():
    import importlib.util
    path = Path(__file__).resolve().parents[1]/'tools/evaluate_routing_signal.py'
    spec = importlib.util.spec_from_file_location('heldout_cli_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_closed_loader_uses_real_ranking_metadata_and_inner_event_ids(tmp_path):
    from dataclasses import asdict
    from outcome_poc.schemas import Document
    from outcome_poc.storage import content_hash
    module = cli_module()
    docs = [Document(content_hash([f'Invented {j}', [f'Sentence {j}.']]), f'Invented {j}',
                     [f'Sentence {j}.'], len(f'Sentence {j}.')) for j in range(10)]
    ranked = [RankedDocument(d.doc_id, 1.-j*.01, j, len(d.title)+d.character_count,
                             len(d.sentences), d.title) for j,d in enumerate(docs)]
    (tmp_path/'documents.jsonl').write_text(''.join(json.dumps(asdict(d))+'\n' for d in docs))
    task = {'task_id':'invented-task', 'split':'fit_extension', 'question':'Which invented moon glows?',
            'candidate_ids':[d.doc_id for d in docs]}
    records, scores = [], []
    for k in (2, 10):
        job = {'task_id':'invented-task','job_id':f'invented-job-{k}','arm':str(k),'budget':k,'stage':'fit','group':'natural'}
        payload = {'ranking':[asdict(r) for r in ranked], 'evidence_ids':[r.doc_id for r in ranked[:k]],
                   'result':{'status':'ok'}, 'actual_allocation_runner':True}
        records.append((job,payload,{}))
        scores.append({'task_id':'invented-task','job_id':job['job_id'],'arm':str(k),'joint_em':int(k==10),
                       'answer_em':1,'seconds':float(k),'status':'ok'})
        inner = tmp_path/'jobs'/job['job_id']/'allocation'
        inner.mkdir(parents=True)
        (inner/'predictions.jsonl').write_text(json.dumps({'job_id':job['job_id'],'task_id':job['task_id'],
            'status':'ok','evidence_ids':payload['evidence_ids'],'event_ids':[f'actual-inner-event-{k}']})+'\n')
        request = tmp_path/'stages/natural/requests'/f'{job["job_id"]}.json'
        request.parent.mkdir(parents=True,exist_ok=True)
        request.write_text(json.dumps({'seconds':float(k)}))
    rows = module._paired_rows(tmp_path, records, scores, {task['task_id']:task}, [task['task_id']], [])
    assert len(rows) == 1
    assert rows[0].small_event_ids == ['actual-inner-event-2']
    assert rows[0].full_event_ids == ['actual-inner-event-10']
    assert rows[0].small_cost_seconds == 2. and rows[0].full_cost_seconds == 10.
    assert len(rows[0].features) == 42
    assert rows[0].ranked_documents == ranked
    # A metadata drift must not be silently accepted as an observable input.
    records[0][1]['ranking'][0]['character_count'] += 1
    records[1][1]['ranking'][0]['character_count'] += 1
    with pytest.raises(ValueError, match='metadata'):
        module._paired_rows(tmp_path, records, scores, {task['task_id']:task}, [task['task_id']], [])


def test_cli_refuses_unclosed_root_before_gold_access(tmp_path):
    import subprocess
    import sys
    root = tmp_path/'unclosed';root.mkdir()
    (root/'plan.json').write_text(json.dumps({'config':{'schema_version':5,'study_kind':'allocation-routing-signal-v5',
                                                       'purpose':'routing-signal'}, 'historical_checkout':'invented'}))
    result = subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'tools/evaluate_routing_signal.py'),
                             '--root',str(root),'--output',str(tmp_path/'out')],capture_output=True,text=True)
    assert result.returncode != 0
    assert not (tmp_path/'out').exists()


def test_restricted_output_permissions_and_fit_gold_only(tmp_path, fast_estimators):
    from outcome_poc.heldout import evaluate
    rows, gold = invented_pairs(16)
    fit = [r.task_id for r in rows[:12]]
    held = [r.task_id for r in rows[12:]]
    # Extra holdout Gold is rejected, even though the caller has offline access.
    with pytest.raises(ValueError,match='exactly fit IDs'):
        evaluate(rows,gold,fit,held,tmp_path/'bad-gold',fit_sizes=(12,))
    assert not (tmp_path/'bad-gold').exists()
    run_fixture(tmp_path/'restricted',fast_estimators)
    assert (tmp_path/'restricted').stat().st_mode & 0o077 == 0
    assert (tmp_path/'restricted/private').stat().st_mode & 0o077 == 0


def test_invalid_citation_keeps_answer_success_with_strict_failure(tmp_path, fast_estimators):
    from outcome_poc.heldout import evaluate
    rows,gold = invented_pairs(16)
    rows = [replace(r,small_joint_em=0,full_joint_em=0,small_answer_em=1,full_answer_em=1,
                    small_status='invalid_citation',full_status='invalid_citation') for r in rows]
    fit = [r.task_id for r in rows[:12]]
    held = [r.task_id for r in rows[12:]]
    result = evaluate(rows,{i:gold[i] for i in fit},fit,held,tmp_path/'citation-failure',fit_sizes=(12,))
    fixed = result['curves'][0]['methods']['FIXED-10']
    assert fixed['E'] == 4 and fixed['S'] == 0 and fixed['R'] is None
    assert fixed['statuses'] == {'invalid_citation':4}
    assert fixed['total_T'] >= 16.

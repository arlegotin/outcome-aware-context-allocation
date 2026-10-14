"""Deterministic inexpensive policy boundaries, without reader calls."""

import json
from dataclasses import asdict, replace

import numpy as np
import pytest

from outcome_poc.policies import AdaptiveKPolicy, FixedPolicy, ThresholdPolicy, training_thresholds
from outcome_poc.schemas import PaidDraft, ReaderResult, validate_record
from test_features import packet


class Regressor:
    def __init__(self, prediction):
        self.prediction = prediction

    def predict(self, values):
        assert values.shape == (1, 42)
        return np.array([self.prediction])


class ForbiddenPrediction:
    def predict(self, values):
        raise AssertionError('prediction forbidden at endpoints or exhausted packets')


@pytest.mark.parametrize('mode,k', [('always_two', 2), ('always_ten', 10)])
def test_learned_endpoints_alias_fixed_actions_without_prediction(mode, k):
    decision = ThresholdPolicy(ForbiddenPrediction(), {'threshold_mode': mode, 'threshold': None}).choose('Lamp?', packet())
    fixed = FixedPolicy(k).choose('Lamp?', packet())
    assert (decision.action_k, decision.requested_budget, decision.effective_budget) == (k, k, fixed.effective_budget)
    assert decision.predicted_delta is None
    validate_record(decision)
    assert 'Infinity' not in json.dumps(asdict(decision), allow_nan=False)


@pytest.mark.parametrize('mode,k,expected_joint', [('always_two', 2, 0), ('always_ten', 10, 1)])
def test_endpoint_scores_alias_fixed_fixture_predictions(tmp_path, mode, k, expected_joint):
    # This is an offline scoring fixture, never a serving import or a model call.
    from outcome_poc.scoring import Scorer
    from outcome_poc.schemas import GoldRecord, Prediction
    from retrieval_helpers import document, store
    doc = document('Invented lamp', ['A violet lamp.'])
    documents = store(tmp_path, [doc])
    gold = GoldRecord('invented-task', 'violet', [('Invented lamp', 0)])
    predictions = {
        action: Prediction('fixture', 'invented-task', f'FIXED-{action}', 'protocol', 'job', 1, 0,
                           [doc.doc_id], 'raw', answer, [(doc.doc_id, 0)], 'ok',
                           'revision', 'prompt', 'decode', 1., 1, 1, 1, ['event'])
        for action, answer in [(2, 'blue'), (10, 'violet')]
    }
    learned = ThresholdPolicy(ForbiddenPrediction(), {'threshold_mode': mode, 'threshold': None}).choose('Lamp?', packet())
    fixed = FixedPolicy(k).choose('Lamp?', packet())
    assert Scorer().score(predictions[learned.action_k], gold, documents).joint_em == expected_joint
    assert predictions[learned.action_k] == predictions[fixed.action_k]


@pytest.mark.parametrize('prediction,threshold,k,clipped', [(0, 0, 2, 0), (.2, 0, 10, .2),
                                                          (-5, -1, 2, -1), (5, 1, 2, 1)])
def test_numeric_threshold_is_inclusive_and_prediction_is_clipped(prediction, threshold, k, clipped):
    policy = ThresholdPolicy(Regressor(prediction), {'threshold_mode': 'numeric', 'threshold': threshold})
    a, b = policy.choose('Lamp?', packet()), policy.choose('Lamp?', packet())
    assert a == b
    assert a.action_k == k and a.predicted_delta == clipped
    validate_record(a)


def test_query_only_uses_seven_features_and_proxy_clips_to_zero_one():
    class QueryRegressor:
        def predict(self, values):
            assert values.shape == (1, 7)
            return np.array([0])
    query = ThresholdPolicy(QueryRegressor(), {'policy_id': 'QUERY-ONLY', 'threshold_mode': 'numeric', 'threshold': 0})
    assert query.choose('Lamp?', packet()).action_k == 2
    proxy = ThresholdPolicy(Regressor(-5), {'policy_id': 'PROXY-LABEL', 'threshold_mode': 'numeric', 'threshold': 0})
    assert proxy.choose('Lamp?', packet()).predicted_delta == 0


@pytest.mark.parametrize('policy', [FixedPolicy(2), AdaptiveKPolicy(0),
                                  ThresholdPolicy(ForbiddenPrediction(), {'threshold_mode': 'numeric', 'threshold': 0})])
def test_zero_packet_is_exhausted_without_prediction_and_pre_policies_reject_paid_draft(policy):
    decision = policy.choose('Lamp?', [])
    assert decision.reason == 'budget_exhausted' and decision.effective_budget == 0
    validate_record(decision)
    draft = PaidDraft('invented-event', ReaderResult('raw', None, [], 'parse_error', 0, 0, [], [], None))
    with pytest.raises(ValueError, match='paid draft'):
        policy.choose('Lamp?', packet(), draft)


@pytest.mark.parametrize('k,m,cap,effective', [(10, 3, 10, 3), (2, 1, 1, 1), (10, 3, 2, 0), (2, 10, 1, 0)])
def test_requested_and_effective_budgets_preserve_short_packet_aliases_and_caps(k, m, cap, effective):
    decision = FixedPolicy(k).choose('Lamp?', packet()[:m], caller_cap=cap)
    assert (decision.action_k, decision.requested_budget, decision.effective_budget) == (k, k, effective)
    assert (decision.reason == 'budget_exhausted') == (effective == 0)


def test_learned_full_request_exhausts_rather_than_switching_to_two_under_cap():
    policy = ThresholdPolicy(Regressor(.5), {'threshold_mode': 'numeric', 'threshold': 0})
    decision = policy.choose('Lamp?', packet(), caller_cap=2)
    assert (decision.action_k, decision.requested_budget, decision.effective_budget) == (10, 10, 0)
    assert decision.reason == 'budget_exhausted'


@pytest.mark.parametrize('cap', [True, -1, 11, 2.5])
def test_invalid_caller_caps_are_rejected(cap):
    with pytest.raises(ValueError):
        FixedPolicy(2).choose('Lamp?', packet(), caller_cap=cap)


def test_adaptive_search_uses_eight_gaps_for_ten_and_zero_buffer_never_returns_zero():
    scores = (1, .9375, .875, .8125, .75, .6875, .625, .5625, .3125, -1)
    assert AdaptiveKPolicy(0).choose('Lamp?', packet(scores)).action_k == 8
    # Exact ties and near-flat values choose the first largest permitted gap.
    assert AdaptiveKPolicy(0).choose('Lamp?', packet((.5,)*10)).action_k == 1
    assert AdaptiveKPolicy(0).choose('Lamp?', packet((.5, .5-1e-12) + (.5-1e-12,)*8)).action_k == 1
    assert AdaptiveKPolicy(5).choose('Lamp?', packet((.5,)*10)).action_k == 6
    assert AdaptiveKPolicy(5).choose('Lamp?', packet((.5,))).action_k == 1
    assert AdaptiveKPolicy(5).policy_id != AdaptiveKPolicy(5, variant='tuned').policy_id


def test_impossible_caller_cap_exhausts_before_model_prediction(caplog):
    policy = ThresholdPolicy(ForbiddenPrediction(), {'threshold_mode': 'numeric', 'threshold': 0})
    decision = policy.choose('Lamp?', packet(), caller_cap=1)
    assert decision.reason == 'budget_exhausted' and decision.effective_budget == 0
    assert 'fallback' not in caplog.text


@pytest.mark.parametrize('failure', ['schema', 'features', 'model', 'nonfinite', 'shape'])
@pytest.mark.parametrize('cap,effective', [(10, 10), (2, 0)])
def test_signal_failure_logs_full_fallback_or_exhaustion(failure, cap, effective, monkeypatch, caplog):
    from outcome_poc import policies
    config = {'threshold_mode': 'numeric', 'threshold': 0}
    model, ranked = Regressor(0), packet()
    if failure == 'schema': config['feature_schema_hash'] = 'stale'
    if failure == 'features': monkeypatch.setattr(policies, 'build_features', lambda *args: np.full(42, np.nan))
    if failure == 'model': model = ForbiddenPrediction()
    if failure == 'nonfinite': model = Regressor(float('inf'))
    if failure == 'shape': model.n_features_in_ = 7
    decision = ThresholdPolicy(model, config).choose('Lamp?', ranked, caller_cap=cap)
    assert decision.action_k == 10 and decision.effective_budget == effective
    assert decision.reason == ('full_fallback' if effective else 'budget_exhausted')
    assert 'fallback' in caplog.text
    validate_record(decision)


def test_invalid_rank_metadata_triggers_safe_fallback():
    ranked = packet()
    ranked[0] = replace(ranked[0], score=float('nan'))
    decision = ThresholdPolicy(ForbiddenPrediction(), {'threshold_mode': 'numeric', 'threshold': 0}).choose('Lamp?', ranked)
    assert decision.reason == 'full_fallback' and decision.effective_budget == 10


def test_training_thresholds_are_unique_linear_quantiles_and_finite_null_endpoints():
    configs = training_thresholds(np.array([0., 1.]))
    numeric = [c['threshold'] for c in configs if c['threshold_mode'] == 'numeric']
    np.testing.assert_allclose(numeric, np.arange(21)*.05, atol=1e-15)
    assert configs[0] == {'threshold_mode': 'always_ten', 'threshold': None}
    assert configs[-1] == {'threshold_mode': 'always_two', 'threshold': None}
    assert len(training_thresholds(np.array([.5, .5]))) == 3
    json.dumps(configs, allow_nan=False)
    for invalid in [np.array([]), np.array([np.nan]), np.array([np.inf]), np.ones((2, 2))]:
        with pytest.raises(ValueError): training_thresholds(invalid)


@pytest.mark.parametrize('constructor', [lambda: FixedPolicy(0), lambda: FixedPolicy(11),
                                        lambda: AdaptiveKPolicy(-1), lambda: AdaptiveKPolicy(6),
                                        lambda: ThresholdPolicy(Regressor(0), {'threshold_mode': 'numeric', 'threshold': None}),
                                        lambda: ThresholdPolicy(Regressor(0), {'threshold_mode': 'always_two', 'threshold': np.inf})])
def test_invalid_policy_configs_are_rejected(constructor):
    with pytest.raises(ValueError): constructor()

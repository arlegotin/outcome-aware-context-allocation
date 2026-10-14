"""Paid POST gates: no free drafts, gold inputs, or repaired retained failures."""
from dataclasses import replace
import math
import numpy as np
import pytest
from outcome_poc import features, policies, runner
from outcome_poc.schemas import PaidDraft, ReaderResult
from serving_helpers import fixture_runtime
from test_features import packet


def draft(raw='bad', status='parse_error', answer=None, citations=None, event='paid'):
    return PaidDraft(event, ReaderResult(raw, answer, citations or [], status, 1, 1, [1], [2], 'stop'))


def test_post_appendages_observable_only_and_event_required():
    assert hasattr(features, 'post_features'), '46-value paid draft features missing'
    d = draft('some raw', 'ok', 'x', [('d', 0), ('d', 0), ('d', 1)])
    values = features.post_features('Who?', packet(), d)
    assert values.shape == (46,)
    np.testing.assert_array_equal(values[:42], features.build_features('Who?', packet()))
    np.testing.assert_allclose(values[42:], [math.log1p(8), 1, 0, 2])
    np.testing.assert_allclose(features.post_features('Who?', packet(), draft('', 'abstain', '  '))[42:], [0, 1, 1, 0])
    assert features.post_features('Who?', packet(), draft('x', 'invalid_citation', 'x', [('d', 0)]))[-1] == 0
    with pytest.raises(ValueError): features.post_features('Who?', packet(), draft(event=''))


def test_post_retention_preserves_failure_and_cost(tmp_path):
    assert hasattr(policies, 'PostOutcomePolicy'), 'POST gate missing'
    runtime, job, _ = fixture_runtime(tmp_path, ['bad'])
    policy = policies.PostOutcomePolicy(None, {'threshold_mode':'always_two', 'threshold':None})
    p = runner.execute_job({**job, 'policy':policy}, runtime, tmp_path)
    assert (p.status, p.raw_output, p.generation_calls) == ('parse_error', 'bad', 1)
    assert p.elapsed_seconds == 11.
    with pytest.raises(ValueError): policy.choose('Who?', packet())


def test_post_clip_and_caps_without_unpaid_or_extra_prediction():
    assert hasattr(policies, 'PostOutcomePolicy'), 'POST gate missing'
    class Model:
        n_features_in_ = 46
        def predict(self, x):
            assert x.shape == (1,46)
            return [9.]
    policy = policies.PostOutcomePolicy(Model(), {'threshold_mode':'numeric','threshold':1.})
    d = policy.choose('Who?',packet(),draft())
    assert d.action_k == 2 and d.predicted_delta == 1.
    assert policy.choose('Who?',packet(),draft(),caller_cap=0).effective_budget == 0
    assert policy.choose('Who?',[],None).effective_budget == 0


def test_paid_start_write_failure_is_zero_backend_calls_and_valid_closed_failure(tmp_path,monkeypatch):
    runtime, job, _ = fixture_runtime(tmp_path)
    original=runner.atomic_json
    def write(path, data):
        if path.name.endswith('.started.json'): raise OSError('forced paid-start write failure')
        return original(path,data)
    monkeypatch.setattr(runner,'atomic_json',write)
    result=runner.execute_job(job,runtime,tmp_path)
    assert result.status == 'infra_error'
    assert result.generation_calls == 0 and result.event_ids == []
    assert runtime.reader.backend.calls == 0
    runner._validate_events(result, [e for e in runner.load_events(tmp_path) if e.role != 'telemetry'])


def test_post_fit_uses_event_bound_existing_drafts_and_preserves_prior_origin(tmp_path):
    from outcome_poc import train
    assert hasattr(train,'fit_post_gate'), 'POST fitting missing'
    from test_training import rows, gold
    values=rows(); prior=tmp_path/'prior'; output=tmp_path/'post'
    original=train.fit_gates(values,gold(values),prior)
    original_bytes=(prior/'fit-origin.json').read_bytes()
    drafts={r.task_id:draft('paid raw','ok','x',event=r.small_event_ids[0]) for r in values}
    fitted=train.fit_post_gate(values,drafts,prior,output)
    manifest=fitted['models']['POST-OUTCOME']
    model=train.load_gate(manifest)
    assert model.n_features_in_ == 46
    assert manifest['feature_schema_hash'] == features.post_feature_schema()['hash']
    assert manifest['parameters'] == original['models']['PRE-OUTCOME-GBM']['parameters']
    assert (prior/'fit-origin.json').read_bytes() == original_bytes
    expected=np.clip(model.predict(np.array([features.post_features(r.question,r.ranked_documents,drafts[r.task_id]) for r in values])),-1,1)
    np.testing.assert_array_equal(expected,manifest['training_predictions'])
    with pytest.raises(ValueError,match='event'):
        train.fit_post_gate(values,{**drafts,values[0].task_id:draft(event='unbound')},prior,tmp_path/'bad')
    with pytest.raises(ValueError,match='origin'):
        train.fit_post_gate([replace(values[0],full_joint_em=1)]+values[1:],drafts,prior,tmp_path/'other')

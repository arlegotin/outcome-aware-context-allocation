from outcome_poc.runner import validate_harness


def test_harness_fixture_gate_is_complete_without_native_model_calls():
    result = validate_harness()
    assert result['passed'] is True
    assert set(result['checks']) >= {'aa','correct_wrong','malformed_citation','timeout','threshold_alias','statistics','cost_ledger','resume'}
    assert result['native_calls'] == 0


def test_harness_timeout_gate_requires_actual_worker_termination():
    result=validate_harness()
    assert result['checks']['timeout'] is True
    assert result['timeout_record']['status']=='timeout'
    assert result['timeout_record']['stop_reason']=='forced_timeout'
    assert result['timeout_record']['partial_tokens'] == 1

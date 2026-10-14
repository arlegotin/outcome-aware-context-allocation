from dataclasses import replace
import json
import pytest


def test_forecast_charges_whole_observed_pipeline_and_reserves_reporting():
    from outcome_poc.pilot import capacity_forecast
    result = capacity_forecast([{'serving_seconds': 4., 'experiment_seconds': 5.,
                                'prompt_tokens': 100, 'output_tokens': 20,
                                'components': {'generation': 3.}, 'planned_jobs': 10}], 4000.)
    assert result['conservative_seconds_per_job'] == 7.5
    assert result['forecast_seconds'] == 75.
    assert result['reserved_reporting_seconds'] == 3600.
    assert result['feasible']
    assert not capacity_forecast([], 5000.)['feasible']
    with pytest.raises(ValueError): capacity_forecast([{'serving_seconds': -1}], 5000.)


def test_slice_frozen_from_hash_before_outcomes_and_no_protected_membership():
    from outcome_poc.pilot import pilot_schedule
    from serving_helpers import fixture_runtime
    from pathlib import Path
    runtime, job, _ = fixture_runtime(Path('/tmp'))
    tasks = [replace(job['task'], task_id=str(i)) for i in range(4)]
    config = {'tasks': tasks, 'assigned_ids': [t.task_id for t in tasks], 'all_k_size': 2, 'determinism': False}
    schedule = pilot_schedule(config)
    assert schedule['all_k_ids'] == pilot_schedule({**config, 'tasks': tasks[::-1]})['all_k_ids']
    assert len(schedule['jobs']) == 4*3 + 2*8
    with pytest.raises(ValueError): pilot_schedule({**config, 'tasks': [replace(tasks[0], split='protected')]})
    with pytest.raises(ValueError): pilot_schedule({**config, 'assigned_ids': ['missing']})


def test_pilot_closes_every_assigned_job_with_distinct_direct_repetitions(tmp_path):
    from outcome_poc.pilot import run_pilot
    from serving_helpers import fixture_runtime
    from outcome_poc.storage import read_jsonl
    runtime, job, _ = fixture_runtime(tmp_path)
    config = {'tasks': [job['task']], 'assigned_ids': ['task'], 'all_k_size': 1,
              'run_dir': str(tmp_path/'pilot'), 'warmups': False, 'determinism': True}
    result = run_pilot(config, runtime)
    assert result['closure']['record_count'] == 13
    assert runtime.reader.backend.calls == 13
    assert result['determinism']['passed']
    rows = list(read_jsonl(tmp_path/'pilot/predictions.jsonl'))
    assert len({row['job_id'] for row in rows}) == 13
    assert len([row for row in rows if row['policy_id'] == 'FIXED-2']) == 2
    assert len([row for row in rows if row['policy_id'] == 'NO-CONTEXT-DIAGNOSTIC']) == 1
    assert json.loads((tmp_path/'pilot/schedule.json').read_text())['all_k_ids'] == ['task']


def test_pilot_rejects_annotation_bearing_configuration(tmp_path):
    from outcome_poc.pilot import run_pilot
    from serving_helpers import fixture_runtime
    runtime, job, _ = fixture_runtime(tmp_path)
    with pytest.raises(ValueError, match='annotation'):
        run_pilot({'tasks': [job['task']], 'assigned_ids': ['task'], 'gold': {}}, runtime)


def test_closed_pilot_analysis_keeps_all_metrics_and_denominators(tmp_path):
    from outcome_poc.pilot import run_pilot
    from outcome_poc.oracle import analyze_pilot
    from outcome_poc.storage import append_jsonl
    from serving_helpers import fixture_runtime
    runtime, job, _ = fixture_runtime(tmp_path)
    root = tmp_path/'pilot'
    result = run_pilot({'tasks': [job['task']], 'assigned_ids': ['task'], 'all_k_size': 0,
                        'run_dir': str(root), 'warmups': False, 'determinism': True}, runtime)
    for observation in result['observations']:
        append_jsonl(root/'scores.jsonl', {'job_id': observation['job_id'], 'task_id': 'task',
                     'joint_em': int(observation['k'] == 10), 'answer_em': 1, 'support_em': int(observation['k'] == 10),
                     'joint_f1': .5, 'answer_f1': 1., 'support_f1': .5})
    summary = analyze_pilot(root, root/'scores.jsonl', tmp_path/'summary', 50000., planned_jobs=10)
    assert summary['headroom']['n'] == 1
    assert summary['headroom']['rescues'] == 1
    assert summary['metrics']['2']['assigned'] == 1
    assert summary['metrics']['10']['joint_em'] == 1.
    assert summary['metrics']['0']['joint_em'] == 0.
    assert summary['gate']['next_stage'] == 'extend_reserved_pilot_to_64'
    assert (tmp_path/'summary/headroom.csv').exists()
    assert (tmp_path/'summary/reader_failures.jsonl').exists()


def test_backend_throughput_keeps_available_rates_and_marks_missing_or_nonfinite():
    from types import SimpleNamespace
    from outcome_poc.generation import backend_throughput
    result = backend_throughput(SimpleNamespace(prompt_tps=200., generation_tps=50.))
    assert result['backend_prompt_tokens_per_second'] == 200.
    assert result['backend_generation_tokens_per_second'] == 50.
    assert result['rate_kind'] == 'backend_reported_including_callback_and_first_token_overhead'
    missing = backend_throughput(SimpleNamespace(prompt_tps=float('nan')))
    assert missing['backend_prompt_tokens_per_second'] is None
    assert missing['backend_generation_tokens_per_second'] is None
    assert missing['reason'] == 'backend_rate_unavailable'


def test_shared_setup_encloses_initial_load_without_double_charge(tmp_path):
    from outcome_poc.pilot import run_pilot
    from serving_helpers import fixture_runtime
    runtime, job, _ = fixture_runtime(tmp_path)
    runtime.reader.backend.lifecycle = [{'kind': 'load', 'start_ns': 0, 'stop_ns': 7000000000, 'owner': None}]
    result = run_pilot({'tasks': [job['task']], 'assigned_ids': ['task'], 'all_k_size': 0,
                        'run_dir': str(tmp_path/'pilot'), 'warmups': False, 'determinism': False,
                        'setup_interval': [0, 9000000000]}, runtime)
    assert not any('setup' in row['components'] for row in result['observations'])
    assert sum(row['experiment_seconds']-row['serving_seconds'] for row in result['observations']) < 10.

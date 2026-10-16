"""NEW injected-clock contracts for the actual runner, not suspend certification."""
from dataclasses import replace
from pathlib import Path

import pytest

from serving_helpers import fixture_runtime


def configured(tmp_path,monkeypatch):
    from outcome_poc import continuous_serving as continuous
    runtime,job,clock=fixture_runtime(tmp_path)
    monkeypatch.setattr(continuous,'continuous_ns',clock)
    monkeypatch.setattr(continuous,'boot_identity',lambda:'authored-boot')
    monkeypatch.setattr(continuous,'clock_identity',lambda:{'name':'authored-continuous','unit':'nanoseconds'})
    runtime.reader.backend.clock=clock
    runtime.config={**runtime.config,'request_timing':continuous.VERSION,
                    'request_clock':{'boot_id':'authored-boot','clock':continuous.clock_identity()}}
    return runtime,job,clock


def test_complete_interval_includes_initial_sync_and_durable_completion_receipt(tmp_path,monkeypatch):
    from outcome_poc import runner,continuous_serving as continuous
    runtime,job,clock=configured(tmp_path,monkeypatch)
    runtime.reader.backend.synchronize=lambda:clock.advance(2)
    original_runner=runner.atomic_json;original_continuous=continuous.atomic_json
    def core_write(path,value):
        if Path(path).name=='completion.json':clock.advance(3)
        return original_runner(path,value)
    def receipt_write(path,value):
        if Path(path).name=='receipt.json':clock.advance(5)
        return original_continuous(path,value)
    monkeypatch.setattr(runner,'atomic_json',core_write)
    monkeypatch.setattr(continuous,'atomic_json',receipt_write)
    prediction=runner.execute_job(job,runtime,tmp_path/'run')
    assert prediction.elapsed_seconds==13  # Inner active work is diagnostic.
    assert runner.accounting(tmp_path/'run',prediction)['total_serving_seconds']==23
    runner.close_run(tmp_path/'run',[job])
    assert runner.accounting(tmp_path/'run',prediction)['total_serving_seconds']==23
    calls=runtime.reader.backend.calls
    assert runner.execute_job(job,runtime,tmp_path/'run')==prediction
    assert runtime.reader.backend.calls==calls


def test_receipt_write_failure_cannot_adopt_inner_commit_or_score(tmp_path,monkeypatch):
    from outcome_poc import runner,continuous_serving as continuous
    runtime,job,clock=configured(tmp_path,monkeypatch)
    original=continuous.atomic_json
    def broken(path,value):
        if Path(path).name=='receipt.json':raise OSError('authored receipt fsync failure')
        return original(path,value)
    monkeypatch.setattr(continuous,'atomic_json',broken)
    with pytest.raises(OSError,match='receipt fsync'):runner.execute_job(job,runtime,tmp_path/'run')
    assert (tmp_path/'run/jobs/job/completion.json').is_file()
    with pytest.raises(ValueError,match='continuous|incomplete|receipt'):
        runner.close_run(tmp_path/'run',[job])
    monkeypatch.setattr(continuous,'atomic_json',original)
    with pytest.raises(ValueError,match='incomplete|unobserved'):
        runner.execute_job(job,runtime,tmp_path/'run')
    assert runtime.reader.backend.calls==1


def test_repeated_task_jobs_do_not_charge_other_jobs_nested_telemetry(tmp_path,monkeypatch):
    from outcome_poc import runner
    runtime,job,clock=configured(tmp_path,monkeypatch)
    root=tmp_path/'run'
    original=runner.atomic_json
    def writing(path,value):
        clock.advance(1)
        return original(path,value)
    monkeypatch.setattr(runner,'atomic_json',writing)
    other={**job,'job_id':'job-two','repetition_id':1}
    predictions=[runner.execute_job(assigned,runtime,root) for assigned in (job,other)]
    runner.close_run(root,[job,other])
    for prediction in predictions:
        measured=runner.accounting(root,prediction)
        # Every diagnostic interval is inside its own complete request. Neither
        # repetition has external setup or shared costs to allocate.
        assert measured['total_experiment_seconds']==measured['total_serving_seconds']


@pytest.mark.parametrize('failure',['boot','domain','reverse'])
def test_clock_contract_refuses_unknown_domain_and_time_reversal(tmp_path,monkeypatch,failure):
    from outcome_poc import runner,continuous_serving as continuous
    runtime,job,clock=configured(tmp_path,monkeypatch)
    if failure=='boot':monkeypatch.setattr(continuous,'boot_identity',lambda:'different-boot')
    if failure=='domain':runtime.reader.backend.clock=lambda:0
    if failure=='reverse':
        original=runtime.reader.backend.generate
        def backwards(*args,**kwargs):
            result=original(*args,**kwargs);clock.value=-100_000_000_000;return result
        runtime.reader.backend.generate=backwards
    with pytest.raises((ValueError,RuntimeError),match='clock|boot|continuous|timestamp|start_ns'):
        runner.execute_job(job,runtime,tmp_path/'run')
    assert not (tmp_path/'run/predictions.closed.json').exists()
    if failure!='reverse':assert runtime.reader.backend.calls==0


def test_unknown_cleanup_preserves_paid_partial_and_blocks_closure(tmp_path,monkeypatch):
    from outcome_poc import runner
    from outcome_poc.followup.supervisor import CleanupFailure
    from outcome_poc.schemas import ReaderResult
    runtime,job,clock=configured(tmp_path,monkeypatch)
    def broken(*args,**kwargs):
        clock.advance(1)
        raise CleanupFailure(ReaderResult('paid partial',None,[],'timeout',2,1,[1,2],[3],'forced_timeout'),RuntimeError('authored orphan'))
    runtime.reader.backend.generate=broken
    with pytest.raises(RuntimeError,match='cleanup'):runner.execute_job(job,runtime,tmp_path/'run')
    row=runner._read(tmp_path/'run/jobs/job/attempt-1/paid-1.finished.json')
    assert row['result']['raw_output']=='paid partial'
    with pytest.raises(ValueError):runner.close_run(tmp_path/'run',[job])


@pytest.mark.parametrize('boundary',['sync','generation'])
def test_plain_supervision_cleanup_error_cannot_become_retryable_complete_request(tmp_path,monkeypatch,boundary):
    from outcome_poc import runner
    runtime,job,clock=configured(tmp_path,monkeypatch)
    def failed(*args,**kwargs):
        clock.advance(1)
        raise RuntimeError('reader worker could not be killed')
    if boundary=='generation':runtime.reader.backend.generate=failed
    else:
        original=runtime.reader.backend.synchronize;count=0
        def sync():
            nonlocal count
            count+=1
            if count>=2:failed()
            return original()
        runtime.reader.backend.synchronize=sync
    with pytest.raises(RuntimeError,match='cleanup|killed'):
        runner.execute_job(job,runtime,tmp_path/'run')
    with pytest.raises(ValueError):runner.close_run(tmp_path/'run',[job])
    assert not list((tmp_path/'run/continuous-requests/job').glob('*/boundary.json'))


@pytest.mark.parametrize('family',['post','judge'])
def test_continuous_interval_charges_both_paid_calls_and_durable_receipt(tmp_path,monkeypatch,family):
    from outcome_poc import runner,continuous_serving as continuous
    from outcome_poc.policies import PostOutcomePolicy,SufficiencyPolicy
    from outcome_poc.schemas import ReaderResult
    runtime,job,clock=configured(tmp_path,monkeypatch)
    original_generate=runtime.reader.backend.generate
    if family=='post':job['policy']=PostOutcomePolicy(None,{'threshold_mode':'always_ten'})
    else:
        job['policy']=SufficiencyPolicy()
        def generate(*args,**kwargs):
            result=original_generate(*args,**kwargs)
            if runtime.reader.backend.calls==1:return replace(result,raw_output='INSUFFICIENT')
            return result
        runtime.reader.backend.generate=generate
    original=continuous.atomic_json
    def receipt(path,value):
        if Path(path).name=='receipt.json':clock.advance(2)
        return original(path,value)
    monkeypatch.setattr(continuous,'atomic_json',receipt)
    prediction=runner.execute_job(job,runtime,tmp_path/'run')
    assert prediction.generation_calls==2
    assert runner.accounting(tmp_path/'run',prediction)['total_serving_seconds']==23
    assert [e.role for e in runner.load_events(tmp_path/'run') if e.role.startswith('generation:')]==(
        ['generation:draft','generation:answer'] if family=='post' else ['generation:judge','generation:answer'])
    runner.close_run(tmp_path/'run',[job])


def test_continuous_scientific_accounting_rejects_development_replay(tmp_path,monkeypatch):
    from outcome_poc import runner
    runtime,job,clock=configured(tmp_path,monkeypatch)
    source=runner.execute_job(job,runtime,tmp_path/'source')
    replay={**job,'job_id':'replayed','mode':'replay','cache_mode':'development_replay',
            'replay_prediction':source,'replay_events':runner.load_events(tmp_path/'source'),
            'replay_signature':runtime.decision_payload['action_signature']}
    with pytest.raises(ValueError,match='direct|fresh|replay'):
        runner.execute_job(replay,runtime,tmp_path/'run')
    assert runtime.reader.backend.calls==1

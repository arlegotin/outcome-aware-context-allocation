import json
from dataclasses import replace

import pytest

from outcome_poc import runner
from outcome_poc.storage import atomic_json, read_jsonl
from serving_helpers import fixture_runtime


def test_completion_resume_checksum_and_complete_assigned_denominator(tmp_path):
    runtime,job,_ = fixture_runtime(tmp_path)
    result = runner.execute_job(job,runtime,tmp_path)
    assert runner.execute_job(job,runtime,tmp_path) == result
    assert runtime.reader.backend.calls == 1
    with pytest.raises(ValueError,match='assigned'):
        runner.close_run(tmp_path,[job,{**job,'job_id':'missing'}])
    closed = runner.close_run(tmp_path,[job])
    assert closed['record_count'] == 1
    path = tmp_path / 'jobs/job/completion.json'
    row = json.loads(path.read_text()); row['prediction_sha256'] = 'bad'; atomic_json(path,row)
    with pytest.raises(ValueError,match='checksum'):
        runner.execute_job(job,runtime,tmp_path)


def test_semantic_failure_no_retry_and_infrastructure_retry_links_all_cost(tmp_path):
    runtime,job,_ = fixture_runtime(tmp_path,['malformed'])
    assert runner.execute_job(job,runtime,tmp_path / 'semantic').status == 'parse_error'
    runner.execute_job(job,runtime,tmp_path / 'semantic')
    assert runtime.reader.backend.calls == 1
    runtime,job,_ = fixture_runtime(tmp_path,['INFRA','{"answer":"blue","citations":[]}'])
    first = runner.execute_job(job,runtime,tmp_path / 'infra')
    assert first.status == 'infra_error'
    with pytest.raises(ValueError,match='infrastructure'):
        runner.close_run(tmp_path / 'infra',[job])
    second = runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path / 'infra')
    assert second.attempt == 2
    totals = runner.accounting(tmp_path / 'infra',second)
    assert totals == {'total_serving_seconds':22.,'total_experiment_seconds':22.}
    attempts = list(read_jsonl(tmp_path / 'infra/attempts.jsonl'))
    assert attempts[-1]['previous_attempt'] == 1
    assert runner.close_run(tmp_path / 'infra',[job])['record_count'] == 1


def test_interruption_after_payload_before_completion_recovers_without_second_answer(tmp_path,monkeypatch):
    runtime,job,_ = fixture_runtime(tmp_path)
    original = runner.atomic_json
    def interrupted(path,value):
        if path.name == 'completion.json': raise KeyboardInterrupt('killed at commit')
        return original(path,value)
    monkeypatch.setattr(runner,'atomic_json',interrupted)
    with pytest.raises(KeyboardInterrupt): runner.execute_job(job,runtime,tmp_path)
    monkeypatch.setattr(runner,'atomic_json',original)
    result = runner.execute_job(job,runtime,tmp_path)
    assert result.status == 'ok' and runtime.reader.backend.calls == 1
    assert runner.close_run(tmp_path,[job])['record_count'] == 1


def test_missing_paid_event_blocks_scoring_and_closure(tmp_path):
    runtime,job,_ = fixture_runtime(tmp_path)
    result = runner.execute_job(job,runtime,tmp_path)
    event_path = tmp_path / 'jobs/job/attempt-1/events.jsonl'
    rows = list(read_jsonl(event_path)); event_path.unlink()
    for row in rows:
        if row['role'] != 'generation:answer':
            runner.append_jsonl(event_path,row)
    with pytest.raises(ValueError,match='event|checksum'):
        runner.accounting(tmp_path,result)
    with pytest.raises(ValueError,match='event|checksum'):
        runner.close_run(tmp_path,[job])


def test_killed_process_mid_completion_write_resumes_assigned_set_without_second_answer(tmp_path):
    import os
    import subprocess
    import sys
    import time
    from pathlib import Path
    child = '''
import sys,time
from pathlib import Path
from serving_helpers import fixture_runtime
from outcome_poc import runner
root=Path(sys.argv[1]);runtime,job,_=fixture_runtime(root)
original=runner.atomic_json
def blocked(path,value):
    if path.name=='completion.json':
        (path.parent / '.completion.json.partial.tmp').write_text('{"partial":')
        (root / 'kill-ready').write_text('ready')
        time.sleep(30)
    return original(path,value)
runner.atomic_json=blocked
runner.execute_job(job,runtime,root)
'''
    environment={**os.environ,'PYTHONPATH':str(Path(__file__).parent)+os.pathsep+os.environ.get('PYTHONPATH','')}
    process=subprocess.Popen([sys.executable,'-c',child,str(tmp_path)],env=environment)
    try:
        deadline=time.monotonic()+5
        while not (tmp_path / 'kill-ready').exists() and time.monotonic()<deadline: time.sleep(.01)
        assert (tmp_path / 'kill-ready').exists()
        process.kill();process.wait(timeout=2)
    finally:
        if process.poll() is None: process.kill();process.wait()
    runtime,job,_=fixture_runtime(tmp_path)
    result=runner.execute_job(job,runtime,tmp_path)
    assert result.status=='ok' and runtime.reader.backend.calls==0
    recovered=runner.close_run(tmp_path,[job])
    fresh_runtime,fresh_job,_=fixture_runtime(tmp_path)
    runner.execute_job(fresh_job,fresh_runtime,tmp_path / 'fresh')
    assert recovered['record_count']==runner.close_run(tmp_path / 'fresh',[fresh_job])['record_count']==1


def test_uncertified_process_death_preserves_cost_but_blocks_inference(tmp_path):
    runtime,job,clock=fixture_runtime(tmp_path)
    attempt=tmp_path / 'jobs/job/attempt-1';attempt.mkdir(parents=True)
    atomic_json(attempt / 'started.json',{'start_ns':0})
    atomic_json(attempt / 'paid-1.started.json',{'start_ns':1_000_000_000,'role':'generation:answer'})
    clock.advance(7)
    result=runner.execute_job(job,runtime,tmp_path)
    recovered=list(read_jsonl(attempt / 'recovered-events.jsonl'))
    assert [e['elapsed_seconds'] for e in recovered if e['role']=='generation:answer']==[6.]
    assert [e['elapsed_seconds'] for e in recovered if e['role']=='serving']==[7.]
    with pytest.raises(ValueError,match='uncertified'):
        runner.close_run(tmp_path,[job])


def test_payload_and_prior_attempt_checksums_block_accounting_tampering(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path,['INFRA','{"answer":"blue","citations":[]}'])
    runner.execute_job(job,runtime,tmp_path)
    result=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    (tmp_path / 'jobs/job/attempt-1/payload.json').write_text('{}')
    with pytest.raises(ValueError,match='checksum'):
        runner.accounting(tmp_path,result)


def test_closed_run_cannot_add_an_unscheduled_answer(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    runner.execute_job(job,runtime,tmp_path)
    runner.close_run(tmp_path,[job])
    with pytest.raises(ValueError,match='closed'):
        runner.execute_job({**job,'job_id':'new-task'},runtime,tmp_path)
    assert runtime.reader.backend.calls==1


def test_bound_payload_has_no_unmeasured_enclosing_time_placeholder(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    result=runner.execute_job(job,runtime,tmp_path)
    payload=json.loads((tmp_path/'jobs/job/attempt-1/payload.json').read_text())
    assert 'elapsed_seconds' not in payload['prediction']
    assert result.elapsed_seconds==11.


def test_observed_final_sync_failure_retains_paid_receipt_and_exact_retry_cost(tmp_path):
    runtime,job,clock=fixture_runtime(tmp_path)
    count=[0]
    def synchronize():
        count[0]+=1
        if count[0]==2:
            clock.advance(4)
            raise RuntimeError('observed final device sync fault')
    runtime.reader.backend.synchronize=synchronize
    first=runner.execute_job(job,runtime,tmp_path)
    assert first.status=='infra_error' and first.elapsed_seconds==15.
    assert first.raw_output and first.generation_calls==1
    assert not (tmp_path/'jobs/job/attempt-1/interrupted.json').exists()
    second=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    assert second.status=='ok' and second.attempt==2
    assert runner.accounting(tmp_path,second)=={'total_serving_seconds':26.,'total_experiment_seconds':26.}
    assert runner.close_run(tmp_path,[job])['record_count']==1


def test_observed_payload_failure_is_certified_and_not_retried_semantically(tmp_path):
    runtime,job,clock=fixture_runtime(tmp_path)
    original=runtime.serialize
    count=[0]
    def serialize(value):
        count[0]+=1
        if count[0]==1:
            clock.advance(3)
            raise RuntimeError('observed payload codec fault')
        return original(value)
    runtime.serialize=serialize
    first=runner.execute_job(job,runtime,tmp_path)
    assert first.status=='infra_error' and first.elapsed_seconds==11.
    assert first.raw_output and first.generated_tokens==8
    assert runner.execute_job(job,runtime,tmp_path)==first
    assert runtime.reader.backend.calls==1
    second=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    assert runner.accounting(tmp_path,second)['total_serving_seconds']==22.
    assert runner.close_run(tmp_path,[job])['record_count']==1


def test_observed_transaction_fault_uses_certified_receipt_and_explicit_retry(tmp_path,monkeypatch):
    runtime,job,clock=fixture_runtime(tmp_path)
    original=runner.atomic_json
    fault=[False]
    def injected(path,value):
        if path.name=='payload.json' and not fault[0]:
            fault[0]=True;clock.advance(2)
            raise OSError('observed one-shot transaction fault')
        return original(path,value)
    monkeypatch.setattr(runner,'atomic_json',injected)
    first=runner.execute_job(job,runtime,tmp_path)
    assert first.status=='infra_error' and first.raw_output and first.generation_calls==1
    assert runner.execute_job(job,runtime,tmp_path)==first
    assert runtime.reader.backend.calls==1
    second=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    assert second.status=='ok' and second.attempt==2
    assert runner.accounting(tmp_path,second)=={'total_serving_seconds':22.,'total_experiment_seconds':24.}
    assert runner.close_run(tmp_path,[job])['record_count']==1


def test_storage_failure_preventing_certification_remains_uncertified(tmp_path,monkeypatch):
    runtime,job,_=fixture_runtime(tmp_path)
    original=runner.atomic_json
    broken=[False]
    def unavailable(path,value):
        if path.name=='payload.json': broken[0]=True
        if broken[0]: raise OSError('storage unavailable')
        return original(path,value)
    monkeypatch.setattr(runner,'atomic_json',unavailable)
    with pytest.raises(OSError): runner.execute_job(job,runtime,tmp_path)
    monkeypatch.setattr(runner,'atomic_json',original)
    second=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    with pytest.raises(ValueError,match='uncertified'):
        runner.close_run(tmp_path,[job])


def test_latest_observed_retry_failure_supersedes_older_completion(tmp_path,monkeypatch):
    runtime,job,clock=fixture_runtime(tmp_path,['INFRA','{"answer":"blue","citations":[]}'])
    first=runner.execute_job(job,runtime,tmp_path)
    original=runner.atomic_json
    failed=[False]
    def injected(path,value):
        if path.parent.name=='attempt-2' and path.name=='payload.json' and not failed[0]:
            failed[0]=True;clock.advance(2);raise OSError('second attempt publication fault')
        return original(path,value)
    monkeypatch.setattr(runner,'atomic_json',injected)
    second=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    assert second.attempt==2 and second.status=='infra_error'
    assert runner.execute_job(job,runtime,tmp_path)==second
    third=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    assert third.attempt==3
    assert runner.accounting(tmp_path,third)=={'total_serving_seconds':33.,'total_experiment_seconds':35.}
    assert runner.close_run(tmp_path,[job])['record_count']==1


def test_observed_initial_sync_failure_has_exact_interval_and_can_resolve(tmp_path):
    runtime,job,clock=fixture_runtime(tmp_path)
    count=[0]
    def synchronize():
        count[0]+=1
        if count[0]==1:
            clock.advance(4)
            raise RuntimeError('observed synchronization failure before query')
    runtime.reader.backend.synchronize=synchronize
    first=runner.execute_job(job,runtime,tmp_path)
    assert first.status=='infra_error' and first.generation_calls==0 and first.elapsed_seconds==4.
    second=runner.execute_job({**job,'retry_infrastructure':True},runtime,tmp_path)
    assert runner.accounting(tmp_path,second)['total_serving_seconds']==15.
    assert runner.close_run(tmp_path,[job])['record_count']==1

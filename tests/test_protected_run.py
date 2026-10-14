"""Frozen scheduler behavior using synthetic tasks and actual durable ledgers."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from outcome_poc import runner, protocol
from outcome_poc.schemas import Task
from outcome_poc.storage import atomic_json, append_jsonl, content_hash, read_jsonl
from serving_helpers import fixture_runtime
from test_protocol import inputs


def protected_fixture(tmp_path, outputs=None, n=2):
    runtime, job, clock = fixture_runtime(tmp_path, outputs)
    c = inputs(tmp_path)
    c['tasks'] = [replace(job['task'], task_id=str(i), split='protected') for i in range(n)]
    c.update(population_ids=[t.task_id for t in c['tasks']], n=n)
    c['development']['reader'] = runtime.config.copy()
    c['development']['reader']['timeout_seconds'] = 20.
    runtime.config = c['development']['reader'].copy()
    frozen = protocol.freeze(c)
    class Model:
        def predict(self, values): return np.zeros(len(values))
    runtime.models = {name:Model() for name in frozen['methods']['models']}
    for name,model in runtime.models.items(): model.n_features_in_ = 46 if name == 'POST-OUTCOME' else 7 if name == 'QUERY-ONLY' else 42
    runtime.tasks = c['tasks']
    documents = [runtime.documents.get(i) for i in job['task'].candidate_ids]
    path = tmp_path/'documents.jsonl'
    for doc in documents: append_jsonl(path, doc)
    runtime.document_path = path
    return frozen, runtime, clock


def test_full_assigned_schedule_is_fresh_and_resumes_without_calls(tmp_path):
    frozen, runtime, _ = protected_fixture(tmp_path, ['not JSON'])
    assert hasattr(runner, 'run'), 'protected scheduler missing'
    result = runner.run(frozen, runtime)
    assert result['status'] == 'closed'
    root = Path(frozen['run_dir'])
    rows = list(read_jsonl(root/'predictions.jsonl'))
    assert len(rows) == 36 and {r['task_id'] for r in rows} == set(frozen['sample']['task_ids'])
    assert all(r['status'] == 'parse_error' for r in rows)
    assert runtime.reader.backend.calls == 38
    assert sum(r['generation_calls'] for r in rows) == 38
    assert len({r['job_id'] for r in rows}) == 36
    before = runtime.reader.backend.calls
    assert runner.run(frozen, runtime) == result
    assert runtime.reader.backend.calls == before
    assert (root/'protected-attempt.started.json').exists()
    with pytest.raises(ValueError, match='attempt'): protocol.bind_source(frozen, 'b'*40)


def test_unverified_direct_protected_serve_and_mutated_runtime_block(tmp_path):
    frozen, runtime, _ = protected_fixture(tmp_path)
    row = frozen['schedule']['jobs'][0]
    task = next(t for t in runtime.tasks if t.task_id == row['task_id'])
    job = {**row, 'task':task, 'policy':protocol.materialize_policy(row['method'], runtime.models),
           'protocol_hash':frozen['protocol_hash'], 'run_id':'confirmation'}
    with pytest.raises(ValueError, match='protected|verified'): runner.serve(task, job['policy'], runtime, job)
    assert hasattr(runner, 'run'), 'protected scheduler missing'
    runtime.config['timeout_seconds'] += 1
    with pytest.raises(ValueError, match='settings|runtime'): runner.run(frozen, runtime)
    assert runtime.reader.backend.calls == 0


def test_deadline_preserves_full_schedule_and_incomplete_status(tmp_path):
    frozen, runtime, _ = protected_fixture(tmp_path)
    # The clock is an operational input, not a new frozen deadline.
    runtime.utcnow = lambda: '2100-01-01T00:00:00+00:00'
    assert hasattr(runner, 'run'), 'protected scheduler missing'
    result = runner.run(frozen, runtime)
    assert result['status'] == 'incomplete' and result['assigned_jobs'] == 36
    assert result['completed_jobs'] == 0
    assert not (Path(frozen['run_dir'])/'predictions.closed.json').exists()
    assert runtime.reader.backend.calls == 0


def test_interruption_resumes_exact_schedule_and_keeps_all_attempts(tmp_path):
    frozen, runtime, _ = protected_fixture(tmp_path)
    assert hasattr(runner, 'run'), 'protected scheduler missing'
    original = runtime.reader.backend.generate
    count = [0]
    def interrupted(*args, **kwargs):
        count[0] += 1
        if count[0] == 3: raise KeyboardInterrupt('process interrupted')
        return original(*args, **kwargs)
    runtime.reader.backend.generate = interrupted
    with pytest.raises(KeyboardInterrupt): runner.run(frozen, runtime)
    assert not (Path(frozen['run_dir'])/'predictions.closed.json').exists()
    runtime.reader.backend.generate = original
    result = runner.run(frozen, runtime)
    # A process-death interval cannot be invented even when later work is resumable.
    assert result['status'] == 'incomplete'
    assert result['assigned_jobs'] == 36
    assert 'uncertified' in json.dumps(result)


def test_runtime_rejects_extra_or_changed_sampled_tasks_before_attempt(tmp_path):
    frozen, runtime, _ = protected_fixture(tmp_path)
    runtime.tasks.append(replace(runtime.tasks[0], task_id='unassigned'))
    with pytest.raises(ValueError,match='sampled|assigned'): runner.run(frozen,runtime)
    assert runtime.reader.backend.calls == 0


def test_infrastructure_retry_preserves_attempt_event_ownership(tmp_path):
    frozen, runtime, _ = protected_fixture(tmp_path,['INFRA','malformed'])
    result=runner.run(frozen,runtime)
    assert result['status']=='closed'
    root=Path(frozen['run_dir'])
    assert len(list(root.glob('jobs/*/attempt-*'))) == 37
    first=frozen['schedule']['jobs'][0]['job_id']
    prediction=runner._complete(root/'jobs'/first)
    assert prediction.attempt==2
    assert runner.accounting(root,prediction)['total_serving_seconds']>prediction.elapsed_seconds


def test_closure_shared_allocation_is_linear_in_assigned_jobs(tmp_path,monkeypatch):
    frozen,runtime,_=protected_fixture(tmp_path)
    root=Path(frozen['run_dir']);root.mkdir()
    runner.record_shared_cost(root,'cold_setup',0,36_000_000_000,[j['job_id'] for j in frozen['schedule']['jobs']])
    original=runner._shared_allocations;calls=[]
    def observed(rows):
        calls.append(len(rows));return original(rows)
    monkeypatch.setattr(runner,'_shared_allocations',observed)
    runner.run(frozen,runtime)
    assert len(calls)<=2, 'closure rebuilds full shared allocation once per assigned job'


def test_timeout_is_terminal_failure_without_semantic_retry(tmp_path):
    frozen,runtime,_=protected_fixture(tmp_path)
    original=runtime.reader.backend.generate
    def timed_out(*args,**kwargs):
        return replace(original(*args,**kwargs),status='timeout',stop_reason='forced_timeout')
    runtime.reader.backend.generate=timed_out
    result=runner.run(frozen,runtime)
    assert result['status']=='closed'
    rows=list(read_jsonl(Path(frozen['run_dir'])/'predictions.jsonl'))
    assert len(rows)==36 and all(r['status']=='timeout' for r in rows)
    assert all(r['attempt']==1 for r in rows)
    assert runtime.reader.backend.calls==36


def test_last_timeout_settles_causal_reload_before_closure(tmp_path):
    frozen,runtime,clock=protected_fixture(tmp_path)
    backend=runtime.reader.backend;original=backend.generate
    backend.lifecycle=[];backend.pending_owner=None;backend.worker_pid=1
    last=frozen['schedule']['jobs'][-1]['job_id']
    def generate(*args,**kwargs):
        result=original(*args,**kwargs)
        if backend.job_owner['job_id']==last:
            backend.pending_owner=backend.job_owner.copy();backend.worker_pid=None
            return replace(result,status='timeout',stop_reason='forced_timeout')
        return result
    def synchronize():
        if backend.pending_owner:
            start=clock();clock.advance(7)
            backend.lifecycle.append({'kind':'load','owner':backend.pending_owner.copy(),'start_ns':start,'stop_ns':clock(),'status':'ok'})
            backend.pending_owner=None;backend.worker_pid=1
    backend.generate=generate;backend.synchronize=synchronize
    result=runner.run(frozen,runtime)
    assert result['status']=='closed'
    root=Path(frozen['run_dir']);p=runner._complete(root/'jobs'/last)
    assert p.status=='timeout' and p.attempt==1
    assert runner.accounting(root,p)['total_serving_seconds']==p.elapsed_seconds+7


def test_restart_load_is_charged_to_pending_origin_and_appears_in_mapping(tmp_path):
    from outcome_poc import protected
    frozen,runtime,clock=protected_fixture(tmp_path)
    runner.run(frozen,runtime)
    # A dedicated unclosed copy of the last transaction represents a checkpoint
    # after a timeout and before its deferred load. Never alter a closed fixture.
    import shutil
    original=Path(frozen['run_dir']);root=tmp_path/'restart'
    jobid=frozen['schedule']['jobs'][-1]['job_id']
    shutil.copytree(original/'jobs'/jobid,root/'jobs'/jobid)
    p=runner._complete(root/'jobs'/jobid)
    owner={'run_dir':str(root),'run_id':p.run_id,'job_id':p.job_id,'task_id':p.task_id,'policy_id':p.policy_id,'attempt':p.attempt}
    atomic_json(root/'jobs'/jobid/'attempt-1'/'recovery-pending.json',{'owner':owner,'recovery_id':content_hash(owner)})
    assert hasattr(protected,'pending_restart_owner'), 'persisted causal restart recovery missing'
    assert protected.pending_restart_owner(root)==owner
    protected.record_restart_load(owner,100_000_000_000,107_000_000_000,True)
    assert protected.pending_restart_owner(root) is None
    assert runner.accounting(root,p)['total_serving_seconds']==p.elapsed_seconds+7
    assert runner._owned_reloads(root/'jobs'/jobid/'attempt-1')[0].role=='worker_reload'


def test_runtime_rejects_document_store_with_unsampled_extra_document(tmp_path):
    from outcome_poc.data_runtime import DocumentStore
    from retrieval_helpers import document
    frozen,runtime,_=protected_fixture(tmp_path)
    append_jsonl(runtime.document_path,document('Extra unassigned',['Not selected.']))
    runtime.documents=DocumentStore(runtime.document_path)
    with pytest.raises(ValueError,match='document|selected'): runner.run(frozen,runtime)
    assert runtime.reader.backend.calls==0


def test_verified_session_cannot_generate_outside_durable_attempt_or_after_closure(tmp_path):
    frozen,runtime,_=protected_fixture(tmp_path)
    runner.run(frozen,runtime)
    job=next(iter(runtime._protected_jobs.values()))
    calls=runtime.reader.backend.calls
    with pytest.raises(ValueError,match='closed|attempt'):
        runner.serve(job['task'],job['policy'],runtime,job)
    assert runtime.reader.backend.calls==calls

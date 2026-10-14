import time

import pytest

from outcome_poc.generation import SupervisedBackend
from outcome_poc.schemas import GenerationRequest, ReaderResult


class WorkerTokenizer:
    chat_template='fixture'
    def apply_chat_template(self,messages,**kwargs):
        return 'stall' if 'Color?' in messages[-1]['content'] else 'ok'


class FixtureBackend:
    tokenizer = WorkerTokenizer()
    def generate(self,prompt,request,*,rendered=False):
        self.progress_callback('partial',[1,2],[3])
        if prompt == 'stall':
            time.sleep(30)
        return ReaderResult('{"answer":"blue","citations":[]}',None,[],'ok',2,1,[1,2],[3],'stop')
    def synchronize(self): pass


def fixture_factory(): return FixtureBackend()


def test_stalled_worker_forced_timeout_retains_partial_and_reloads_next_boundary():
    request = GenerationRequest('r','m','p','d','answer',8192,256,.15,'none')
    with SupervisedBackend(fixture_factory, startup_timeout=5) as backend:
        first_pid = backend.worker_pid
        result = backend.generate('stall',request,rendered=True)
        assert result.status == 'timeout' and result.raw_output == 'partial'
        assert result.generated_token_ids == [3] and result.prompt_token_ids == [1,2]
        assert result.stop_reason == 'forced_timeout'
        assert backend.worker_pid is None
        result = backend.generate('ok',request,rendered=True)
        assert result.status == 'ok' and backend.worker_pid != first_pid
        assert len(backend.lifecycle) == 3  # load, forced termination, reload


def test_worker_reload_charge_survives_timeout_and_is_added_once(tmp_path):
    from outcome_poc import runner
    from outcome_poc.generation import Reader
    from serving_helpers import fixture_runtime
    runtime,job,_=fixture_runtime(tmp_path)
    runtime.clock=time.perf_counter_ns
    runtime.serialize=runner.canonical_bytes
    with SupervisedBackend(fixture_factory,startup_timeout=5) as backend:
        # Worker startup belongs to setup. Subsequent reload belongs to serving.
        runtime.reader=Reader(backend)
        first=runner.execute_job(job,runtime,tmp_path / 'first')
        assert first.status=='timeout'
        from dataclasses import replace
        second=runner.execute_job({**job,'job_id':'job2','task':replace(job['task'],question='Next?')},runtime,tmp_path / 'second')
        events=runner.load_events(tmp_path / 'second')
        assert len([e for e in events if e.role=='worker_reload'])==0
        source=runner.load_events(tmp_path / 'first')
        assert len([e for e in source if e.role=='worker_reload'])==1
        totals=runner.accounting(tmp_path / 'second',second)
        assert totals['total_serving_seconds'] == second.elapsed_seconds
        assert runner.accounting(tmp_path / 'first',first)['total_serving_seconds'] > first.elapsed_seconds


def test_failed_arm_owns_deferred_reload_without_changing_its_completion(tmp_path):
    from outcome_poc import runner
    from serving_helpers import fixture_runtime
    runtime,job,clock=fixture_runtime(tmp_path)
    original=runtime.reader.backend
    class Backend:
        tokenizer=original.tokenizer
        worker_pid=1
        lifecycle=[{'kind':'load','start_ns':0,'stop_ns':0}]
        pending_owner=None
        def synchronize(self):
            if self.worker_pid is None:
                start=clock();clock.advance(7)
                self.lifecycle.append({'kind':'load','start_ns':start,'stop_ns':clock(),'owner':self.pending_owner})
                self.pending_owner=None
                self.worker_pid=2
        def generate(self,*args,**kwargs):
            result=original.generate(*args,**kwargs)
            if original.calls==1:
                from dataclasses import replace
                self.worker_pid=None
                self.pending_owner=getattr(self,'job_owner',None)
                return replace(result,status='timeout',stop_reason='forced_timeout')
            return result
    runtime.reader.backend=Backend()
    a=runner.execute_job({**job,'arm':'A*'},runtime,tmp_path)
    transaction=tmp_path/'jobs/job/completion.json'
    original_bytes=transaction.read_bytes()
    bjob={**job,'job_id':'B','arm':'B*'}
    b=runner.execute_job(bjob,runtime,tmp_path)
    assert a.elapsed_seconds==b.elapsed_seconds==11.
    assert runner.accounting(tmp_path,a)['total_serving_seconds']==18.
    assert runner.accounting(tmp_path,b)['total_serving_seconds']==11.
    assert transaction.read_bytes()==original_bytes
    # Verified resume of B consumes no lifecycle/cost again.
    assert runner.execute_job(bjob,runtime,tmp_path)==b
    assert runner.accounting(tmp_path,a)['total_serving_seconds']==18.
    from outcome_poc.schemas import CostEvent
    from outcome_poc.storage import read_jsonl
    import json
    source_dir=tmp_path/'jobs/job/attempt-1'
    source_events=[CostEvent(**row) for row in read_jsonl(source_dir/'events.jsonl')]
    source_events += [CostEvent(**json.loads(path.read_text())['event']) for path in (source_dir/'reloads').glob('*.json')]
    source_signature=json.loads((source_dir/'decision.json').read_text())['action_signature']
    replay={**job,'job_id':'replay','mode':'replay','cache_mode':'development_replay',
        'replay_prediction':a,'replay_events':source_events,'replay_signature':source_signature}
    replayed=runner.execute_job(replay,runtime,tmp_path/'replay')
    assert runner.accounting(tmp_path/'replay',replayed)['total_serving_seconds']==18.
    assert original.calls==2
    assert runner.close_run(tmp_path,[{**job,'arm':'A*'},bjob])['record_count']==2


def test_pending_recovery_blocks_closure_and_closed_origin_cannot_gain_cost(tmp_path):
    import json
    from outcome_poc import runner
    from serving_helpers import fixture_runtime
    from types import SimpleNamespace
    runtime,job,_=fixture_runtime(tmp_path)
    result=runner.execute_job(job,runtime,tmp_path)
    owner={'run_dir':str(tmp_path),'run_id':'run','task_id':'task','policy_id':'FIXED-2','job_id':'job','attempt':1}
    backend=SimpleNamespace(pending_owner=owner)
    runner._record_pending_recovery(backend)
    with pytest.raises(ValueError,match='unresolved attributable'):
        runner.close_run(tmp_path,[job])
    (tmp_path/'predictions.closed.json').write_text('{}')
    with pytest.raises(ValueError,match='closed origin'):
        runner._check_pending_recovery(backend)
    assert not list((tmp_path/'jobs/job/attempt-1/reloads').glob('*.json'))


def test_reload_already_inside_origin_service_is_not_charged_twice(tmp_path):
    from outcome_poc import runner
    from serving_helpers import fixture_runtime
    runtime,job,clock=fixture_runtime(tmp_path)
    original=runtime.reader.backend
    class Backend:
        tokenizer=original.tokenizer
        lifecycle=[{'kind':'load','start_ns':0,'stop_ns':0}]
        def synchronize(self): pass
        def generate(self,*args,**kwargs):
            start=clock();clock.advance(7)
            self.lifecycle.append({'kind':'load','start_ns':start,'stop_ns':clock(),'owner':getattr(self,'job_owner',None)})
            return original.generate(*args,**kwargs)
    runtime.reader.backend=Backend()
    result=runner.execute_job(job,runtime,tmp_path)
    assert result.elapsed_seconds==18.
    assert runner.accounting(tmp_path,result)['total_serving_seconds']==18.
    assert len([e for e in runner.load_events(tmp_path) if e.role=='worker_reload_in_serving'])==1
    b=runner.execute_job({**job,'job_id':'B'},runtime,tmp_path)
    assert runner.accounting(tmp_path,result)['total_serving_seconds']==18.
    assert runner.accounting(tmp_path,b)['total_serving_seconds']==18.


def test_closed_supplement_checksum_cannot_change_primary_cost(tmp_path):
    from outcome_poc import runner
    from serving_helpers import fixture_runtime
    runtime,job,_=fixture_runtime(tmp_path)
    result=runner.execute_job(job,runtime,tmp_path)
    runner.close_run(tmp_path,[job])
    # Late origin-owned metadata would invalidate the fixed closure denominator/cost.
    runner.atomic_json(tmp_path/'jobs/job/attempt-1/recovery-pending.json',{'owner':'late'})
    with pytest.raises(ValueError,match='supplement'):
        runner.accounting(tmp_path,result)


def test_inline_reload_receipt_retry_preserves_original_enclosure(tmp_path,monkeypatch):
    from outcome_poc import runner
    from serving_helpers import fixture_runtime
    runtime,job,clock=fixture_runtime(tmp_path)
    original=runtime.reader.backend
    class Backend:
        tokenizer=original.tokenizer
        lifecycle=[{'kind':'load','start_ns':0,'stop_ns':0}]
        def synchronize(self): pass
        def generate(self,*args,**kwargs):
            start=clock();clock.advance(7)
            self.lifecycle.append({'kind':'load','start_ns':start,'stop_ns':clock(),
                                   'owner':getattr(self,'job_owner',None)})
            return original.generate(*args,**kwargs)
    runtime.reader.backend=Backend()
    atomic=runner.atomic_json
    injected=[False]
    def write(path,value):
        if path.parent.name=='reloads' and not injected[0]:
            injected[0]=True
            raise OSError('one-shot inline reload receipt publication failure')
        return atomic(path,value)
    monkeypatch.setattr(runner,'atomic_json',write)
    ajob={**job,'arm':'A*'}
    a=runner.execute_job(ajob,runtime,tmp_path)
    assert a.status=='infra_error' and a.elapsed_seconds==18.
    assert runner.accounting(tmp_path,a)=={'total_serving_seconds':18.,'total_experiment_seconds':18.}
    completion=tmp_path/'jobs/job/completion.json'
    completed_bytes=completion.read_bytes()
    bjob={**job,'job_id':'B','arm':'B*'}
    b=runner.execute_job(bjob,runtime,tmp_path)
    assert b.status=='ok' and b.elapsed_seconds==18.
    assert runner.accounting(tmp_path,a)=={'total_serving_seconds':18.,'total_experiment_seconds':18.}
    assert runner.accounting(tmp_path,b)=={'total_serving_seconds':18.,'total_experiment_seconds':18.}
    assert completion.read_bytes()==completed_bytes
    retry=runner.execute_job({**ajob,'retry_infrastructure':True},runtime,tmp_path)
    assert retry.status=='ok' and retry.attempt==2 and retry.elapsed_seconds==18.
    assert runner.accounting(tmp_path,retry)=={'total_serving_seconds':36.,'total_experiment_seconds':36.}
    assert runner.close_run(tmp_path,[ajob,bjob])['record_count']==2
    # Closure and ordinary resume cannot trigger another publication or paid call.
    assert runner.execute_job(ajob,runtime,tmp_path)==retry
    assert original.calls==3

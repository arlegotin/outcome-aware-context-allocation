import time

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
        assert len([e for e in events if e.role=='worker_reload'])==1
        totals=runner.accounting(tmp_path / 'second',second)
        assert totals['total_serving_seconds'] > second.elapsed_seconds

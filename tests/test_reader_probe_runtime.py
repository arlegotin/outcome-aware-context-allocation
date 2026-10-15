"""Paid-call lifecycle adapter tests with authored fake readers."""
from dataclasses import replace
import json
import pytest
from outcome_poc.schemas import ReaderResult
from outcome_poc.storage import content_hash
from test_reader_probe_study import prepared

class Tokenizer:
    chat_template='authored character tokenizer'
    def apply_chat_template(self,messages,**kwargs):return json.dumps(messages)
    def encode(self,text,**kwargs):return list(text.encode())

class Backend:
    tokenizer=Tokenizer()
    peak_mlx_bytes=1
    last_resources={'peak_mlx_bytes':1,'rss_bytes':1}
    lifecycle=[]
    calls=0
    def __init__(self,factory):pass
    def synchronize(self):pass
    def generate(self,prompt,request,**kwargs):
        type(self).calls+=1
        ids=self.tokenizer.encode(prompt)
        raw='{"answer":"LARK-27","citations":[{"doc_id":"D0","sentence_index":0}]}'
        self.progress_callback(raw,ids,[1,2])
        return ReaderResult(raw,None,[],'ok',len(ids),2,ids,[1,2],'stop')
    def close(self):pass

@pytest.fixture
def run_ready(prepared,monkeypatch):
    from outcome_poc.reader_probe import runtime
    monkeypatch.setattr(runtime,'resource_check',lambda _: {'passed':True})
    Backend.calls=0
    return prepared


def test_three_calls_close_and_rerun_never_regenerates(run_ready):
    from outcome_poc.reader_probe import runtime,study
    result=runtime.run(run_ready,backend_factory=Backend)
    assert result['status']=='passed'
    assert Backend.calls==3
    assert runtime.run(run_ready,backend_factory=Backend)==result
    assert Backend.calls==3
    assert study.verify(run_ready)['plan_hash']==result['plan_hash']
    assert len(result['calls'])==3

@pytest.mark.parametrize('failure',['malformed','truncated','timeout','interrupt','cleanup','counter'])
def test_failure_retained_and_no_paid_retry(run_ready,failure):
    from outcome_poc.reader_probe import runtime
    class Broken(Backend):
        def generate(self,*args,**kwargs):
            value=super().generate(*args,**kwargs)
            if failure=='interrupt':raise KeyboardInterrupt()
            if failure=='counter':self.peak_mlx_bytes=None;self.last_resources={}
            return replace(value,raw_output='bad') if failure=='malformed' else replace(value,status='budget_exhausted') if failure=='truncated' else replace(value,status='timeout') if failure=='timeout' else value
        def close(self):
            if failure=='cleanup':raise RuntimeError('authored cleanup failure')
    result=runtime.run(run_ready,backend_factory=Broken)
    assert result['status'] in {'failed','blocked','incomplete'}
    assert list((run_ready/'jobs').glob('*/started.json'))
    assert list((run_ready/'stages/preflight').glob('session-accounting-*.json'))
    with pytest.raises(RuntimeError,match='non-admissible|quiescence|unknown'):
        runtime.run(run_ready,backend_factory=Backend)


def test_closed_payload_tampering_rejected(run_ready):
    from outcome_poc.reader_probe import runtime,study
    runtime.run(run_ready,backend_factory=Backend)
    path=next((run_ready/'jobs').glob('*/result.json'))
    path.write_text('{}')
    with pytest.raises(ValueError):study.verify(run_ready)


def test_constructor_failure_retains_close_and_lifecycle(run_ready):
    from outcome_poc.reader_probe import runtime
    closed=[]
    class Failed(Backend):
        def __init__(self,factory):
            self.lifecycle=[{'kind':'authored failed construction'}]
            raise RuntimeError('constructor failure')
        def close(self):closed.append(True)
    result=runtime.run(run_ready,backend_factory=Failed)
    assert result['status']=='blocked'
    assert closed==[True]
    assert 'authored failed construction' in (run_ready/'stages/preflight/lifecycle.jsonl').read_text()


def test_prepaid_resource_block_can_resume_with_retained_session(run_ready,monkeypatch):
    from outcome_poc.reader_probe import runtime
    monkeypatch.setattr(runtime,'resource_check',lambda _: {'passed':False})
    first=runtime.run(run_ready,backend_factory=Backend)
    assert first['status']=='blocked' and Backend.calls==0
    monkeypatch.setattr(runtime,'resource_check',lambda _: {'passed':True})
    second=runtime.run(run_ready,backend_factory=Backend)
    assert second['status']=='passed' and second['accounting']['sessions']==2


def test_repeat_mismatch_fails_without_fourth_call(run_ready):
    from outcome_poc.reader_probe import runtime
    class Different(Backend):
        calls=0
        def generate(self,*args,**kwargs):
            value=super().generate(*args,**kwargs)
            return replace(value,generated_token_ids=[1,self.calls])
    result=runtime.run(run_ready,backend_factory=Different)
    assert result['status']=='failed' and Different.calls==3
    assert not (run_ready/'closed.json').exists()


def test_constructor_unknown_worker_blocks_resume(run_ready,monkeypatch):
    from outcome_poc.reader_probe import runtime
    class Failed(Backend):
        def __init__(self,factory):raise RuntimeError('authored constructor')
    monkeypatch.setattr(runtime,'_worker_identity_unknown',lambda *args,**kwargs:True)
    first=runtime.run(run_ready,backend_factory=Failed)
    assert first['accounting']['upper_seconds'] is None
    with pytest.raises(RuntimeError,match='unknown'):
        runtime.run(run_ready,backend_factory=Backend)


def test_failed_call_still_records_post_call_gate(run_ready):
    from outcome_poc.reader_probe import runtime
    class Broken(Backend):
        def generate(self,*args,**kwargs):return replace(super().generate(*args,**kwargs),raw_output='bad')
    runtime.run(run_ready,backend_factory=Broken)
    rows=[json.loads(line) for line in (run_ready/'stages/preflight/gates.jsonl').read_text().splitlines()]
    assert len(rows)==3 and rows[-1]['boundary'].startswith('after_')

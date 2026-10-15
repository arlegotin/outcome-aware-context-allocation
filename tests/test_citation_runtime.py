"""Authored input/model doubles; real sealed stores, transactions and SQLite."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from followup_helpers import Backend
from retrieval_helpers import Encoder
from test_citation_study import prepare_fixture
from outcome_poc.storage import read_jsonl


def ready(tmp_path, documents10, monkeypatch):
    from outcome_poc.citation_study import preparation
    from outcome_poc.followup.study import read
    root,plan,_=prepare_fixture(tmp_path,documents10,monkeypatch)
    asset=read(root/'assets.json')['assets']['encoder']
    def encoder(_):
        value=Encoder();value.identity={k:asset[k] for k in ('revision','snapshot_hash')};return value
    monkeypatch.setattr(preparation,'EncoderBackend',encoder)
    preparation.index(root,'diagnosis')
    return root,plan,encoder


def test_factor_requests_pause_resume_close_and_score(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import runtime,scoring
    from outcome_poc.followup.study import read, identity
    root,plan,encoder=ready(tmp_path,documents10,monkeypatch)
    backends=[]
    def factory(_):
        b=Backend();backends.append(b);return b
    assert runtime.run_stage(root,'diagnosis',backend_factory=factory,encoder_factory=encoder,max_jobs=6)['status']=='incomplete'
    jobs=[j for j in read(root/'schedule.json') if j['stage']=='diagnosis']
    seen={}
    for job in jobs[:6]:
        payload,receipt=runtime.completion(root,plan,job)
        paid=read(root/'jobs'/job['job_id']/'paid.json')
        assert paid['request']['decoding_hash']==plan['freeze']['decoding_hash']
        assert (paid['request']['max_context_tokens'],paid['request']['max_new_tokens'],paid['request']['timeout_seconds'])==(8192,256,120)
        messages=json.loads(paid['prompt']);seen[(job['prompt_condition'],job['arm'])]=(messages,payload)
        assert messages[0]['content']==read(root/'prompts.json')[job['prompt_condition']]['system']
        assert payload['calls']==receipt['calls']==1
    for arm in ('2','10','support-documents'):
        b,c=seen['baseline',arm],seen['chain',arm]
        assert b[0][1]==c[0][1] and b[1]['aliases']==c[1]['aliases'] and b[1]['evidence_ids']==c[1]['evidence_ids']
    with pytest.raises(ValueError,match='incomplete'):scoring.score_stage(root,'diagnosis')
    assert not (root/'scores').exists()
    runtime.run_stage(root,'diagnosis',backend_factory=factory,encoder_factory=encoder)
    assert sum(b.calls for b in backends)==386
    before=identity(root/'stages/diagnosis/closed.json')
    with monkeypatch.context() as patch:
        patch.setattr(runtime.subprocess,'run',lambda *a,**kw:pytest.fail('closed stage dispatched native worker'))
        assert runtime.launch(root,'diagnosis')['status']=='closed'
    assert identity(root/'stages/diagnosis/closed.json')==before
    summary=scoring.score_stage(root,'diagnosis')
    scores=identity(root/'scores/diagnosis/scores.jsonl')
    assert summary['assigned_observations']==384
    assert scoring.score_stage(root,'diagnosis')==summary
    assert identity(root/'scores/diagnosis/scores.jsonl')==scores and identity(root/'stages/diagnosis/closed.json')==before
    decision=scoring.admit(root)
    assert decision['decision']=='defer' # Identical authored responses cannot strictly improve.
    with pytest.raises(ValueError,match='admission'):runtime.run_stage(root,'comparison',backend_factory=factory,encoder_factory=encoder)
    receipt=root/'jobs'/jobs[0]['job_id']/'paid.json';receipt.write_text('{}')
    with pytest.raises(ValueError):runtime.validate_closed_stage(root,'diagnosis')


@pytest.mark.parametrize('failure',['timeout','context_overflow','infra_error','cleanup','retrieval','interrupt'])
def test_assigned_failure_paid_partials_abort_permanently(tmp_path,documents10,monkeypatch,failure):
    from outcome_poc.citation_study import runtime
    from outcome_poc.followup.study import read
    from outcome_poc.followup.supervisor import CleanupFailure
    from outcome_poc.retrieval import Retrieval
    root,plan,encoder=ready(tmp_path,documents10,monkeypatch)
    class Fails(Backend):
        def generate(self,*a,**kw):
            result=super().generate(*a,**kw)
            if self.calls>1:
                if failure=='interrupt':raise KeyboardInterrupt()
                if failure=='cleanup':raise CleanupFailure(result,RuntimeError('authored cleanup'))
                return replace(result,status=failure,raw_output='partial authored output')
            return result
    if failure=='retrieval':
        def broken(*a):raise RuntimeError('authored retrieval')
        monkeypatch.setattr(Retrieval,'rank',broken)
    with pytest.raises(BaseException):runtime.run_stage(root,'diagnosis',backend_factory=lambda _:Fails(),encoder_factory=encoder)
    with pytest.raises(RuntimeError,match='aborted|interrupted'):
        runtime.run_stage(root,'diagnosis',backend_factory=lambda _:pytest.fail('must not acquire'),encoder_factory=encoder)
    terminals=list((root/'jobs').glob('*/terminal.json'))
    assert len(terminals)==1
    payload=read(terminals[0])
    assert payload['calls']==(0 if failure=='retrieval' else 1)
    if failure in {'timeout','interrupt'}:assert payload['result']['generated_tokens']==1
    assert not (root/'stages/diagnosis/closed.json').exists()


def test_comparison_denied_before_selector_or_index(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import runtime,preparation,study
    root,plan,encoder=ready(tmp_path,documents10,monkeypatch)
    def forbidden(*a,**kw):pytest.fail('comparison loader reached before admission')
    monkeypatch.setattr(runtime,'selected_jobs',forbidden)
    with pytest.raises(ValueError,match='admission'):runtime.run_stage(root,'comparison')
    monkeypatch.setattr(preparation,'verify_stage',forbidden)
    with pytest.raises(ValueError,match='admission'):preparation.index(root,'comparison')
    with pytest.raises(ValueError,match='admission'):study.selected_jobs(root,'comparison')


@pytest.mark.parametrize('worker',['live','unknown','stopped'])
def test_constructor_failure_quiescence_before_assignment(tmp_path,documents10,monkeypatch,worker):
    import os,psutil,subprocess,sys
    from outcome_poc.citation_study import runtime
    from outcome_poc.followup.study import read,publish
    from outcome_poc.followup.clock import continuous_ns
    root,plan,encoder=ready(tmp_path,documents10,monkeypatch)
    child=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.read()'],stdin=subprocess.PIPE)
    def broken(factory):
        state=read(factory.session_start)
        publish(factory.session_start.parent/f"session-worker-{state['session']}-{child.pid}.json",{
            'session':state['session'],'plan_hash':plan['plan_hash'],'boot_id':state['boot_id'],
            'pid':child.pid,'created':None if worker=='unknown' else psutil.Process(child.pid).create_time(),'continuous_ns':continuous_ns()})
        if worker=='stopped':child.terminate();child.wait(timeout=5)
        raise RuntimeError('authored constructor failure')
    try:
        with pytest.raises(RuntimeError,match='constructor'):runtime.run_stage(root,'diagnosis',backend_factory=broken,encoder_factory=encoder)
        receipt=read(next((root/'stages/diagnosis').glob('session-accounting-*.json')))
        assert (receipt['stop_ns'] is None)==(worker!='stopped')
        if worker!='stopped':
            with pytest.raises(RuntimeError):runtime.run_stage(root,'diagnosis',backend_factory=lambda _:pytest.fail('acquired'),encoder_factory=encoder)
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=5)
        child.stdin.close()
    if worker=='live':
        runtime.run_stage(root,'diagnosis',backend_factory=lambda _:Backend(),encoder_factory=encoder,max_jobs=1)
        report=runtime.report(root)
        assert report['physical_costs']['total_seconds'] is None
        assert read(next((root/'stages/diagnosis').glob('session-reconciliation-*.json')))['stop_ns'] is None


def test_backend_exception_keeps_paid_partial_tokens(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import runtime
    from outcome_poc.followup.study import read
    root,plan,encoder=ready(tmp_path,documents10,monkeypatch)
    class Fails(Backend):
        def generate(self,*a,**kw):
            result=super().generate(*a,**kw)
            if self.calls>1:raise RuntimeError('authored transport raised after progress')
            return result
    with pytest.raises(RuntimeError):runtime.run_stage(root,'diagnosis',backend_factory=lambda _:Fails(),encoder_factory=encoder)
    payload=read(next((root/'jobs').glob('*/terminal.json')))
    assert payload['calls']==1 and payload['result']['raw_output']=='partial authored output'
    assert payload['result']['generated_token_ids']==[3]


def test_admission_requires_every_native_session_probe(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study.scoring import execution_health
    root,plan,encoder=ready(tmp_path,documents10,monkeypatch)
    from outcome_poc.citation_study import runtime
    runtime.run_stage(root,'diagnosis',backend_factory=lambda _:Backend(),encoder_factory=encoder,max_jobs=1)
    jobs=[j for j in runtime.read(root/'schedule.json') if j['stage']=='diagnosis']
    records=[(jobs[0],*runtime.completion(root,plan,jobs[0]))]
    assert not execution_health(root,plan,records)
    launch=runtime.launch_binding(root,'diagnosis',plan)
    runtime.publish(launch/'denial-probe.json',{'network_denied':True,'file_denials':2})
    assert not execution_health(root,plan,records)


def test_spawn_rejects_session_binding_before_acquisition(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import runtime
    root,plan,_=ready(tmp_path,documents10,monkeypatch)
    monkeypatch.setattr(runtime,'install_guard',lambda _:None)
    monkeypatch.setattr(runtime,'probe_denials',lambda _:None)
    import outcome_poc.followup.runtime as historical
    monkeypatch.setattr(historical,'verify_import_origins',lambda _:None)
    monkeypatch.setattr(historical,'probe_denials',lambda _:None)
    path=root/'bad-session.json';runtime.publish(path,{'plan_hash':'wrong','boot_id':plan['freeze']['boot_id'],
        'session':'bad','parent_pid':__import__('os').getpid()})
    def acquire():pytest.fail('model acquisition before checking session binding')
    with pytest.raises(ValueError,match='session'):
        runtime.IsolatedReaderFactory(acquire,root,plan['plan_hash'],path)()

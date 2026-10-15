"""Paired transactions on invented inputs and model doubles only."""
from dataclasses import replace
import pytest
from test_reader_study_preparation import prepared_study
from followup_helpers import Backend
from retrieval_helpers import Encoder
from outcome_poc.followup.study import read, identity


class Counters(Backend):
    peak_mlx_bytes=1
    last_resources={'rss_bytes':1,'peak_mlx_bytes':1}


@pytest.fixture
def ready(prepared_study,monkeypatch):
    from outcome_poc.reader_study import preparation
    root,plan,_=prepared_study
    asset=read(root/'assets.json')['assets']['encoder']
    def encoder(_):
        e=Encoder();e.identity={k:asset[k] for k in ('revision','snapshot_hash')};return e
    monkeypatch.setattr(preparation,'EncoderBackend',encoder)
    preparation.index(root,'development')
    return root,plan,encoder


def test_two_readers_requests_pause_resume_and_closed_verification(ready,monkeypatch):
    from outcome_poc.reader_study import runtime
    root,plan,encoder=ready;backends=[]
    def factory(f):
        b=Counters();backends.append((f,b));return b
    assert runtime.run_stage(root,'development',backend_factory=factory,encoder_factory=encoder,max_jobs=2)['status']=='incomplete'
    result=runtime.run_stage(root,'development',backend_factory=factory,encoder_factory=encoder)
    assert result['status']=='closed' and result['assigned_observations']==96
    closed=runtime.validate_closed_stage(root,'development')
    assert len(closed['records'])==96
    assert {j['reader_id'] for j,p,r in closed['records']}=={'qwen4b-instruct','qwen14b-nonthinking'}
    for job,payload,receipt in closed['records']:
        leaf=runtime.leaf_root(root,'development',job['reader_id'])
        paid=read(leaf/'jobs'/job['job_id']/'paid.json')
        assert paid['request']['model_revision']==read(leaf/'assets.json')['assets']['reader']['revision']
        assert paid['request']['max_new_tokens']==256 and payload['calls']==1
        assert payload['job']['scientific_stage']=='development'
    assert sum(b.calls for f,b in backends)==99 # 96 assigned plus three sessions' warmups
    before=identity(root/'stages/development/closed.json')
    assert runtime.run_stage(root,'development',backend_factory=lambda _:pytest.fail('regenerated'),encoder_factory=encoder)==result
    assert runtime.launch(root,'development')==result
    assert identity(root/'stages/development/closed.json')==before


@pytest.mark.parametrize('failure',['timeout','context_overflow','infra_error','interrupt','parser','truncated'])
def test_attempts_retained_and_fatal_stage_never_retries(ready,failure):
    from outcome_poc.reader_study import runtime
    root,_,encoder=ready
    class Fails(Counters):
        def generate(self,*args,**kwargs):
            r=super().generate(*args,**kwargs)
            if self.calls==1:return r
            if failure=='interrupt':raise KeyboardInterrupt()
            if failure=='parser':return replace(r,raw_output='not json')
            if failure=='truncated':return replace(r,status='budget_exhausted',stop_reason='length')
            return replace(r,status=failure)
    if failure in {'parser','truncated'}:
        result=runtime.run_stage(root,'development',backend_factory=lambda _:Fails(),encoder_factory=encoder)
        assert result['status']=='closed'
        records=runtime.validate_closed_stage(root,'development')['records']
        assert all(p['result']['status']!='ok' for j,p,r in records)
    else:
        with pytest.raises(BaseException):runtime.run_stage(root,'development',backend_factory=lambda _:Fails(),encoder_factory=encoder)
        with pytest.raises(RuntimeError,match='abort|interrupt'):
            runtime.run_stage(root,'development',backend_factory=lambda _:pytest.fail('reacquired'),encoder_factory=encoder)
        terminals=list((root/'leaves/development').glob('*/jobs/*/terminal.json'))
        assert len(terminals)==1 and read(terminals[0])['calls']==1
        assert not (root/'stages/development/closed.json').exists()


@pytest.mark.parametrize('mutation',['extra','missing','request'])
def test_closed_stage_refuses_extra_missing_and_reader_request_swap(ready,mutation):
    from outcome_poc.reader_study import runtime
    root,_,encoder=ready
    runtime.run_stage(root,'development',backend_factory=lambda _:Counters(),encoder_factory=encoder)
    leaf=runtime.leaf_root(root,'development','qwen4b-instruct')
    if mutation=='extra':(leaf/'jobs/unassigned').mkdir()
    elif mutation=='missing':next((leaf/'jobs').glob('*/receipt.json')).unlink()
    else:next((leaf/'jobs').glob('*/paid.json')).write_text('{}')
    with pytest.raises((ValueError,FileNotFoundError)):runtime.validate_closed_stage(root,'development')


def test_confirmation_admission_missing_precedes_input_reads(ready):
    from outcome_poc.reader_study import runtime
    root,_,encoder=ready
    with pytest.raises(ValueError,match='admission'):runtime.run_stage(root,'confirmation',backend_factory=lambda _:pytest.fail('acquired'),encoder_factory=encoder)


def test_failed_constructor_object_is_closed_and_charged(ready):
    from outcome_poc.reader_study import runtime
    root,_,encoder=ready;closed=[]
    class Broken:
        lifecycle=[]
        def __init__(self,f):self.mark=f.reader_id;raise RuntimeError('constructor failed')
        def close(self):closed.append(self.mark)
    with pytest.raises(RuntimeError,match='constructor failed'):runtime.run_stage(root,'development',backend_factory=Broken,encoder_factory=encoder)
    assert len(closed)==1
    receipt=read(next((root/'leaves/development').glob('*/stages/diagnosis/session-accounting-*.json')))
    assert receipt['status']=='failed' and receipt['stop_ns']>=receipt['start_ns']
    runtime.run_stage(root,'development',backend_factory=lambda _:Counters(),encoder_factory=encoder,max_jobs=1)


def test_unknown_worker_identity_permanently_blocks_stage(ready):
    from outcome_poc.reader_study import runtime
    from outcome_poc.followup.study import publish
    root,_,encoder=ready
    def broken(factory):
        state=read(factory.session_start)
        publish(factory.session_start.parent/f"session-worker-{state['session']}-99.json",{
            'session':state['session'],'plan_hash':factory.plan_hash,'boot_id':state['boot_id'],
            'pid':99,'created':None,'continuous_ns':runtime.continuous_ns()})
        raise RuntimeError('authored constructor')
    with pytest.raises(RuntimeError,match='constructor'):runtime.run_stage(root,'development',backend_factory=broken,encoder_factory=encoder)
    with pytest.raises(RuntimeError,match='unknown|abort'):runtime.run_stage(root,'development',backend_factory=lambda _:pytest.fail('acquired'),encoder_factory=encoder)
    receipt=read(next((root/'leaves/development').glob('*/stages/diagnosis/session-accounting-*.json')))
    assert receipt['stop_ns'] is None and receipt['cleanup_error']


def test_retrieval_parity_checked_across_reader_blocks(ready,monkeypatch):
    from outcome_poc.reader_study import runtime
    from outcome_poc.retrieval import Retrieval
    root,_,encoder=ready
    rank=Retrieval.rank;calls=[0]
    def shifted(self,*args):
        calls[0]+=1;rows=rank(self,*args)
        return rows if calls[0]<=48 else rows[1:]+rows[:1]
    monkeypatch.setattr(Retrieval,'rank',shifted)
    with pytest.raises(ValueError,match='parity'):runtime.run_stage(root,'development',backend_factory=lambda _:Counters(),encoder_factory=encoder)
    assert not (root/'stages/development/closed.json').exists()


def test_unknown_reader_directory_refused(ready):
    from outcome_poc.reader_study import runtime
    root,_,encoder=ready
    (root/'leaves/development/unknown-reader').mkdir()
    with pytest.raises(ValueError,match='reader'):runtime.run_stage(root,'development',backend_factory=lambda _:Counters(),encoder_factory=encoder)


def test_report_charges_unreceipted_paid_interruption(ready):
    from outcome_poc.reader_study import runtime,scoring
    root,_,encoder=ready
    class Interrupt(Counters):
        def generate(self,*a,**kw):
            value=super().generate(*a,**kw)
            if self.calls>1:raise KeyboardInterrupt()
            return value
    with pytest.raises(KeyboardInterrupt):runtime.run_stage(root,'development',backend_factory=lambda _:Interrupt(),encoder_factory=encoder)
    stage=scoring.report(root)['stages']['development']
    assert stage['assigned_calls']==1 and stage['terminal_observations']==0
    assert stage['unreceipted_attempts']==1 and stage['assigned_observations']==96


@pytest.mark.parametrize('failure',['timeout','interrupt','abandoned'])
def test_paid_warmup_failure_also_permanently_blocks_resume(ready,failure):
    from outcome_poc.reader_study import runtime
    root,_,encoder=ready
    class Fails(Counters):
        def generate(self,*a,**kw):
            result=super().generate(*a,**kw)
            if failure in {'interrupt','abandoned'}:raise KeyboardInterrupt()
            return replace(result,status='timeout')
    with pytest.raises(BaseException):runtime.run_stage(root,'development',backend_factory=lambda _:Fails(),encoder_factory=encoder)
    if failure=='abandoned':
        for path in (root/'leaves/development').glob('*/stages/diagnosis/aborted.json'):path.unlink()
        for path in (root/'leaves/development').glob('*/stages/diagnosis/session-accounting-*.json'):path.unlink()
    with pytest.raises(RuntimeError,match='abort'):
        runtime.run_stage(root,'development',backend_factory=lambda _:pytest.fail('warmup retried'),encoder_factory=encoder)
    assert len(list((root/'leaves/development').glob('*/stages/diagnosis/warmup-*/paid.json')))==1


def test_failed_warmup_retains_post_attempt_resource_gate(ready):
    from outcome_poc.reader_study import runtime
    from outcome_poc.storage import read_jsonl
    root,_,encoder=ready
    class Fails(Counters):
        def generate(self,*a,**kw):return replace(super().generate(*a,**kw),status='timeout')
    with pytest.raises(RuntimeError):runtime.run_stage(root,'development',backend_factory=lambda _:Fails(),encoder_factory=encoder)
    gates=[r for p in (root/'leaves/development').glob('*/stages/diagnosis/gates-*/gates.jsonl') for r in read_jsonl(p)]
    assert 'after_warmup' in {r['boundary'] for r in gates}

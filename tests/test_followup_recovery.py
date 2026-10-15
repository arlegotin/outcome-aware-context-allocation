"""Authored native admission and abrupt resident-session recovery regressions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


def test_admitted_headroom_runs_with_scores_still_kernel_denied(tmp_path, documents10):
    from followup_helpers import root_fixture, Backend
    from retrieval_helpers import Encoder
    from outcome_poc.followup import runtime
    from outcome_poc.followup.scoring import score_stage
    from outcome_poc.followup.study import identity, publish
    root,plan=root_fixture(tmp_path,documents10)
    for stage in ('calibration','diagnosis'):
        runtime.run_stage(root,stage,backend_factory=lambda _:Backend(),encoder_factory=lambda _:Encoder())
    score_stage(root,'diagnosis')
    publish(root/'headroom-decision.json',{'plan_hash':plan['plan_hash'],'decision':'admit','rationale':'Authored fixture',
        'diagnosis_scores':identity(root/'scores/diagnosis/closed.json')})
    attestation=runtime.attest_headroom(root,plan)
    profile=root/'native.sb';profile.write_text(runtime.sandbox_profile(root,[Path(plan['gold_input']['path'])]))
    code='''
import sys
from pathlib import Path
from followup_helpers import Backend
from retrieval_helpers import Encoder
from outcome_poc.followup.runtime import run_stage
root=Path(sys.argv[1])
try:open(root/'scores/diagnosis/closed.json').read()
except PermissionError:pass
else:raise RuntimeError('scorer store became readable')
result=run_stage(root,'headroom',backend_factory=lambda _:Backend(),encoder_factory=lambda _:Encoder())
assert result['status']=='closed'
'''
    env={**os.environ,'PYTHONPATH':os.pathsep.join([str(Path(__file__).parent),str(Path('src').resolve())]),
         'OUTCOME_FOLLOWUP_ADMISSION_SHA256':attestation['sha256']}
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),sys.executable,'-B','-c',code,str(root)],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    runtime.validate_closed_stage(root,'headroom')
    # A changed decision cannot keep an older attestation valid.
    (root/'headroom-decision.json').write_text('{}')
    with pytest.raises(ValueError):runtime.validate_headroom_admission(root,plan,attestation['sha256'])


def test_abrupt_exit_retains_interrupted_session_bounds_and_both_warmups(tmp_path, documents10):
    from followup_helpers import root_fixture, Backend
    from retrieval_helpers import Encoder
    from outcome_poc.followup import runtime
    from outcome_poc.followup.__main__ import report
    from outcome_poc.followup.study import read
    root,plan=root_fixture(tmp_path,documents10)
    code='''
import os,sys
from pathlib import Path
from followup_helpers import Backend
from retrieval_helpers import Encoder
from outcome_poc.followup.runtime import run_stage
class Abrupt(Backend):
    def generate(self,*args,**kwargs):
        result=super().generate(*args,**kwargs)
        if self.calls==2:os._exit(17)
        return result
run_stage(Path(sys.argv[1]),'calibration',backend_factory=lambda _:Abrupt(),encoder_factory=lambda _:Encoder())
'''
    env={**os.environ,'PYTHONPATH':os.pathsep.join([str(Path(__file__).parent),str(Path('src').resolve())])}
    first=subprocess.run([sys.executable,'-B','-c',code,str(root)],env=env,capture_output=True,text=True)
    assert first.returncode==17,first.stderr
    before=report(root)
    assert before['physical_costs']['total_seconds'] is None
    assert before['physical_costs']['accounting_status']=='unresolved'
    assert before['stages']['calibration']['authored_warmup_calls']==1
    assert before['stages']['calibration']['session_accounting']['open_sessions']==1
    runtime.run_stage(root,'calibration',backend_factory=lambda _:Backend(),encoder_factory=lambda _:Encoder())
    runtime.validate_closed_stage(root,'calibration')
    after=report(root)
    accounting=after['stages']['calibration']['session_accounting']
    assert after['stages']['calibration']['authored_warmup_calls']==2
    assert accounting['sessions']==2 and accounting['open_sessions']==0
    assert accounting['interrupted_sessions']==1 and accounting['exact_seconds'] is None
    assert accounting['lower_seconds']>0 and accounting['upper_seconds']>=accounting['lower_seconds']
    assert after['physical_costs']['total_seconds'] is None
    assert after['physical_costs']['total_lower_seconds']>=accounting['lower_seconds']
    assert after['overall_timing_health']['cost_comparisons']=='unresolved'
    starts=sorted((read(p) for p in (root/'stages/calibration').glob('session-start-*.json')),key=lambda r:r['start_ns'])
    old=read(root/'stages/calibration'/f"session-accounting-{starts[0]['session']}.json")
    current=read(root/'stages/calibration'/f"session-accounting-{starts[1]['session']}.json")
    assert old['stop_ns'] is None and old['stop_upper_bound_ns']<=starts[1]['start_ns']
    assert current['stop_ns'] is not None and old['stop_lower_bound_ns']>old['start_ns']
    assert read(root/'stages/calibration/closed.json')['session_accounting']['interrupted_sessions']==1


def test_reconcile_refuses_a_live_owned_worker_without_killing_it(tmp_path, documents10):
    import psutil
    from followup_helpers import root_fixture
    from outcome_poc.followup import runtime
    from outcome_poc.followup.clock import continuous_ns
    from outcome_poc.followup.study import publish
    root,plan=root_fixture(tmp_path,documents10)
    stage=root/'stages/calibration';stage.mkdir(parents=True)
    state={'session':'authored-worker','plan_hash':plan['plan_hash'],'boot_id':plan['freeze']['boot_id'],
           'start_ns':continuous_ns(),'reader_worker_expected':True}
    publish(stage/'session-start-authored-worker.json',state)
    child=subprocess.Popen([sys.executable,'-B','-c','import sys; sys.stdin.read()'],stdin=subprocess.PIPE)
    try:
        publish(stage/f'session-worker-authored-worker-{child.pid}.json',{'session':state['session'],
            'plan_hash':plan['plan_hash'],'boot_id':state['boot_id'],'pid':child.pid,
            'created':psutil.Process(child.pid).create_time(),'continuous_ns':continuous_ns()})
        with pytest.raises(RuntimeError,match='still alive'):runtime.reconcile_sessions(root,'calibration',plan)
        assert child.poll() is None # Reconciliation must not kill an arbitrary process.
        assert not (stage/'session-accounting-authored-worker.json').exists()
    finally:
        child.terminate();child.wait(timeout=5)
        child.stdin.close()
    accounting=runtime.reconcile_sessions(root,'calibration',plan)
    assert accounting['interrupted_sessions']==1 and accounting['exact_seconds'] is None
    assert accounting['upper_seconds']>=accounting['lower_seconds']>0


@pytest.mark.parametrize('null_creation_identity',[False,True])
def test_unknown_worker_identity_keeps_upper_bound_unknown_and_blocks_resume(tmp_path, documents10, null_creation_identity):
    from followup_helpers import root_fixture
    from outcome_poc.followup import runtime
    from outcome_poc.followup.clock import continuous_ns
    from outcome_poc.followup.study import publish, read
    from outcome_poc.followup.__main__ import report
    root,plan=root_fixture(tmp_path,documents10)
    stage=root/'stages/calibration';stage.mkdir(parents=True)
    publish(stage/'session-start-unknown.json',{'session':'unknown','plan_hash':plan['plan_hash'],
        'boot_id':plan['freeze']['boot_id'],'start_ns':continuous_ns(),'reader_worker_expected':True})
    if null_creation_identity:
        publish(stage/f'session-worker-unknown-{os.getpid()}.json',{'session':'unknown','plan_hash':plan['plan_hash'],
            'boot_id':plan['freeze']['boot_id'],'pid':os.getpid(),'created':None,'continuous_ns':continuous_ns()})
    with pytest.raises(RuntimeError,match='identity unknown'):runtime.reconcile_sessions(root,'calibration',plan)
    receipt=read(stage/'session-accounting-unknown.json')
    assert receipt['stop_ns'] is None and receipt['stop_upper_bound_ns'] is None
    with pytest.raises(RuntimeError,match='identity remains unknown'):runtime.reconcile_sessions(root,'calibration',plan)
    summary=report(root)
    assert summary['physical_costs']['total_seconds'] is None
    assert summary['physical_costs']['total_upper_seconds'] is None


def test_failed_close_preserves_unknown_endpoint_and_guards_resume(tmp_path, documents10):
    import psutil
    from followup_helpers import root_fixture, Backend
    from retrieval_helpers import Encoder
    from outcome_poc.followup import runtime
    from outcome_poc.followup.__main__ import report
    from outcome_poc.followup.clock import continuous_ns
    from outcome_poc.followup.study import publish, read
    root,plan=root_fixture(tmp_path,documents10)
    stage=root/'stages/calibration'
    child=subprocess.Popen([sys.executable,'-B','-c','import sys; sys.stdin.read()'],stdin=subprocess.PIPE)
    acquired=[]
    class CannotClose(Backend):
        def close(self):raise RuntimeError('authored reader cleanup failed')
    def broken_factory(factory):
        state=read(factory.session_start)
        publish(stage/f"session-worker-{state['session']}-{child.pid}.json",{'session':state['session'],
            'plan_hash':plan['plan_hash'],'boot_id':state['boot_id'],'pid':child.pid,
            'created':psutil.Process(child.pid).create_time(),'continuous_ns':continuous_ns()})
        return CannotClose()
    def next_factory(_):acquired.append(True);return Backend()
    try:
        with pytest.raises(RuntimeError,match='cleanup failed'):
            runtime.run_stage(root,'calibration',backend_factory=broken_factory,encoder_factory=lambda _:Encoder(),max_jobs=1)
        original=list(stage.glob('session-accounting-*.json'))[0]
        receipt=read(original)
        assert receipt['stop_ns'] is None and receipt['stop_upper_bound_ns'] is None
        before=report(root)
        assert before['physical_costs']['total_seconds'] is None
        assert before['physical_costs']['total_upper_seconds'] is None
        with pytest.raises(RuntimeError,match='still alive'):
            runtime.run_stage(root,'calibration',backend_factory=next_factory,encoder_factory=lambda _:Encoder())
        assert not acquired and len(list(stage.glob('session-start-*.json')))==1
        assert child.poll() is None
    finally:
        child.terminate();child.wait(timeout=5);child.stdin.close()
    runtime.run_stage(root,'calibration',backend_factory=next_factory,encoder_factory=lambda _:Encoder())
    assert acquired==[True]
    assert read(original)==receipt # The uncertain original is never rewritten as exact.
    recovered=list(stage.glob('session-reconciliation-*.json'))
    assert len(recovered)==1 and read(recovered[0])['stop_ns'] is None
    after=report(root)
    assert after['stages']['calibration']['status']=='closed_unscored'
    assert after['physical_costs']['total_seconds'] is None
    assert after['stages']['calibration']['authored_warmup_calls']==2


def test_finite_receipt_does_not_bypass_owned_worker_guard(tmp_path, documents10):
    import psutil
    from followup_helpers import root_fixture
    from outcome_poc.followup import runtime
    from outcome_poc.followup.clock import continuous_ns
    from outcome_poc.followup.study import publish, identity
    root,plan=root_fixture(tmp_path,documents10)
    stage=root/'stages/calibration';stage.mkdir(parents=True)
    start=continuous_ns();state={'session':'finite','plan_hash':plan['plan_hash'],
        'boot_id':plan['freeze']['boot_id'],'start_ns':start,'reader_worker_expected':True}
    path=stage/'session-start-finite.json';publish(path,state)
    child=subprocess.Popen([sys.executable,'-B','-c','import sys; sys.stdin.read()'],stdin=subprocess.PIPE)
    try:
        publish(stage/f'session-worker-finite-{child.pid}.json',{'session':'finite','plan_hash':plan['plan_hash'],
            'boot_id':state['boot_id'],'pid':child.pid,'created':psutil.Process(child.pid).create_time(),
            'continuous_ns':continuous_ns()})
        stop=continuous_ns()
        publish(stage/'session-accounting-finite.json',{'session':'finite','plan_hash':plan['plan_hash'],
            'boot_id':state['boot_id'],'start_identity':identity(path),'start_ns':start,'stop_ns':stop,
            'stop_lower_bound_ns':stop,'stop_upper_bound_ns':stop,'timing_status':'exact','status':'failed'})
        with pytest.raises(RuntimeError,match='still alive'):runtime.reconcile_sessions(root,'calibration',plan)
        assert child.poll() is None
    finally:
        child.terminate();child.wait(timeout=5);child.stdin.close()


def test_failed_job_with_successful_close_keeps_exact_session_cost(tmp_path, documents10):
    from followup_helpers import root_fixture, Backend
    from retrieval_helpers import Encoder
    from outcome_poc.followup import runtime
    from outcome_poc.followup.__main__ import report
    from outcome_poc.followup.study import read
    root,plan=root_fixture(tmp_path,documents10)
    class JobFails(Backend):
        def synchronize(self):
            if self.calls>=2:raise RuntimeError('authored job synchronization failed')
    with pytest.raises(RuntimeError,match='synchronization failed'):
        runtime.run_stage(root,'calibration',backend_factory=lambda _:JobFails(),encoder_factory=lambda _:Encoder())
    receipt=read(list((root/'stages/calibration').glob('session-accounting-*.json'))[0])
    assert receipt['status']=='failed' and receipt['timing_status']=='exact'
    assert receipt['stop_ns']==receipt['stop_lower_bound_ns']==receipt['stop_upper_bound_ns']
    costs=report(root)['physical_costs']
    assert costs['accounting_status']=='complete' and costs['total_seconds']>0


@pytest.mark.parametrize('startup_cleanup_succeeds',[False,True])
def test_constructor_failure_checks_registered_worker_before_exact_accounting(tmp_path, documents10, startup_cleanup_succeeds):
    import psutil
    from followup_helpers import root_fixture, Backend
    from retrieval_helpers import Encoder
    from outcome_poc.followup import runtime
    from outcome_poc.followup.__main__ import report
    from outcome_poc.followup.clock import continuous_ns
    from outcome_poc.followup.study import publish, read
    root,plan=root_fixture(tmp_path,documents10)
    stage=root/'stages/calibration'
    child=subprocess.Popen([sys.executable,'-B','-c','import sys; sys.stdin.read()'],stdin=subprocess.PIPE)
    acquired=[]
    def constructor(factory):
        state=read(factory.session_start)
        publish(stage/f"session-worker-{state['session']}-{child.pid}.json",{'session':state['session'],
            'plan_hash':plan['plan_hash'],'boot_id':state['boot_id'],'pid':child.pid,
            'created':psutil.Process(child.pid).create_time(),'continuous_ns':continuous_ns()})
        if startup_cleanup_succeeds:child.terminate();child.wait(timeout=5)
        raise RuntimeError('authored constructor failed before backend assignment')
    def next_factory(_):acquired.append(True);return Backend()
    try:
        with pytest.raises(RuntimeError,match='constructor failed'):
            runtime.run_stage(root,'calibration',backend_factory=constructor,encoder_factory=lambda _:Encoder())
        original=list(stage.glob('session-accounting-*.json'))[0]
        receipt=read(original)
        costs=report(root)['physical_costs']
        assert not list((root/'jobs').glob('*/started.json'))
        assert not list(stage.glob('warmup-*/paid.json'))
        if startup_cleanup_succeeds:
            assert receipt['timing_status']=='exact' and receipt['status']=='failed'
            assert receipt['stop_ns']==receipt['stop_lower_bound_ns']==receipt['stop_upper_bound_ns']
            assert costs['accounting_status']=='complete' and costs['total_seconds']>0
        else:
            assert receipt['stop_ns'] is None and receipt['stop_upper_bound_ns'] is None
            assert costs['accounting_status']=='unresolved' and costs['total_seconds'] is None
            assert costs['total_upper_seconds'] is None
            with pytest.raises(RuntimeError,match='still alive'):
                runtime.run_stage(root,'calibration',backend_factory=next_factory,encoder_factory=lambda _:Encoder())
            assert not acquired and child.poll() is None
            assert len(list(stage.glob('session-start-*.json')))==1
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=5)
        child.stdin.close()
    if not startup_cleanup_succeeds:
        runtime.run_stage(root,'calibration',backend_factory=next_factory,encoder_factory=lambda _:Encoder())
        assert acquired==[True] and read(original)==receipt
        reconciliation=read(list(stage.glob('session-reconciliation-*.json'))[0])
        assert reconciliation['stop_ns'] is None and reconciliation['stop_upper_bound_ns']>=receipt['stop_lower_bound_ns']
        assert report(root)['physical_costs']['total_seconds'] is None

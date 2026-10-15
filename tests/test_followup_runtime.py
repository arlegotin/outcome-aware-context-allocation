import importlib
import json
import subprocess
import sys
from pathlib import Path
import pytest


def test_serving_imports_do_not_load_gold():
    result=subprocess.run([sys.executable,'-c',"import sys; import outcome_poc.followup.runtime; assert not any(n in sys.modules for n in ('outcome_poc.scoring','outcome_poc.data','outcome_poc.followup.scoring'))"],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_real_native_sandbox_denial(tmp_path):
    from outcome_poc.followup.runtime import sandbox_profile, probe_denials
    secret=tmp_path/'gold'; secret.write_text('authored secret')
    profile=tmp_path/'native.sb'; profile.write_text(sandbox_profile(tmp_path,[secret]))
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),sys.executable,'-c',
        'from outcome_poc.followup.runtime import probe_denials; import sys; probe_denials([sys.argv[1]])',str(secret)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_interrupted_resume_closed_stage_and_corrupt_receipt(tmp_path, documents10):
    from followup_helpers import root_fixture, Backend
    from outcome_poc.followup.runtime import execute_job, close_stage, validate_closed_stage, completion
    from outcome_poc.followup.study import read
    from outcome_poc.data_runtime import DocumentStore, load_tasks
    from outcome_poc.retrieval import Retrieval
    from retrieval_helpers import Encoder
    root,plan=root_fixture(tmp_path,documents10)
    docs=DocumentStore(root/'documents.jsonl');encoder=Encoder()
    retrieval=Retrieval(root/'index-setup/index',docs,encoder)
    task=load_tasks(root/'tasks.jsonl','fit_extension')[0]
    jobs=[j for j in read(root/'schedule.json') if j['stage']=='calibration']
    backend=Backend(interrupt=True)
    with pytest.raises(KeyboardInterrupt):execute_job(root,plan,jobs[0],task,docs,retrieval,backend)
    assert (root/'jobs'/jobs[0]['job_id']/'progress.json').exists()
    backend=Backend()
    result,receipt=execute_job(root,plan,jobs[0],task,docs,retrieval,backend)
    assert backend.calls==0
    assert result['result']['raw_output']=='partial authored output'
    assert result['result']['status']=='infra_error' and receipt['calls']==1
    with pytest.raises(ValueError,match='incomplete'):close_stage(root,plan,'calibration')
    for job in jobs[1:]:execute_job(root,plan,job,task,docs,retrieval,backend)
    assert backend.calls==5
    assert len(encoder.texts)==6 # interrupted paid call + five fresh query encodings
    close_stage(root,plan,'calibration');validate_closed_stage(root,'calibration')
    from outcome_poc.followup.scoring import score_stage
    summary=score_stage(root,'calibration')
    assert summary['assigned_observations']==6 and summary['assigned_unique_questions']==1
    assert summary['arms']['2']['observations']==2
    assert score_stage(root,'calibration')==summary
    payload=root/'jobs'/jobs[-1]['job_id']/'terminal.json'
    payload.write_text('{}')
    with pytest.raises(ValueError,match='sealed file changed'):completion(root,plan,jobs[-1])
    with pytest.raises(ValueError):score_stage(root,'calibration')


def test_cleanup_failure_preserves_paid_partial_then_aborts(tmp_path, documents10):
    from followup_helpers import root_fixture, Backend
    from outcome_poc.followup.runtime import execute_job, completion
    from outcome_poc.followup.supervisor import CleanupFailure
    from outcome_poc.followup.study import read
    from outcome_poc.data_runtime import DocumentStore, load_tasks
    from outcome_poc.retrieval import Retrieval
    from outcome_poc.schemas import ReaderResult
    from retrieval_helpers import Encoder
    root,plan=root_fixture(tmp_path,documents10)
    job=read(root/'schedule.json')[0];task=load_tasks(root/'tasks.jsonl','fit_extension')[0]
    docs=DocumentStore(root/'documents.jsonl')
    class Failed(Backend):
        def generate(self,*args,**kwargs):
            raise CleanupFailure(ReaderResult('paid partial',None,[],'timeout',2,1,[1,2],[3],'timeout'),RuntimeError('cannot reap'))
    with pytest.raises(RuntimeError,match='cleanup failed'):
        execute_job(root,plan,job,task,docs,Retrieval(root/'index-setup/index',docs,Encoder()),Failed())
    payload,receipt=completion(root,plan,job)
    assert payload['result']['raw_output']=='paid partial'
    assert payload['result']['generated_tokens']==1 and payload['cleanup_error']=='RuntimeError: cannot reap'
    assert receipt['calls']==1


def test_post_generation_sync_failure_preserves_result(tmp_path, documents10):
    from followup_helpers import root_fixture, Backend
    from outcome_poc.followup.runtime import execute_job
    from outcome_poc.followup.study import read
    from outcome_poc.data_runtime import DocumentStore, load_tasks
    from outcome_poc.retrieval import Retrieval
    from retrieval_helpers import Encoder
    root,plan=root_fixture(tmp_path,documents10)
    docs=DocumentStore(root/'documents.jsonl');task=load_tasks(root/'tasks.jsonl','fit_extension')[0]
    class Failed(Backend):
        def synchronize(self):
            if self.calls:raise TimeoutError('post sync')
    job=read(root/'schedule.json')[0]
    with pytest.raises(RuntimeError,match='synchronization failed'):
        execute_job(root,plan,job,task,docs,Retrieval(root/'index-setup/index',docs,Encoder()),Failed())
    payload,_=__import__('outcome_poc.followup.runtime',fromlist=['completion']).completion(root,plan,job)
    assert payload['result']['raw_output'] and payload['result']['generated_tokens']==1
    assert payload['result']['status']=='infra_error'


def test_closed_stage_required_before_gold_open(tmp_path, documents10):
    from followup_helpers import root_fixture
    from outcome_poc.followup.scoring import score_stage
    root,plan=root_fixture(tmp_path,documents10)
    # Incomplete stage must fail even when Gold is unavailable.
    (root.parent/'fixture-gold.jsonl').unlink()
    with pytest.raises(ValueError,match='incomplete'):score_stage(root,'calibration')


def test_receipt_cannot_omit_payload_hash_or_change_job(tmp_path, documents10):
    from followup_helpers import root_fixture, Backend
    from outcome_poc.followup.runtime import execute_job, completion
    from outcome_poc.followup.study import read
    from outcome_poc.data_runtime import DocumentStore, load_tasks
    from outcome_poc.retrieval import Retrieval
    from outcome_poc.storage import atomic_json
    from retrieval_helpers import Encoder
    root,plan=root_fixture(tmp_path,documents10)
    docs=DocumentStore(root/'documents.jsonl');task=load_tasks(root/'tasks.jsonl','fit_extension')[0]
    job=read(root/'schedule.json')[0]
    execute_job(root,plan,job,task,docs,Retrieval(root/'index-setup/index',docs,Encoder()),Backend())
    path=root/'jobs'/job['job_id']/'receipt.json';receipt=read(path)
    receipt['files'].pop('terminal.json');atomic_json(path,receipt)
    with pytest.raises(ValueError):completion(root,plan,job)


def test_stage_engine_resumes_without_answer_replay_and_rejects_reboot(tmp_path, documents10, monkeypatch):
    from followup_helpers import root_fixture, Backend
    from outcome_poc.followup import runtime
    from retrieval_helpers import Encoder
    root,plan=root_fixture(tmp_path,documents10)
    backends=[]
    def factory(_):
        backend=Backend();backends.append(backend);return backend
    runtime.run_stage(root,'calibration',backend_factory=factory,encoder_factory=lambda _:Encoder(),max_jobs=2)
    assert not (root/'stages/calibration/closed.json').exists()
    runtime.run_stage(root,'calibration',backend_factory=factory,encoder_factory=lambda _:Encoder())
    assert sum(b.calls for b in backends)==8
    assert len(list((root/'stages/calibration').glob('warmup-*/result.json')))==2
    runtime.validate_closed_stage(root,'calibration')
    monkeypatch.setattr(runtime,'boot_identity',lambda:'another-boot')
    with pytest.raises(ValueError,match='cross-boot'):runtime.run_stage(root,'calibration',backend_factory=factory,encoder_factory=lambda _:Encoder())


def test_scoring_recomputes_on_each_fresh_dispatch(tmp_path, documents10, monkeypatch):
    from followup_helpers import root_fixture, Backend
    from outcome_poc.followup import runtime, scoring
    from retrieval_helpers import Encoder
    root,plan=root_fixture(tmp_path,documents10)
    runtime.run_stage(root,'calibration',backend_factory=lambda _:Backend(),encoder_factory=lambda _:Encoder())
    scoring.score_stage(root,'calibration')
    # A changed scoring computation must conflict with immutable scores, even on resume.
    original=scoring.score_answer
    monkeypatch.setattr(scoring,'score_answer',lambda p,g:{**original(p,g),'em':1-original(p,g)['em']})
    with pytest.raises(ValueError,match='immutable'):scoring.score_stage(root,'calibration')


def test_native_profile_denies_aliases_projections_and_old_parent(tmp_path):
    from outcome_poc.followup.runtime import sandbox_profile
    parent=tmp_path/'old-and-new';parent.mkdir()
    root=parent/'new';root.mkdir()
    secret=parent/'old-gold.jsonl';secret.write_text('authored secret')
    alias=tmp_path/'alias';alias.symlink_to(secret)
    projection=root/'forbidden.gold.jsonl';projection.write_text('authored projection')
    good=root/'annotation-free.json';good.write_text('{}')
    profile=root/'native.sb';profile.write_text(sandbox_profile(root,[parent]))
    code='from outcome_poc.followup.runtime import probe_denials; import sys; probe_denials(sys.argv[2:]); assert open(sys.argv[1]).read()=="{}"'
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),sys.executable,'-B','-c',code,
        str(good),str(secret),str(alias),str(projection)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_report_keeps_incomplete_denominators_and_no_raw_prose(tmp_path, documents10):
    from followup_helpers import root_fixture, Backend
    from outcome_poc.followup import runtime, scoring
    from retrieval_helpers import Encoder
    root,plan=root_fixture(tmp_path,documents10)
    runtime.run_stage(root,'calibration',backend_factory=lambda _:Backend(),encoder_factory=lambda _:Encoder())
    scoring.score_stage(root,'calibration')
    result=subprocess.run([sys.executable,'-B','-m','outcome_poc.followup','report','--root',str(root)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout)
    assert report['stages']['calibration']['authored_warmup_calls']==1
    assert report['stages']['diagnosis']['status']=='incomplete'
    assert report['stages']['diagnosis']['assigned_observations']==4
    assert 'summary' not in report['stages']['diagnosis']
    assert 'violet' not in result.stdout and 'Authored question' not in result.stdout


def test_reader_factory_installs_guard_in_native_child(tmp_path):
    import os
    import shutil
    from outcome_poc.followup.runtime import sandbox_profile
    root=tmp_path/'new';root.mkdir()
    package=Path(__file__).resolve().parents[1]/'src/outcome_poc'
    shutil.copytree(package,root/'source/src/outcome_poc',ignore=shutil.ignore_patterns('__pycache__'))
    secret=tmp_path/'gold';secret.write_text('authored secret')
    (root/'plan.json').write_text(json.dumps({'plan_hash':'authored','freeze':{'denied_probes':[str(secret)]}}))
    profile=root/'native.sb';profile.write_text(sandbox_profile(root,[secret]))
    (root/'source/src/authored_guard.py').write_text("""
import importlib
class Tokenizer:
    chat_template='authored guarded reader'
class Backend:
    tokenizer=Tokenizer()
    def synchronize(self):pass
class Probe:
    def __call__(self):
        for name in ('outcome_poc.scoring','outcome_poc.followup.scoring','outcome_poc.data'):
            try:importlib.import_module(name)
            except ImportError:pass
            else:raise RuntimeError('Gold import was allowed')
        return Backend()
""")
    code='''
import sys
from pathlib import Path
from authored_guard import Probe
from outcome_poc.followup.runtime import IsolatedReaderFactory
from outcome_poc.followup.supervisor import ContinuousBackend
with ContinuousBackend(IsolatedReaderFactory(Probe(),Path(sys.argv[1]),'authored'),startup_timeout=10.) as backend:
    backend.synchronize()
    assert backend.worker_pid is not None
    assert backend.tokenizer.chat_template=='authored guarded reader'
'''
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),sys.executable,'-B','-c',code,str(root)],
        env={**os.environ,'PYTHONPATH':str(root/'source/src')},capture_output=True,text=True)
    assert result.returncode==0,result.stderr

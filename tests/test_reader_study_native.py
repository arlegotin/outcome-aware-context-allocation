"""Actual macOS kernel and spawn boundary with exclusively authored bytes."""
import os
from pathlib import Path
import subprocess
import sys
import pytest
from test_reader_study_preparation import fixture_config
from outcome_poc.storage import content_hash
from outcome_poc.followup.study import read


@pytest.fixture
def native_ready(tmp_path,documents10,monkeypatch):
    from outcome_poc.reader_study import preparation
    from retrieval_helpers import Encoder
    config,path,prepared=fixture_config(tmp_path,documents10)
    raw=tmp_path/'relocated-raw/authored.json';raw.parent.mkdir();raw.write_text('authored raw fixture')
    history=tmp_path/'history/outcome.json';history.parent.mkdir();history.write_text('authored historical fixture')
    monkeypatch.setattr(preparation,'EXPECTED_ELIGIBLE_COUNT',130)
    monkeypatch.setattr(preparation,'EXPECTED_ELIGIBLE_HASH',content_hash([f't-{i:04}' for i in range(992,1122)]))
    monkeypatch.setattr(preparation,'EXPECTED_PREPARED_FINGERPRINT','authored')
    monkeypatch.setattr(preparation,'validate_metadata_inventory',lambda c:None)
    monkeypatch.setattr(preparation,'verify_strong_manifest',lambda *args:None)
    monkeypatch.setattr(preparation,'discover_denial_locations',lambda r:{'version':1,'registries':[],
        'conventional_denied':[str(prepared),str(history.parent)],'raw_locations':[str(raw.parent)],
        'declared_raw_files':[str(raw)],'raw_probes':[str(raw)],'gold_probes':[str(prepared/'gold/gold.jsonl')]})
    root=tmp_path/'run';preparation.prepare(root,path)
    asset=read(root/'assets.json')['assets']['encoder']
    def encoder(_):
        e=Encoder();e.identity={k:asset[k] for k in ('revision','snapshot_hash')};return e
    monkeypatch.setattr(preparation,'EncoderBackend',encoder);preparation.index(root,'development')
    return root


SCRIPT='''
from dataclasses import replace
from pathlib import Path
import json,os,sys
import numpy as np
from outcome_poc.reader_study import runtime,study
from outcome_poc.followup.supervisor import ContinuousBackend
from outcome_poc.generation import NativeReaderFactory
from outcome_poc.reader_probe.profile import ProfileFactory
from outcome_poc.schemas import ReaderResult
import outcome_poc.retrieval as retrieval
class Tokenizer:
    chat_template='authored tokenizer'
    def apply_chat_template(self,messages,**kwargs):return json.dumps(messages)
    def encode(self,text,**kwargs):return list(text.encode())
class Fake:
    tokenizer=Tokenizer()
    def __init__(self,revision):self.revision=revision
    def synchronize(self):pass
    def resource_counters(self):return {'peak_mlx_bytes':1,'rss_bytes':1}
    def generate(self,prompt,request,**kwargs):
        ids=self.tokenizer.encode(prompt)
        import re
        text=json.loads(prompt)[1]['content']
        match=re.search(r'(D\\d+) \\| Invented lantern 0\\n',text)
        raw=json.dumps({'answer':'authored violet','citations':[{'doc_id':match[1] if match else 'D999','sentence_index':999 if self.revision.startswith('50d4') else 0}]})
        self.progress_callback(raw,ids,[1])
        return ReaderResult(raw,None,[],'ok',len(ids),1,ids,[1],'stop')
def assert_denied(root):
    plan=study.read(root/'plan.json')
    names=runtime.denial_paths(plan,'development',probes=True)+list(plan['freeze']['source_files'])
    for name in names:
        try:Path(name).read_bytes()
        except PermissionError:continue
        raise AssertionError('readable before acquisition: '+name)
class Old(NativeReaderFactory):
    def __call__(self):
        root=Path(os.environ['OUTCOME_READER_STUDY_SERVING']);assert_denied(root)
        assert list((root/'leaves/development').glob('*/stages/diagnosis/worker-probes-*.json'))
        if os.environ.get('STARTUP_ONCE')=='1' and not (root/'startup-failure').exists():
            (root/'startup-failure').write_text('authored startup failure before paid work')
            raise RuntimeError('authored startup-only failure')
        (root/('acquired-'+self.config['revision'])).write_text('after worker denials')
        return Fake(self.config['revision'])
class Strong(ProfileFactory):
    def __call__(self):return Old(self.snapshot,self.config)()
class Spawn(ContinuousBackend):
    def __init__(self,factory):
        cls=Strong if factory.reader_id=='qwen14b-nonthinking' else Old
        inner=cls(factory.factory.snapshot,factory.factory.config)
        if os.environ.get('TAMPER_PROFILE')=='1':inner=replace(inner,config={**inner.config,'max_new_tokens':255})
        super().__init__(replace(factory,factory=inner))
from authored_retrieval import Encoder as TestEncoder
class Encoder(TestEncoder):
    def __init__(self,path):
        super().__init__()
        root=Path(os.environ['OUTCOME_READER_STUDY_SERVING'])
        a=study.read(root/'assets.json')['assets']['encoder']
        self.identity={k:a[k] for k in ('revision','snapshot_hash')}
    def encode(self,texts,query=False):
        out=np.zeros((len(texts),384),dtype=np.float32);out[:,0]=1;return out
if __name__=='__main__':
    root=Path(sys.argv[1]);plan=study.verify(root,stage='development')
    runtime.isolation(root,'development',plan);assert_denied(root)
    runtime.ContinuousBackend=Spawn;retrieval.EncoderBackend=Encoder
    runtime.native_entry(root,'development')
'''


def install_child(root,monkeypatch,*,tamper=False,startup_once=False):
    from outcome_poc.reader_study import runtime
    script=root/'authored-coordinator.py';script.write_text(SCRIPT)
    (root/'authored_retrieval.py').write_bytes(Path('tests/retrieval_helpers.py').read_bytes())
    original=subprocess.run
    def child(command,**kwargs):
        if tamper:kwargs['env']['TAMPER_PROFILE']='1'
        if startup_once:kwargs['env']['STARTUP_ONCE']='1'
        return original(command[:3]+[sys.executable,'-B',str(script),str(root)],timeout=80,**kwargs)
    monkeypatch.setattr(runtime.subprocess,'run',child)


def test_native_coordinator_worker_denials_and_reader_receipts(native_ready,monkeypatch):
    from outcome_poc.reader_study import runtime,scoring
    root=native_ready;install_child(root,monkeypatch)
    result=runtime.launch(root,'development')
    assert result['status']=='closed'
    assert len(list(root.glob('acquired-*')))==2
    closed=runtime.validate_closed_stage(root,'development')
    assert scoring.execution_health(root,closed['plan'],closed['records'])
    before=read(root/'stages/development/closed.json')
    assert runtime.launch(root,'development')==result
    assert read(root/'stages/development/closed.json')==before


def test_native_reader_profile_swap_stops_before_acquisition(native_ready,monkeypatch):
    from outcome_poc.reader_study import runtime
    root=native_ready;install_child(root,monkeypatch,tamper=True)
    with pytest.raises(RuntimeError,match='native stage failed'):runtime.launch(root,'development')
    assert not list(root.glob('acquired-*'))
    assert not list((root/'leaves/development').glob('*/jobs/*/paid.json'))
    errors='\n'.join(p.read_text() for p in (root/'stages/development').glob('launch-*/stderr.txt'))
    assert 'factory/profile mismatch' in errors


def test_current_checkout_import_origin_is_rejected(native_ready):
    root=native_ready
    process=subprocess.run([sys.executable,'-c',
        'from pathlib import Path;from outcome_poc.reader_study.runtime import native_entry;native_entry(Path(__import__("sys").argv[1]),"development")',str(root)],capture_output=True,text=True)
    assert process.returncode!=0 and 'non-snapshot import' in process.stderr
    assert not list(root.glob('acquired-*'))


def test_inherited_writer_lock_covers_child_streams_and_closure(native_ready,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    import threading
    from outcome_poc.reader_study import runtime
    root=native_ready;install_child(root,monkeypatch)
    actual=runtime.subprocess.run;ownership=runtime._launch_ownership
    ready=threading.Event();waiter=threading.Event();release=threading.Event();children=[]
    def child(command,**kwargs):
        children.append(command);ready.set();assert release.wait(20)
        return actual(command,**kwargs)
    @contextmanager
    def owned(path):
        if threading.current_thread().name.startswith('waiting'):waiter.set()
        with ownership(path) as fd:yield fd
    monkeypatch.setattr(runtime.subprocess,'run',child);monkeypatch.setattr(runtime,'_launch_ownership',owned)
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='active') as a, ThreadPoolExecutor(max_workers=1,thread_name_prefix='waiting') as b:
        first=a.submit(runtime.launch,root,'development');assert ready.wait(10)
        second=b.submit(runtime.launch,root,'development')
        try:assert waiter.wait(10) and not second.done()
        finally:release.set()
        assert first.result(timeout=80)==second.result(timeout=80)
    assert len(children)==1
    assert len(list((root/'stages/development').glob('launch-*')))==1
    runtime.validate_closed_stage(root,'development')


def test_native_admission_unlocks_complete_confirmation_and_seals_handoff(native_ready,monkeypatch):
    from outcome_poc.reader_study import runtime,scoring,preparation
    from test_reader_study_runtime import Counters
    from retrieval_helpers import Encoder
    root=native_ready
    with monkeypatch.context() as patch:
        install_child(root,patch);runtime.launch(root,'development')
    scoring.score_stage(root,'development')
    decision=scoring.admit(root)
    assert decision['decision']=='admit',decision
    runtime.validate_admission(root)
    preparation.index(root,'confirmation')
    asset=read(root/'assets.json')['assets']['encoder']
    def encoder(_):
        value=Encoder();value.identity={k:asset[k] for k in ('revision','snapshot_hash')};return value
    result=runtime.run_stage(root,'confirmation',backend_factory=lambda _:Counters(),encoder_factory=encoder)
    assert result['assigned_observations']==512
    assert len(scoring.score_stage(root,'confirmation'))==512
    summary=read(root/'scores/confirmation/summary.json')
    assert summary['population_N']==88587 and summary['assigned_unique_questions']==128
    path=root/'confirmation-admission.json';path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='closure|admission'):runtime.validate_closed_stage(root,'confirmation')


def test_exact_startup_only_failure_can_resume_without_erasing_failed_cost(native_ready,monkeypatch):
    from outcome_poc.reader_study import runtime,scoring
    root=native_ready
    with monkeypatch.context() as patch:
        install_child(root,patch,startup_once=True)
        with pytest.raises(RuntimeError,match='native stage failed'):runtime.launch(root,'development')
        assert not list((root/'leaves/development').glob('*/jobs/*/paid.json'))
        assert not list((root/'leaves/development').glob('*/stages/diagnosis/warmup-*/paid.json'))
        failed=list((root/'leaves/development').glob('*/stages/diagnosis/session-accounting-*.json'))
        assert len(failed)==1 and read(failed[0])['status']=='failed' and read(failed[0])['stop_ns'] is not None
        saved=failed[0].read_bytes()
        runtime.launch(root,'development')
    scoring.score_stage(root,'development')
    assert scoring.admit(root)['decision']=='admit'
    assert failed[0].read_bytes()==saved
    report=scoring.report(root)
    assert sum(v['sessions'] for v in report['stages']['development']['session_accounting'].values())==3

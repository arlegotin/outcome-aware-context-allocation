"""Actual Seatbelt and spawned fake backend; no model acquisition."""
import os
from pathlib import Path
import subprocess
import sys
from test_reader_probe_study import prepared


def test_real_native_spawn_checks_denials_before_acquisition(prepared):
    script=prepared/'authored-native.py'
    script.write_text('''
from dataclasses import replace
import json, sys
from pathlib import Path
from outcome_poc.reader_probe import runtime, study
from outcome_poc.followup.supervisor import ContinuousBackend
from outcome_poc.schemas import ReaderResult
# Only asset verification is replaced: this fixture has no real model files.
study.verify_manifest=lambda *args:None
class Tokenizer:
    chat_template='authored character tokenizer'
    def apply_chat_template(self,messages,**kwargs):return json.dumps(messages)
    def encode(self,text,**kwargs):return list(text.encode())
class Fake:
    tokenizer=Tokenizer()
    def synchronize(self):pass
    def resource_counters(self):return {'peak_mlx_bytes':1,'rss_bytes':1}
    def generate(self,prompt,request,**kwargs):
        ids=self.tokenizer.encode(prompt)
        raw='{"answer":"LARK-27","citations":[{"doc_id":"D0","sentence_index":0}]}'
        self.progress_callback(raw,ids,[1,2])
        return ReaderResult(raw,None,[],'ok',len(ids),2,ids,[1,2],'stop')
def actual_denials(root):
    checkout=root.parents[2]
    for path in (checkout/'relocated/raw-assets/authored.json',
                 checkout/'data/prepared/reproduction/gold/gold.jsonl',
                 checkout/'models/pinned/data/fallback.json'):
        try:path.read_bytes()
        except PermissionError:continue
        raise AssertionError('actual raw/Gold file readable before acquisition: '+str(path))
class Acquire:
    def __init__(self,root):self.root=root
    def __call__(self):
        actual_denials(self.root)
        assert list((self.root/'stages/preflight').glob('worker-probes-*.json'))
        (self.root/'acquisition-marker').write_text('after worker denials')
        return Fake()
class Spawn(ContinuousBackend):
    def __init__(self,factory):super().__init__(replace(factory,factory=Acquire(factory.root)))
if __name__=='__main__':
    root=Path(sys.argv[1])
    plan=study.verify(root)
    assert runtime.isolation(root,plan)['network_denied']
    actual_denials(root)
    result=runtime.run(root,backend_factory=Spawn)
    assert result['status']=='passed',result
    assert (root/'acquisition-marker').exists()
    assert len(list((root/'stages/preflight').glob('worker-probes-*.json')))==1
    assert runtime.run(root,backend_factory=Spawn)==result
''')
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(prepared/'native.sb'),sys.executable,
        '-B',str(script),str(prepared)],cwd=prepared/'source',
        env={**os.environ,'PYTHONPATH':str(prepared/'source/src'),'PYTHONDONTWRITEBYTECODE':'1'},
        capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stderr


def test_unexpected_checkout_import_rejected_before_acquisition(prepared):
    result=subprocess.run([sys.executable,'-B','-c',
        'from pathlib import Path; from outcome_poc.reader_probe.runtime import native_entry; '
        f'native_entry(Path({str(prepared)!r}))'],capture_output=True,text=True)
    assert result.returncode!=0
    assert 'non-snapshot import' in result.stderr
    assert not (prepared/'stages').exists()


def test_paused_second_launcher_cannot_mutate_completed_closure(prepared,monkeypatch):
    """Actual child plus concurrent callers reproduces the review's interleaving."""
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from outcome_poc.reader_probe import runtime,study
    script=prepared/'authored-coordinator.py'
    script.write_text('''
from pathlib import Path
import sys
from outcome_poc.reader_probe import runtime,study
from test_reader_probe_runtime import Backend
study.verify_manifest=lambda *args:None
runtime.resource_check=lambda _: {'passed':True}
result=runtime.run(Path(sys.argv[1]),backend_factory=Backend)
assert result['status']=='passed',result
''')
    initial_check=threading.Event()
    resume=threading.Event()
    original_exists=Path.exists
    original_run=subprocess.run
    paused=[]
    children=[]
    def exists(path):
        value=original_exists(path)
        caller=sys._getframe(1).f_code.co_name
        if (path==prepared/'closed.json' and caller=='launch' and not value and
                threading.current_thread().name.startswith('second-launcher') and not paused):
            paused.append(True)
            initial_check.set()
            assert resume.wait(20)
        return value
    def child(command,**kwargs):
        children.append(command)
        kwargs['env']={**kwargs['env'],'PYTHONPATH':os.pathsep.join(
            [str(prepared/'source/src'),str(Path('tests').resolve())])}
        return original_run(command[:3]+[sys.executable,'-B',str(script),str(prepared)],timeout=20,**kwargs)
    monkeypatch.setattr(Path,'exists',exists)
    monkeypatch.setattr(runtime.subprocess,'run',child)
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='second-launcher') as pool:
        second=pool.submit(runtime.launch,prepared)
        assert initial_check.wait(10)
        try:
            first=runtime.launch(prepared)
            sealed=runtime._outputs(prepared)
        finally:
            resume.set()
        assert second.result(timeout=20)==first
    assert first['status']=='passed'
    assert len(children)==1
    assert runtime._outputs(prepared)==sealed
    study.verify(prepared)


def test_active_launcher_serializes_second_caller_without_extra_child(prepared,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    import threading
    from outcome_poc.reader_probe import runtime,study
    script=prepared/'authored-active-coordinator.py'
    script.write_text('''
from pathlib import Path
import sys
from outcome_poc.reader_probe import runtime,study
from test_reader_probe_runtime import Backend
study.verify_manifest=lambda *args:None
runtime.resource_check=lambda _: {'passed':True}
assert runtime.run(Path(sys.argv[1]),backend_factory=Backend)['status']=='passed'
''')
    child_ready=threading.Event()
    waiter_ready=threading.Event()
    release_child=threading.Event()
    original_run=subprocess.run
    original_ownership=runtime._launch_ownership
    children=[]
    @contextmanager
    def ownership(root):
        if threading.current_thread().name.startswith('second-active'):
            waiter_ready.set()
        with original_ownership(root) as descriptor:
            yield descriptor
    def child(command,**kwargs):
        children.append(command)
        child_ready.set()
        assert release_child.wait(20)
        kwargs['env']={**kwargs['env'],'PYTHONPATH':os.pathsep.join(
            [str(prepared/'source/src'),str(Path('tests').resolve())])}
        return original_run(command[:3]+[sys.executable,'-B',str(script),str(prepared)],timeout=20,**kwargs)
    monkeypatch.setattr(runtime,'_launch_ownership',ownership)
    monkeypatch.setattr(runtime.subprocess,'run',child)
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='first-active') as first_pool, \
            ThreadPoolExecutor(max_workers=1,thread_name_prefix='second-active') as second_pool:
        first=first_pool.submit(runtime.launch,prepared)
        assert child_ready.wait(10)
        second=second_pool.submit(runtime.launch,prepared)
        try:
            assert waiter_ready.wait(10)
            assert not second.done()
        finally:
            release_child.set()
        assert first.result(timeout=20)==second.result(timeout=20)
    assert len(children)==1
    assert len(list((prepared/'launches').iterdir()))==1
    study.verify(prepared)

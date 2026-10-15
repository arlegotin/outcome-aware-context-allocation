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
class Acquire:
    def __init__(self,root):self.root=root
    def __call__(self):
        assert list((self.root/'stages/preflight').glob('worker-probes-*.json'))
        (self.root/'acquisition-marker').write_text('after worker denials')
        return Fake()
class Spawn(ContinuousBackend):
    def __init__(self,factory):super().__init__(replace(factory,factory=Acquire(factory.root)))
if __name__=='__main__':
    root=Path(sys.argv[1])
    plan=study.verify(root)
    assert runtime.isolation(root,plan)['network_denied']
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

"""Actual macOS Seatbelt and spawn through the new entry, authored fixtures only."""
import os
from pathlib import Path
import subprocess
import sys
from test_citation_runtime import ready


def test_new_native_entry_sqlite_gold_raw_comparison_and_spawn_import_denials(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import runtime
    from outcome_poc.followup.study import read
    root,plan,encoder=ready(tmp_path,documents10,monkeypatch)
    derived=root/'stages/comparison/index-setup/index';derived.mkdir(parents=True)
    (derived/'metadata.sqlite3').write_text('authored comparison evidence')
    launch=runtime.launch_binding(root,'diagnosis',plan)
    script=root/'native-authored-test.py'
    script.write_text('''
import importlib,os,sys
from pathlib import Path
from followup_helpers import Backend
from retrieval_helpers import Encoder
from outcome_poc.citation_study import runtime
from outcome_poc.followup.study import read

class ProbeFactory:
    def __call__(self):
        for name in runtime.DENIED_MODULES:
            try:importlib.import_module(name)
            except ImportError:pass
            else:raise RuntimeError('spawn annotation import allowed: '+name)
        # Check succeeds before a model would be acquired; this authored marker is deliberate.
        Path(os.environ['OUTCOME_CITATION_SERVING'],'worker-guard-passed').write_text('passed before acquisition')
        raise RuntimeError('authored stop before model acquisition')

if __name__=='__main__':
    root=Path(sys.argv[1]);plan=read(root/'plan.json')
    original=runtime.run_stage
    def authored(root,stage):
        for name in runtime.DENIED_MODULES:
            try:importlib.import_module(name)
            except ImportError:pass
            else:raise RuntimeError('coordinator annotation import allowed: '+name)
        paths=[Path(plan['gold_input']['path']),Path(plan['gold_input']['path']).parent.parent/'tasks.jsonl',
            root/'inputs/comparison/tasks.jsonl',root/'stages/comparison/index-setup/index/metadata.sqlite3']
        for path in paths:
            try:path.read_bytes()
            except PermissionError:pass
            else:raise RuntimeError('native evidence/Gold denial failed '+str(path))
        import socket
        sock=socket.socket()
        try:
            try:sock.connect(('127.0.0.1',9))
            except PermissionError:pass
            else:raise RuntimeError('native network allowed')
        finally:sock.close()
        def encoder(_):
            e=Encoder();e.identity={k:read(root/'assets.json')['assets']['encoder'][k] for k in ('revision','snapshot_hash')};return e
        result=original(root,stage,backend_factory=lambda _:Backend(),encoder_factory=encoder,max_jobs=6)
        assert result['status']=='incomplete'
        assert len(list((root/'jobs').glob('*/receipt.json')))==6 # Real SQLite retrieval through new entry.
        session=next((root/'stages/diagnosis').glob('session-start-*.json'))
        factory=runtime.IsolatedReaderFactory(ProbeFactory(),root,plan['plan_hash'],session,'diagnosis')
        try:runtime.ContinuousBackend(factory,startup_timeout=10.)
        except RuntimeError:pass
        else:raise RuntimeError('authored spawn unexpectedly acquired model')
        assert (root/'worker-guard-passed').read_text()=='passed before acquisition'
        return result
    runtime.run_stage=authored
    runtime.native_entry(root,'diagnosis')
''')
    env={**os.environ,'PYTHONPATH':os.pathsep.join([str(root/'source/src'),str(Path('tests').resolve())]),
        'PYTHONDONTWRITEBYTECODE':'1','OUTCOME_CITATION_SERVING':str(root),'OUTCOME_CITATION_LAUNCH':str(launch)}
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(launch/'native.sb'),sys.executable,'-B',str(script),str(root)],
        env=env,cwd=root/'source',capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stderr
    assert read(launch/'denial-probe.json')['file_denials']==2


def test_entry_rejects_already_loaded_scorer_before_native_model_start(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import runtime
    root,plan,_=ready(tmp_path,documents10,monkeypatch)
    code='''
import sys
from pathlib import Path
from outcome_poc.citation_study import scoring,runtime
try:runtime.native_entry(Path(sys.argv[1]),'diagnosis')
except RuntimeError as e:assert 'already imported' in str(e)
else:raise AssertionError('preloaded Gold scorer accepted')
'''
    env={**os.environ,'PYTHONPATH':str(root/'source/src')}
    result=subprocess.run([sys.executable,'-B','-c',code,str(root)],env=env,cwd=root/'source',capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_closed_native_diagnosis_admits_comparison_without_score_store_access(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import runtime,scoring,preparation
    from outcome_poc.followup.study import read,identity
    root,plan,encoder=ready(tmp_path,documents10,monkeypatch)
    launch=runtime.launch_binding(root,'diagnosis',plan)
    script=root/'native-positive-test.py'
    script.write_text('''
import json,re,sys
from dataclasses import replace
from pathlib import Path
from followup_helpers import Backend
from retrieval_helpers import Encoder
from outcome_poc.citation_study import runtime
from outcome_poc.followup.study import read
root=Path(sys.argv[1]);stage=sys.argv[2]
class Positive(Backend):
    def generate(self,prompt,*a,**kw):
        result=super().generate(prompt,*a,**kw)
        messages=json.loads(prompt);user=messages[1]['content']
        match=re.search(r'(D[0-9]+) \\| Invented lantern 0\\n',user)
        citations=[{'doc_id':match.group(1),'sentence_index':0}] if match and 'Include the supplied sentences' in messages[0]['content'] else []
        return replace(result,raw_output=json.dumps({'answer':'authored violet','citations':citations}))
def encoder(_):
    e=Encoder();e.identity={k:read(root/'assets.json')['assets']['encoder'][k] for k in ('revision','snapshot_hash')};return e
original=runtime.run_stage
runtime.run_stage=lambda root,stage:original(root,stage,backend_factory=lambda _:Positive(),encoder_factory=encoder,max_jobs=1 if stage=='comparison' else None)
if stage=='comparison':
    try:(root/'scores/diagnosis/scores.jsonl').read_bytes()
    except PermissionError:pass
    else:raise AssertionError('comparison can read scored diagnosis')
runtime.native_entry(root,stage)
''')
    def invoke(stage,launch,admission=None):
        env={**os.environ,'PYTHONPATH':os.pathsep.join([str(root/'source/src'),str(Path('tests').resolve())]),
            'PYTHONDONTWRITEBYTECODE':'1','OUTCOME_CITATION_SERVING':str(root),'OUTCOME_CITATION_LAUNCH':str(launch)}
        if admission:env['OUTCOME_CITATION_ADMISSION_SHA256']=admission['sha256']
        result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(launch/'native.sb'),sys.executable,'-B',str(script),str(root),stage],
            env=env,cwd=root/'source',capture_output=True,text=True,timeout=120)
        assert result.returncode==0,result.stderr
    invoke('diagnosis',launch)
    summary=scoring.score_stage(root,'diagnosis')
    assert summary['cells']['chain/10']['counts']['joint_em']==64
    assert summary['cells']['baseline/10']['counts']['joint_em']==0
    decision=scoring.admit(root)
    assert decision['healthy'] and decision['decision']=='admit'
    preparation.index(root,'comparison')
    launch=runtime.launch_binding(root,'comparison',plan)
    invoke('comparison',launch,identity(root/'comparison-admission.json'))
    assert runtime.report(root)['stages']['comparison']['terminal_observations']==1
    # A changed privileged handoff cannot retain its older launch hash.
    old=identity(root/'comparison-admission.json')['sha256']
    (root/'comparison-admission.json').write_text('{}')
    import pytest
    with pytest.raises(ValueError,match='admission'):runtime.validate_admission(root,plan,old)


def test_native_entry_rejects_resealed_weakened_profile_before_work(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import runtime
    from outcome_poc.storage import canonical_bytes
    root,plan,_=ready(tmp_path,documents10,monkeypatch)
    launch=runtime.launch_binding(root,'diagnosis',plan)
    profile=launch/'native.sb';profile.write_text(profile.read_text()+'(allow file-write*)\n')
    binding=runtime.read(launch/'binding.json');binding['profile']=runtime.identity(profile)
    (launch/'binding.json').write_bytes(canonical_bytes(binding))
    code='''
import sys
from pathlib import Path
from outcome_poc.citation_study import runtime
runtime.run_stage=lambda *a:(_ for _ in ()).throw(AssertionError('work reached with weakened profile'))
try:runtime.native_entry(Path(sys.argv[1]),'diagnosis')
except ValueError as e:assert 'profile' in str(e)
else:raise AssertionError('weakened profile accepted')
'''
    env={**os.environ,'PYTHONPATH':str(root/'source/src'),'OUTCOME_CITATION_LAUNCH':str(launch)}
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),sys.executable,'-B','-c',code,str(root)],
        env=env,cwd=root/'source',capture_output=True,text=True)
    assert result.returncode==0,result.stderr

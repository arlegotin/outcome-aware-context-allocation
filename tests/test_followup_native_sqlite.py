"""Actual SQLite/ranking integration under the production denied-parent profile."""
import json
import os
from pathlib import Path
import subprocess
import sys


def authored_native_root(tmp_path, documents):
    from followup_helpers import root_fixture
    from outcome_poc.followup.runtime import sandbox_profile
    historical=tmp_path/'artifacts';runs=historical/'runs';runs.mkdir(parents=True)
    root,plan=root_fixture(runs,documents)
    previous=historical/'previous-run';previous.mkdir()
    (previous/'predictions.jsonl').write_text('authored historical output')
    raw=tmp_path/'raw';raw.mkdir();(raw/'benchmark.json').write_text('authored raw secret')
    (root/'scores').mkdir();(root/'scores/private.json').write_text('authored score secret')
    alias=tmp_path/'gold-alias';alias.symlink_to(Path(plan['gold_input']['path']))
    denied=[str(raw/'benchmark.json'),plan['gold_input']['path'],str(alias),
            str(previous/'predictions.jsonl'),str(root/'scores/private.json')]
    profile=root/'native.sb';profile.write_text(sandbox_profile(root,[historical,raw]))
    return root,profile,denied


def native(root, profile, code, denied):
    env={**os.environ,'PYTHONPATH':os.pathsep.join([str(Path(__file__).parent),str(Path('src').resolve())]),
         'PYTHONDONTWRITEBYTECODE':'1'}
    return subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),sys.executable,'-B','-c',code,
        str(root),json.dumps(denied)],env=env,capture_output=True,text=True)


def test_native_stage_ranks_real_sqlite_beneath_denied_historical_parent(tmp_path, documents10):
    root,profile,denied=authored_native_root(tmp_path,documents10)
    code='''
import json,os,sqlite3,sys
from pathlib import Path
from followup_helpers import Backend
from retrieval_helpers import Encoder
from outcome_poc.followup.runtime import run_stage,probe_denials
root=Path(sys.argv[1]);probe_denials(json.loads(sys.argv[2]))
# Root bytes alone were readable even under the defective profile.
assert (root/'index-setup/index/metadata.sqlite3').read_bytes()
with sqlite3.connect('file:'+str(root/'index-setup/index/metadata.sqlite3')+'?mode=ro',uri=True) as db:
    assert db.execute('SELECT count(*) FROM documents').fetchone()[0]==10
encoders=[];backends=[]
def encoder_factory(_):
    encoder=Encoder();encoders.append(encoder);return encoder
def backend_factory(_):
    backend=Backend();backends.append(backend);return backend
result=run_stage(root,'calibration',backend_factory=backend_factory,encoder_factory=encoder_factory)
assert result['status']=='closed'
assert len(encoders[0].texts)==6 # Every assigned arm re-encodes and opens the real SQLite index.
assert backends[0].calls==7 # Six authored cohort calls plus one separate authored warm-up.
for directory in (root.parent,root.parent.parent):
    directory.lstat()
    try:os.listdir(directory)
    except PermissionError:pass
    else:raise RuntimeError('historical parent directory contents became readable')
probe_denials(json.loads(sys.argv[2]))
for name in json.loads(sys.argv[2]):
    try:Path(name).stat()
    except PermissionError:pass
    else:raise RuntimeError('secret file metadata became readable: '+name)
'''
    result=native(root,profile,code,denied)
    assert result.returncode==0,result.stderr


def test_native_retrieval_database_failure_aborts_after_first_zero_call_job(tmp_path, documents10):
    root,profile,denied=authored_native_root(tmp_path,documents10)
    # Reintroduce precisely the observed metadata denial as an authored fault.
    with profile.open('a') as stream:
        for parent in (root.parent,root.parent.parent):
            stream.write(f'(deny file-read-metadata (literal {json.dumps(str(parent))}))\n')
    code='''
import json,sys
from pathlib import Path
from followup_helpers import Backend
from retrieval_helpers import Encoder
from outcome_poc.followup.runtime import run_stage,probe_denials
from outcome_poc.followup.study import read
root=Path(sys.argv[1]);probe_denials(json.loads(sys.argv[2]))
backends=[]
def backend_factory(_):
    backend=Backend();backends.append(backend);return backend
try:run_stage(root,'calibration',backend_factory=backend_factory,encoder_factory=lambda _:Encoder())
except RuntimeError as error:
    assert 'retrieval failed' in str(error),str(error)
else:raise RuntimeError('retrieval infrastructure failure silently consumed the schedule')
receipts=list((root/'jobs').glob('*/receipt.json'))
assert len(receipts)==1
receipt=read(receipts[0]);payload=read(receipts[0].parent/'terminal.json')
assert receipt['calls']==0 and payload['result']['status']=='infra_error'
assert payload['result']['stop_reason']=='OperationalError: unable to open database file'
assert backends[0].calls==1 # The only generation is the separate authored warm-up.
assert not (root/'stages/calibration/closed.json').exists()
assert len(list((root/'jobs').glob('*/started.json')))==1
probe_denials(json.loads(sys.argv[2]))
'''
    result=native(root,profile,code,denied)
    assert result.returncode==0,result.stderr

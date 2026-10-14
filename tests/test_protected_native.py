from pathlib import Path
import json

import pytest

from outcome_poc import protected
from outcome_poc.data_runtime import DocumentStore
from outcome_poc.storage import append_jsonl, content_hash
from test_protected_run import protected_fixture
from retrieval_helpers import Encoder, document


def test_sample_projection_excludes_unassigned_documents_and_resumes(tmp_path):
    frozen,runtime,_=protected_fixture(tmp_path)
    append_jsonl(runtime.document_path,document('Unassigned',['No serving access.']))
    assert hasattr(protected,'selected_documents'), 'selected document projection missing'
    selected=protected.selected_documents(frozen,runtime.document_path)
    expected={d for t in frozen['sample']['tasks'] for d in t['candidate_ids']}
    assert set(selected.offsets)==expected
    assert len(selected.offsets)==10
    assert protected.selected_documents(frozen,runtime.document_path).path==selected.path


def test_index_realization_binds_algorithm_documents_and_completed_bytes(tmp_path):
    frozen,runtime,_=protected_fixture(tmp_path)
    frozen['methods']['retrieval'].update(index_dir=str(tmp_path/'index'),reuse_indexes=[],
        operational_realization_path=str(Path(frozen['run_dir'])/'index-realization.json'))
    # Operational helper consumes the already verified protocol. This synthetic
    # helper fixture does not re-freeze any real benchmark protocol.
    assert hasattr(protected,'realize_index'), 'index operational seal missing'
    docs=DocumentStore(runtime.document_path);encoder=Encoder()
    manifest=protected.realize_index(frozen,docs,encoder)
    seal=json.loads(Path(frozen['methods']['retrieval']['operational_realization_path']).read_text())
    assert seal['scientific_digests']==frozen['digests']
    assert seal['document_ids_hash']==frozen['sample']['document_ids_hash']
    assert seal['manifest_hash']==content_hash(manifest)
    count=len(encoder.texts)
    assert protected.realize_index(frozen,docs,encoder)==manifest
    assert len(encoder.texts)==count
    (tmp_path/'index'/'vectors.f32').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum|digest|completion'):
        protected.realize_index(frozen,docs,encoder)


def test_native_sandbox_denies_raw_gold_projection_and_network():
    assert hasattr(protected,'sandbox_profile'), 'native sandbox boundary missing'
    profile=protected.sandbox_profile(Path('/project'),Path('data/prepared'))
    for text in ('deny network','data/prepared/gold','models/pinned/data','[.]gold[.]jsonl'):
        assert text in profile


def test_snapshot_copies_exact_source_and_refuses_changed_bytes(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    source=Path('src/outcome_poc');source.mkdir(parents=True)
    (source/'protected.py').write_text('bound source')
    from outcome_poc.protocol import file_hash
    p={'protocol_hash':'hash','run_dir':str(tmp_path/'run'),
       'source':{'commit':'a'*40,'sha256':{'src/outcome_poc/protected.py':file_hash(source/'protected.py')}}}
    assert hasattr(protected,'capture_snapshot'), 'immutable execution snapshot missing'
    snapshot=protected.capture_snapshot(p)
    assert (snapshot/'src/outcome_poc/protected.py').read_text()=='bound source'
    assert protected.capture_snapshot(p)==snapshot
    (snapshot/'src/outcome_poc/protected.py').write_text('changed')
    with pytest.raises(ValueError,match='snapshot|checksum'):
        protected.capture_snapshot(p)


def test_real_native_profile_denies_protected_annotation_and_network_paths(tmp_path):
    import subprocess
    import sys
    if sys.platform!='darwin': pytest.skip('macOS sandbox boundary')
    cwd=tmp_path
    paths=[cwd/'data/prepared/gold/gold.jsonl',cwd/'models/pinned/data/raw.json',cwd/'private/scores.gold.jsonl']
    for path in paths: path.parent.mkdir(parents=True,exist_ok=True);path.write_text('denied')
    profile=tmp_path/'native.sb';profile.write_text(protected.sandbox_profile(cwd,Path('data/prepared')))
    script="import errno,socket,sys\nfor p in sys.argv[1:]:\n try: open(p).read()\n except PermissionError: pass\n else: raise AssertionError('annotation accessible')\ns=socket.socket();s.settimeout(.1)\ntry:s.connect(('1.1.1.1',443))\nexcept OSError as e: assert e.errno in (errno.EPERM,errno.EACCES)\nelse: raise AssertionError('network accessible')"
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),sys.executable,'-c',script,*map(str,paths)],capture_output=True,text=True)
    if 'sandbox_apply: Operation not permitted' in result.stderr: pytest.skip('outer sandbox disallows nested sandbox')
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('index_failure',[False,True])
def test_native_worker_fixture_executes_projected_index_and_complete_closed_schedule(tmp_path,monkeypatch,index_failure):
    """Exercise native orchestration with only model/kernel boundaries injected."""
    from types import SimpleNamespace
    from outcome_poc import environment,generation,retrieval,train,protocol as protocol_module
    from outcome_poc.storage import atomic_json
    frozen,runtime,_=protected_fixture(tmp_path)
    root=Path(frozen['run_dir']);root.mkdir()
    prepared=tmp_path/'prepared';prepared.mkdir()
    (prepared/'documents.jsonl').write_bytes(runtime.document_path.read_bytes())
    frozen['methods']['retrieval'].update(prepared_dir=str(prepared),index_dir=str(tmp_path/'index'),reuse_indexes=[],
        operational_realization_path=str(root/'index-realization.json'))
    assets=tmp_path/'asset-manifest.json'
    atomic_json(assets,{'assets':{'reader':{'local_path':'unused-fixture-reader'},'encoder':{'local_path':'unused-fixture-encoder'}}})
    frozen['artifact_sha256'][str(assets)]=protocol_module.file_hash(assets)
    frozen['digests']['methods']=content_hash(frozen['methods'])
    atomic_json(Path(frozen['output_dir'])/'methods.json',frozen['methods'])
    frozen['protocol_hash']=protocol_module._hash_protocol(frozen)
    atomic_json(Path(frozen['output_dir'])/'protocol.json',frozen)
    profile=root/'native.sb';profile.write_text('fixture injected kernel boundary')
    plan=root/'launch-plan.json'
    atomic_json(plan,{'protocol_path':str(Path(frozen['output_dir'])/'protocol.json'),
        'protocol_hash':frozen['protocol_hash'],'sandbox_sha256':protocol_module.file_hash(profile)})
    monkeypatch.setattr(environment,'discover',lambda path:{'native_supported':True,'resource_gate':{'passed':True},'physical_memory_bytes':32*1024**3})
    encoder=Encoder()
    if index_failure:
        def fail(texts): raise RuntimeError('injected index failure')
        encoder.encode=fail
    monkeypatch.setattr(retrieval,'EncoderBackend',lambda path:encoder)
    monkeypatch.setattr(train,'load_gate',lambda manifest:runtime.models[manifest['family']])
    class Resident:
        def __init__(self,factory):pass
        def __enter__(self):
            runtime.reader.backend.lifecycle=[]
            runtime.reader.backend.last_resources={'peak_mlx_bytes':1024}
            return runtime.reader.backend
        def __exit__(self,*args):pass
    monkeypatch.setattr(generation,'SupervisedBackend',Resident)
    import subprocess
    old=subprocess.run
    def kernel_probe(cmd,*args,**kwargs):
        if len(cmd)>2 and cmd[1]=='-c':return SimpleNamespace(stdout=json.dumps({'gold':True,'raw':True,'projection':True,'network':True}))
        return old(cmd,*args,**kwargs)
    monkeypatch.setattr(subprocess,'run',kernel_probe)
    if index_failure:
        with pytest.raises(RuntimeError,match='injected'): protected.native_main(plan,1)
        from outcome_poc.storage import read_jsonl
        costs=list(read_jsonl(root/'shared-costs.jsonl'))
        assert any(r['role']=='offline' and r['elapsed_seconds']>0 for r in costs)
        assert (root/'native-1.failure.json').exists()
        assert not (root/'protected-attempt.started.json').exists()
        return
    result=protected.native_main(plan,1)
    assert result['status']=='closed' and result['assigned_jobs']==36
    assert result['resource_gate']['passed']
    assert (root/'protected-run.closed.json').is_file()
    costs=list(__import__('outcome_poc.storage',fromlist=['read_jsonl']).read_jsonl(root/'shared-costs.jsonl'))
    assert [r['role'] for r in costs]==['cold_setup','offline','cold_setup']
    assert all(costs[i]['stop_ns']==costs[i+1]['start_ns'] for i in range(2))

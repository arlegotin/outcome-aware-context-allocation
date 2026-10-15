"""Independent diagnostic protocol and receipts, entirely synthetic."""
from copy import deepcopy
from dataclasses import asdict,replace
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from outcome_poc.schemas import Task,RankedDocument,ReaderResult,GoldRecord
from outcome_poc.storage import append_jsonl,atomic_json,content_hash,read_jsonl,canonical_bytes
from outcome_poc.data_runtime import DocumentStore
from outcome_poc.protocol import file_hash,freeze
from retrieval_helpers import document
from test_protocol import inputs
from test_prompt import Tokenizer


def api():
    assert importlib.util.find_spec('outcome_poc.transfer_runtime'),'independent transfer implementation missing'
    return importlib.import_module('outcome_poc.transfer_runtime')


def fixture(tmp_path):
    config=inputs(tmp_path)
    docs=[document('Fixture '+str(i),['Evidence '+str(i)+'.']) for i in range(12)]
    protected=[Task('query'+str(i),'protected','Fixture?', [d.doc_id for d in docs[:10]]) for i in range(50)]
    dev=[Task('development','pilot','Development?',[d.doc_id for d in docs[2:]])]
    prepared=tmp_path/'prepared';prepared.mkdir()
    for d in docs:append_jsonl(prepared/'documents.jsonl',d)
    for t in [*dev,*protected]:append_jsonl(prepared/'tasks.jsonl',t)
    config.update(tasks=protected,population_ids=[t.task_id for t in protected],n=40)
    config['development']['forecast']['available_seconds']=1000000.
    config['development']['retrieval']={'prepared_dir':str(prepared),'reuse_indexes':[],'index_dir':str(tmp_path/'primary-index')}
    primary=freeze(config)
    assert 'deadline_utc' not in primary
    source=tmp_path/'fixture-source.py';source.write_text('synthetic source')
    sources={'commit':'a'*40,'sha256':{str(source):file_hash(source)}}
    manifest=api().prospective_manifest(primary,dev,protected,sources,tmp_path/'transfer',fixture=True)
    root=Path(manifest['root']);root.mkdir()
    atomic_json(root/'manifest.json',manifest)
    for doc in sorted(docs,key=lambda d:d.doc_id):append_jsonl(root/'corpus-documents.jsonl',doc)
    store=DocumentStore(root/'corpus-documents.jsonl')
    class Retrieval:
        last_query={};last_timings={}
        def rank(self,question,candidates):
            # A winner absent from the query's original supplied packet.
            result=[RankedDocument(d.doc_id,1.-i*.01,i,d.character_count,len(d.sentences),d.title)
                    for i,d in enumerate([docs[11],*docs[:9]])]
            self.last_query={'retained_ids_hash':'fixture','truncated':False}
            self.last_timings={'full_seconds':.1,'window_count':12,'document_count':12}
            return result
    class Backend:
        tokenizer=Tokenizer();lifecycle=[];last_resources={};worker_pid=123
        def synchronize(self):pass
        def generate(self,prompt,request,*,rendered):
            raw='{"answer":"fixture","citations":[{"doc_id":"D0","sentence_index":0}]}'
            return ReaderResult(raw,None,[],'ok',2,1,[1,2],[3],'stop')
    class Model:
        def predict(self,values):return np.zeros(len(values))
    models={name:Model() for name in primary['methods']['models']}
    runtime=(Retrieval(),store,Backend(),models)
    return manifest,primary,docs,runtime


def test_fixed_32_queries_are_hash_selected_without_outcomes_and_full_union(tmp_path):
    m,p,docs,_=fixture(tmp_path)
    assert len(m['queries'])==32 and len(m['jobs'])==96
    expected=sorted(p['sample']['task_ids'],key=lambda tid:(content_hash([271828,tid,'task15-pooled-transfer']),tid))[:32]
    assert [t['task_id'] for t in m['queries']]==expected
    assert set(m['corpus']['document_ids'])=={d.doc_id for d in docs}
    assert m['corpus']['protected_population_count']==50
    assert m['policies']=={'A':p['methods']['selected']['A'],'B':p['methods']['selected']['B'],'FIXED10':p['methods']['anchor']}
    assert m['primary_protocol_hash']==p['protocol_hash'] and m['selection_reads_scores'] is False
    assert m['scope']=='nested exploratory pooled transfer; not confirmation'
    assert m['deadline_utc']==p['methods']['deadline_utc']


def test_manifest_rejects_resizing_or_changed_reader_and_snapshot_bytes(tmp_path):
    m,p,_,_=fixture(tmp_path)
    altered=deepcopy(m);altered['reader']['timeout_seconds']=999.
    altered['manifest_hash']=content_hash({k:v for k,v in altered.items() if k!='manifest_hash'})
    with pytest.raises(ValueError):api().verify_manifest(altered)
    bad=deepcopy(m);bad['queries'].pop();bad['manifest_hash']=content_hash({k:v for k,v in bad.items() if k!='manifest_hash'})
    with pytest.raises(ValueError):api().verify_manifest(bad)
    source=next(iter(m['source']['sha256']));Path(source).write_text('changed')
    with pytest.raises(ValueError,match='source'):api().verify_manifest(m)


def test_independent_pipeline_closes_every_fresh_job_and_seals_outside_primary(tmp_path):
    m,p,_,runtime=fixture(tmp_path);before=deepcopy(p)
    result=api().run_diagnostic(m,*runtime)
    assert result['status']=='closed' and result['assigned_jobs']==96
    predictions,costs,bindings=api().validate_transfer(m)
    assert len(predictions)==96 and len({v.job_id for v in predictions})==96
    assert all(v.run_id=='task15-pooled-transfer' and v.protocol_hash==m['manifest_hash'] for v in predictions)
    assert all(v.evidence_ids[0] not in m['queries'][0]['candidate_ids'] for v in predictions)
    assert all(costs[v.job_id]['total_serving_seconds']>0 for v in predictions)
    assert before==p and bindings
    assert len(list(Path(m['root']).glob('jobs/*/attempt-1/paid-1.finished.json')))==96
    with pytest.raises(ValueError,match='already|attempt|closed'):api().run_diagnostic(m,*runtime)


def test_infrastructure_failure_remains_incomplete_and_cannot_open_gold(tmp_path,monkeypatch):
    m,_,_,runtime=fixture(tmp_path)
    runtime[2].generate=lambda *a,**k:ReaderResult('',None,[],'infra_error',0,0,[],[],'fixture infrastructure')
    result=api().run_diagnostic(m,*runtime)
    assert result['status']=='incomplete' and result['assigned_jobs']==96 and result['completed_jobs']==1
    assert not (Path(m['root'])/'transfer.closed.json').exists()
    with pytest.raises((ValueError,FileNotFoundError)):api().score_transfer(m)


def test_timeout_keeps_denominator_and_recovery_is_owned_by_current_job(tmp_path):
    m,_,_,runtime=fixture(tmp_path);backend=runtime[2];original=backend.generate;state={'dead':False,'recoveries':0}
    def generate(*args,**kwargs):
        result=original(*args,**kwargs);state['dead']=True
        return replace(result,status='timeout',stop_reason='fixture timeout')
    def synchronize():
        if state['dead']:state['recoveries']+=1;state['dead']=False
    backend.generate=generate;backend.synchronize=synchronize
    api().run_diagnostic(m,*runtime)
    predictions,_,_=api().validate_transfer(m)
    assert len(predictions)==96 and all(v.status=='timeout' for v in predictions)
    assert state['recoveries']==96


def test_assigned_only_scorer_verifies_closure_before_synthetic_gold_and_reports_recall(tmp_path):
    m,_,docs,runtime=fixture(tmp_path)
    prepared=Path(m['prepared_dir']);gold=prepared/'gold/gold.jsonl'
    for task in m['queries']:append_jsonl(gold,GoldRecord(task['task_id'],'fixture',[(docs[11].title,0)]))
    append_jsonl(gold,GoldRecord('unassigned','ignored',[('Unassigned',0)]))
    atomic_json(prepared/'manifest.json',{'files':{'gold/gold.jsonl':{'sha256':file_hash(gold)}}})
    api().run_diagnostic(m,*runtime)
    result=api().score_transfer(m)
    assert result['assigned_unique_tasks']==32 and result['assigned_jobs']==96
    assert result['supporting_document_recall_at10']==1.
    assert result['supporting_fact_title_coverage_at10']==1.
    assert len(list(read_jsonl(Path(m['root'])/'scoring/scores.gold.jsonl')))==32
    assert result['families']['A']['assigned_tasks']==32
    assert api().score_transfer(m)==result
    # Mutation must reject even if an already produced scoring output exists.
    next(Path(m['root']).glob('jobs/*/attempt-1/paid-1.finished.json')).write_text('{}')
    with pytest.raises(ValueError):api().score_transfer(m)


def test_index_failures_preserve_paths_costs_and_do_not_look_completed(tmp_path,monkeypatch):
    m,_,_,runtime=fixture(tmp_path)
    from outcome_poc import retrieval
    def broken(documents,encoder,path,**kwargs):
        path.mkdir(parents=True);(path/'partial').write_text('partial')
        raise RuntimeError('synthetic index failure')
    monkeypatch.setattr(retrieval,'build_index',broken)
    with pytest.raises(RuntimeError):api().build_pooled_index(m,runtime[1],object())
    root=Path(m['root'])
    assert (root/'index/attempt-1/partial').exists()
    records=list(read_jsonl(root/'index-attempts.jsonl'))
    assert len(records)==1 and records[0]['status']=='failed' and records[0]['elapsed_seconds']>0
    assert not (root/'pilot.closed.json').exists()


def test_native_diagnostic_refuses_fixture_manifest_without_accessing_assets(tmp_path):
    m,_,_,_=fixture(tmp_path)
    with pytest.raises(ValueError,match='fixture'):api().launch(m,'pilot')


def test_source_snapshot_refuses_mutation_and_is_not_primary_snapshot(tmp_path):
    m,_,_,_=fixture(tmp_path)
    snapshot=api().capture_snapshot(m)
    assert snapshot.is_relative_to(Path(m['root']))
    exported=next(p for p in snapshot.rglob('*') if p.is_file() and p.name!='snapshot.json')
    exported.write_text('tampered')
    with pytest.raises(ValueError,match='snapshot|source'):api().capture_snapshot(m)


def test_measured_pilot_and_remaining_report_reserve_gate_whole_diagnostic(tmp_path,monkeypatch):
    m,_,_,_=fixture(tmp_path);root=Path(m['root'])
    parent_attempt(m,'preparation-1','prospective-preparation')
    atomic_json(root/'pilot.closed.json',{'manifest_hash':m['manifest_hash'],'hashes':{},'parent_attempt':'launch-pilot-1'})
    parent_attempt(m,'launch-pilot-1','pilot')
    result=api().authorize_execution(m,forecast_seconds=300.)
    assert result['assigned_jobs']==96 and result['queries']==32
    assert result['pilot_closure_hash']==file_hash(root/'pilot.closed.json')
    from datetime import datetime,timezone
    class Late(datetime):
        @classmethod
        def now(cls,tz=None):return datetime(2100,1,1,tzinfo=timezone.utc)
    monkeypatch.setattr(api(),'datetime',Late)
    with pytest.raises(ValueError,match='reserve|budget|deadline'):api().authorize_execution(m,forecast_seconds=300.)


def test_real_os_profile_denies_synthetic_gold_raw_and_network(tmp_path):
    import subprocess,sys
    if sys.platform!='darwin':pytest.skip('macOS denial profile')
    denied=[tmp_path/'prepared/gold/gold.jsonl',tmp_path/'private/scores.gold.jsonl',tmp_path/'models/pinned/data/raw.json']
    for path in denied:path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic denied data')
    profile=tmp_path/'profile.sb';profile.write_text(api().diagnostic_profile(tmp_path,tmp_path/'prepared'))
    script="import errno,socket,sys\nfor p in sys.argv[1:]:\n try:open(p).read()\n except PermissionError:pass\n else:raise AssertionError('annotation exposed')\ns=socket.socket();s.settimeout(.1)\ntry:s.connect(('1.1.1.1',443))\nexcept OSError as e:assert e.errno in (errno.EPERM,errno.EACCES)\nelse:raise AssertionError('network exposed')"
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),sys.executable,'-c',script,*map(str,denied)],capture_output=True,text=True)
    if 'sandbox_apply: Operation not permitted' in result.stderr:pytest.skip('outer sandbox denies nested sandbox')
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('phase',['pilot','run'])
def test_native_orchestration_with_only_model_and_index_boundaries_injected(tmp_path,monkeypatch,phase):
    from outcome_poc import environment,generation,retrieval,assets,train
    m,_,_,runtime=fixture(tmp_path);root=Path(m['root']);module=api()
    asset_path=tmp_path/'asset-manifest.json'
    atomic_json(asset_path,{'assets':{'reader':{'local_path':'unused-reader'},
        'encoder':{'local_path':'unused-encoder','revision':'fixture','snapshot_hash':'fixture'}}})
    m['artifact_sha256']={str(asset_path):file_hash(asset_path)}
    m['manifest_hash']=module._digest(m);atomic_json(root/'manifest.json',m)
    monkeypatch.setattr(environment,'discover',lambda _: {'native_supported':True,'resource_gate':{'passed':True},'physical_memory_bytes':1024**4})
    monkeypatch.setattr(assets,'verify_assets',lambda _:None)
    import psutil
    from types import SimpleNamespace
    monkeypatch.setattr(psutil,'Process',lambda:SimpleNamespace(memory_info=lambda:SimpleNamespace(rss=1_000_000),children=lambda **kw:[]))
    monkeypatch.setattr(psutil,'swap_memory',lambda:SimpleNamespace(used=0))
    encoder=type('Encoder',(),{'identity':{'revision':'fixture','snapshot_hash':'fixture'}})()
    monkeypatch.setattr(retrieval,'EncoderBackend',lambda _:encoder)
    index=root/'synthetic-index';index.mkdir()
    index_manifest={'document_count':12,'window_count':12,'offline':{'seconds':.1}}
    monkeypatch.setattr(retrieval,'_completed_manifest',lambda _:index_manifest)
    def built(*args):
        atomic_json(root/'index-realization.json',{'index_dir':str(index),'files':{},'reuse_source_hashes':{}})
        return index,index_manifest
    monkeypatch.setattr(module,'build_pooled_index',built)
    monkeypatch.setattr(module,'PooledRetrieval',lambda *a,**k:runtime[0])
    monkeypatch.setattr(train,'load_gate',lambda descriptor:runtime[3][descriptor['family']])
    class Resident:
        def __init__(self,*args):pass
        def __enter__(self):runtime[2].peak_mlx_bytes=1;return runtime[2]
        def __exit__(self,*args):pass
    monkeypatch.setattr(generation,'SupervisedBackend',Resident)
    if phase=='run':built()
    result=module._native_work(m,phase,'synthetic-'+phase)
    assert result['status']=='complete'
    if phase=='pilot':
        assert result['generation_calls']==0
        assert (root/'pilot.closed.json').exists()
        assert len(list(read_jsonl(root/'pilot-queries-synthetic-pilot.jsonl')))==32
    else:
        assert result['result']['assigned_jobs']==96 and (root/'transfer.closed.json').exists()


def test_completed_receipts_still_reject_changed_frozen_request_settings(tmp_path):
    m,_,_,runtime=fixture(tmp_path);api().run_diagnostic(m,*runtime)
    root=Path(m['root']);path=next(root.glob('jobs/*/attempt-1/paid-1.started.json'))
    row=json.loads(path.read_text());row['request']['max_new_tokens']=999;atomic_json(path,row)
    terminal=path.with_name('paid-1.finished.json');value=json.loads(terminal.read_text())
    value['started_receipt_sha256']=file_hash(path);atomic_json(terminal,value)
    marker=json.loads((root/'transfer.closed.json').read_text())
    for changed in (path,terminal):marker['hashes'][str(changed.relative_to(root))]=file_hash(changed)
    atomic_json(root/'transfer.closed.json',marker)
    with pytest.raises(ValueError,match='request|settings'):api().validate_transfer(m)


def parent_attempt(m,label,stage,*,status='ok',finish=True,cost=True,seconds=2.):
    """Independent hand-written parent receipts; no process/model is launched."""
    root=Path(m['root']);start={'source_id':label,'stage':stage,'manifest_hash':m['manifest_hash'],
        'start_ns':1_000_000_000,'utc':'2026-10-15T00:00:00+00:00'}
    if stage!='prospective-preparation':start['phase']=stage
    atomic_json(root/f'{label}.started.json',start)
    if stage!='prospective-preparation':
        atomic_json(root/f'{label}.plan.json',{'manifest_hash':m['manifest_hash'],
            'started_receipt_sha256':file_hash(root/f'{label}.started.json'),'snapshot_hash':'synthetic','profile_hash':'synthetic'})
    if not finish:return
    output=root/('manifest.json' if stage=='prospective-preparation' else 'pilot.closed.json' if stage=='pilot' else 'transfer.closed.json')
    terminal={'source_id':label,'stage':stage,'manifest_hash':m['manifest_hash'],'status':status,
        'returncode':0 if status=='ok' and stage!='prospective-preparation' else None,
        'stop_ns':1_000_000_000+round(seconds*1e9),'elapsed_seconds':seconds,
        'started_receipt_sha256':file_hash(root/f'{label}.started.json'),
        'plan_sha256':file_hash(root/f'{label}.plan.json') if stage!='prospective-preparation' else None,
        'output_sha256':file_hash(output) if status=='ok' else None}
    atomic_json(root/f'{label}.finished.json',terminal)
    if cost:append_jsonl(root/'stage-costs.jsonl',{'source_id':label,'stage':stage,'status':status,
        'elapsed_seconds':seconds,'finished_receipt_sha256':file_hash(root/f'{label}.finished.json')})


def test_post_pilot_worker_seal_without_parent_terminal_cannot_authorize(tmp_path):
    m,_,_,_=fixture(tmp_path);root=Path(m['root'])
    parent_attempt(m,'preparation-1','prospective-preparation')
    parent_attempt(m,'launch-pilot-1','pilot',finish=False)
    atomic_json(root/'pilot.closed.json',{'manifest_hash':m['manifest_hash'],'hashes':{},'parent_attempt':'launch-pilot-1'})
    before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with pytest.raises(ValueError,match='parent|attempt|cost'):api().authorize_execution(m,forecast_seconds=300.)
    assert not (root/'execution-authorization.json').exists()
    assert before=={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('orphan_stage',['pilot','prospective-preparation'])
def test_earlier_orphan_parent_cannot_disappear_behind_successful_retry(tmp_path,orphan_stage):
    m,_,_,runtime=fixture(tmp_path);root=Path(m['root'])
    if orphan_stage=='prospective-preparation':
        parent_attempt(m,'preparation-1',orphan_stage,finish=False)
        parent_attempt(m,'preparation-2',orphan_stage)
    else:
        parent_attempt(m,'preparation-1','prospective-preparation')
        parent_attempt(m,'launch-pilot-1','pilot',finish=False)
    pilot_label='launch-pilot-2' if orphan_stage=='pilot' else 'launch-pilot-1'
    atomic_json(root/'pilot.closed.json',{'manifest_hash':m['manifest_hash'],'hashes':{},'parent_attempt':pilot_label})
    parent_attempt(m,pilot_label,'pilot')
    with pytest.raises(ValueError,match='parent|attempt|cost'):api().authorize_execution(m,forecast_seconds=300.)
    # Even a complete worker's 96 outputs cannot make unknown parent work free.
    api().run_diagnostic(m,*runtime)
    parent_attempt(m,'launch-run-1','run',seconds=1000.)
    with pytest.raises(ValueError,match='parent|attempt|cost'):api().validate_transfer(m)


@pytest.mark.parametrize('corrupt',['missing_cost','duplicate_cost','wrong_seconds'])
def test_parent_start_finish_cost_rows_must_reconcile_exactly(tmp_path,corrupt):
    m,_,_,_=fixture(tmp_path);root=Path(m['root'])
    parent_attempt(m,'preparation-1','prospective-preparation',cost=corrupt!='missing_cost')
    atomic_json(root/'pilot.closed.json',{'manifest_hash':m['manifest_hash'],'hashes':{},'parent_attempt':'launch-pilot-1'})
    parent_attempt(m,'launch-pilot-1','pilot')
    rows=list(read_jsonl(root/'stage-costs.jsonl'))
    if corrupt=='duplicate_cost':append_jsonl(root/'stage-costs.jsonl',rows[0])
    if corrupt=='wrong_seconds':
        rows[0]['elapsed_seconds']=.5
        (root/'stage-costs.jsonl').write_bytes(b''.join(canonical_bytes(r)+b'\n' for r in rows))
    with pytest.raises(ValueError,match='parent|attempt|cost'):api().authorize_execution(m,forecast_seconds=300.)


def test_failed_parent_costs_are_retained_and_run_resource_trace_is_sealed(tmp_path):
    m,_,_,runtime=fixture(tmp_path);root=Path(m['root'])
    parent_attempt(m,'preparation-1','prospective-preparation',status='failed',seconds=3.)
    parent_attempt(m,'preparation-2','prospective-preparation',seconds=2.)
    parent_attempt(m,'launch-pilot-1','pilot',status='failed',seconds=5.)
    atomic_json(root/'pilot.closed.json',{'manifest_hash':m['manifest_hash'],'hashes':{},'parent_attempt':'launch-pilot-2'})
    parent_attempt(m,'launch-pilot-2','pilot',seconds=4.)
    api().authorize_execution(m,forecast_seconds=300.)
    api().run_diagnostic(m,*runtime)
    resource=root/'worker-launch-run-1-resources.jsonl';append_jsonl(resource,{'synthetic':True})
    parent_attempt(m,'launch-run-1','run',seconds=1000.)
    api()._seal_native_completion(m)
    marker=json.loads((root/'launch-run.completed.json').read_text())
    assert str(resource.relative_to(root)) in marker['hashes']
    predictions,costs,_=api().validate_transfer(m)
    assert sum(costs[p.job_id]['total_experiment_seconds'] for p in predictions)==pytest.approx(1014.)
    append_jsonl(resource,{'changed':True})
    with pytest.raises(ValueError,match='checksum'):api().validate_transfer(m)


def test_failed_preparation_is_journaled_and_unknown_terminal_is_never_repaired(tmp_path):
    root=tmp_path/'independent-failed-preparation'
    with pytest.raises(FileNotFoundError):api().seal_manifest(tmp_path/'missing-primary.json',root)
    start=json.loads((root/'preparation-1.started.json').read_text())
    finish=json.loads((root/'preparation-1.finished.json').read_text())
    costs=list(read_jsonl(root/'stage-costs.jsonl'))
    assert finish['status']=='failed' and costs[0]['status']=='failed'
    assert costs[0]['elapsed_seconds']==(finish['stop_ns']-start['start_ns'])/1e9>0
    assert costs[0]['finished_receipt_sha256']==file_hash(root/'preparation-1.finished.json')
    (root/'preparation-1.finished.json').unlink()
    before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with pytest.raises(ValueError,match='parent'):api().seal_manifest(tmp_path/'missing-primary.json',root)
    assert before=={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}

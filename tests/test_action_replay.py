"""A03 adapter contracts using real synthetic schedule/run/score producers only."""
from copy import deepcopy
import importlib
from pathlib import Path

import pytest

from outcome_poc import protocol, runner, scoring, statistics
from outcome_poc.schemas import GoldRecord
from outcome_poc.storage import atomic_json, append_jsonl, content_hash
from test_protected_run import protected_fixture
from retrieval_helpers import Encoder


def api():
    assert importlib.util.find_spec('outcome_poc.action_replay'), 'A03 adapter missing'
    return importlib.import_module('outcome_poc.action_replay')


def fixture(tmp_path, outputs=None, close=True):
    from outcome_poc.data_runtime import DocumentStore
    from outcome_poc.retrieval import build_index, Retrieval
    parent, runtime, _ = protected_fixture(tmp_path, outputs)
    # Only synthetic manifests are amended, before any synthetic job starts.
    parent['methods']['retrieval'].update(index_dir=str(tmp_path/'index'),
        operational_realization_path=str(tmp_path/'run'/'index-realization.json'))
    parent['methods']['encoder'] = Encoder.identity.copy()
    assets=tmp_path/'asset-manifest.json'
    atomic_json(assets,{'assets':{'encoder':{'local_path':'synthetic-local',**Encoder.identity}}})
    parent['artifact_sha256'][str(assets)]=protocol.file_hash(assets)
    save(parent)
    p = deepcopy(parent)
    p['output_dir'] = str(tmp_path/'a03-protocol')
    p['run_dir'] = str(tmp_path/'a03-run')
    p['methods']['representatives'] = []
    p['methods']['deadline_utc'] = '2099-01-02T00:00:00+00:00'
    p['methods']['retrieval']['operational_realization_path'] = str(Path(p['run_dir'])/'index-realization.json')
    parent_path = Path(parent['output_dir'])/'protocol.json'
    p['replication'] = {'amendment_id':'A03', 'parent':{
        'protocol_path':str(parent_path), 'protocol_hash':parent['protocol_hash'],
        'protocol_file_sha256':protocol.file_hash(parent_path),
        'sample_file_sha256':protocol.file_hash(parent_path.with_name('sample.json')),
        'scientific_digests':parent['digests'], 'source':parent['source'],
        'output_dir':parent['output_dir'], 'run_dir':parent['run_dir']}}
    for name in ('protocol.json','sample.json','methods.json','schedule.json'):
        path=parent_path.with_name(name)
        p['artifact_sha256'][str(path)] = protocol.file_hash(path)
    save(p)
    documents=DocumentStore(runtime.document_path)
    encoder=Encoder()
    build_index((documents.get(i) for i in documents.offsets),encoder,tmp_path/'index')
    runtime.retrieval=Retrieval(tmp_path/'index',documents,encoder)
    if close:
        runner.run(p,runtime)
        gold=tmp_path/'synthetic-gold.jsonl'
        for t in runtime.tasks: append_jsonl(gold,GoldRecord(t.task_id,'blue',[('Lamp 0',0)]))
        rows=scoring.score_run(p,Path(p['run_dir']),gold,documents_path=runtime.document_path)
        atomic_json(Path(p['run_dir'])/'analysis.json',statistics.analyze_run(p,rows,runner.load_events(Path(p['run_dir']))))
    return p,parent,runtime


def save(p):
    p['schedule']={'jobs':protocol.plan_jobs(p['methods'],p['sample']['tasks']),
                   'assigned_task_ids':p['sample']['task_ids']}
    p['digests']={k:content_hash(p[k]) for k in ('methods','sample','schedule')}
    p['protocol_hash']=protocol._hash_protocol(p)
    for name in ('methods','sample','schedule'): atomic_json(Path(p['output_dir'])/(name+'.json'),p[name])
    atomic_json(Path(p['output_dir'])/'protocol.json',p)


def test_real_seven_job_admission_and_conditional_replay(tmp_path):
    p,parent,runtime=fixture(tmp_path)
    a=api().admit(Path(p['output_dir'])/'protocol.json')
    result=api().reconstruct(a,runtime.retrieval,runtime.models)
    assert len(a['scores'])==14
    assert result['assigned_tasks']==2 and result['assigned_jobs']==14
    assert {r['family'] for r in result['policies']} == {'PRE-LINEAR','PRE-RF','QUERY-ONLY','SHUFFLED-LABEL-GBM','PRE-OUTCOME-GBM','PROXY-LABEL'}
    assert all(len(r['rows'])==2 and r['quality']['n']==2 for r in result['policies'])
    assert all(r['full_direct_runtime_seconds'] is None for r in result['policies'])
    assert result['conditional_on_compatible_fixed_action_outputs'] is True
    assert result['missing_representative_direct_parity']=='unobserved'
    assert result['original_full_roster_analysis']=='unexecuted'
    assert all(r['status']=='compatible' for r in result['selected_checks'])
    assert len(result['accounting'])==8
    assert all(r['direct_serving_seconds']>0 and r['source_cost_surrogate_seconds']>0 for r in result['accounting'])
    assert all(r['paid_attempts'] for r in result['accounting'])
    assert result['traces'][0]['features'] and result['traces'][0]['rankings']
    assert result['parent_registry']['protocol_hash']==parent['protocol_hash']
    assert not Path(parent['run_dir']).exists()


def test_failed_semantic_actions_keep_assigned_denominator(tmp_path):
    p,_,runtime=fixture(tmp_path,['malformed'])
    result=api().reconstruct(api().admit(Path(p['output_dir'])/'protocol.json'),runtime.retrieval,runtime.models)
    for policy in result['policies']:
        assert policy['quality']['n']==2 and policy['quality']['joint_successes']==0
        assert all(row['source']['prediction']['status']=='parse_error' for row in policy['rows'])


def test_incomplete_schedule_is_unavailable_without_subset_or_gold(tmp_path,monkeypatch):
    p,_,_=fixture(tmp_path,close=False)
    result=api().admit(Path(p['output_dir'])/'protocol.json')
    assert result['status']=='unavailable' and result['assigned_tasks']==2
    assert result['assigned_jobs']==14 and result['scores'] is None


@pytest.mark.parametrize('name',['scores.jsonl','job-evidence.json','predictions.closed.json','protected-run.closed.json'])
def test_closed_input_checksum_mismatch_rejected(tmp_path,name):
    p,_,_=fixture(tmp_path)
    with (Path(p['run_dir'])/name).open('ab') as stream:stream.write(b'\n')
    with pytest.raises(ValueError,match='checksum|closure'):
        api().admit(Path(p['output_dir'])/'protocol.json')


@pytest.mark.parametrize('change',['missing','duplicate','wrong-task','wrong-parent','wrong-reader','extra-representative'])
def test_exact_assignment_and_parent_provenance(tmp_path,change):
    p,parent,runtime=fixture(tmp_path)
    if change in ('missing','duplicate','wrong-task'):
        root=Path(p['run_dir']);rows=list(__import__('outcome_poc.storage',fromlist=['read_jsonl']).read_jsonl(root/'scores.jsonl'))
        if change=='missing':rows.pop()
        elif change=='duplicate':rows[-1]=rows[0]
        else:rows[0]['task_id']='other'
        (root/'scores.jsonl').unlink()
        for row in rows:append_jsonl(root/'scores.jsonl',row)
        marker=protocol._read(root/'scores.jsonl.closed.json');marker['hashes']['scores.jsonl']=protocol.file_hash(root/'scores.jsonl')
        atomic_json(root/'scores.jsonl.closed.json',marker)
    elif change=='wrong-parent':p['replication']['parent']['protocol_hash']='f'*64;save(p)
    elif change=='wrong-reader':p['methods']['reader']['timeout_seconds']+=1;save(p)
    else:p['methods']['representatives']=[parent['methods']['representatives'][0]];save(p)
    with pytest.raises(ValueError):api().admit(Path(p['output_dir'])/'protocol.json')


def test_reconstruction_failures_stay_visible_without_complete_quality(tmp_path):
    p,_,runtime=fixture(tmp_path)
    real=runtime.retrieval.rank
    calls=0
    def fail_once(*args):
        nonlocal calls
        calls+=1
        if calls==1:raise ValueError('synthetic retrieval unavailable')
        return real(*args)
    runtime.retrieval.rank=fail_once
    result=api().reconstruct(api().admit(Path(p['output_dir'])/'protocol.json'),runtime.retrieval,runtime.models)
    assert len(result['traces'])==2
    assert all(len(row['rows'])==2 and row['quality'] is None for row in result['policies'])
    assert all(row['rows'][0]['status']=='unavailable' for row in result['policies'])


def test_selected_action_disagreement_withholds_selected_replay(tmp_path):
    p,_,runtime=fixture(tmp_path)
    class Changed:
        n_features_in_=42
        def predict(self,x):return [1.]*len(x)
    runtime.models['PRE-OUTCOME-GBM']=Changed()
    result=api().reconstruct(api().admit(Path(p['output_dir'])/'protocol.json'),runtime.retrieval,runtime.models)
    selected=next(row for row in result['policies'] if row['family']=='PRE-OUTCOME-GBM')
    assert selected['quality'] is None
    assert all(row['status']=='incompatible' for row in selected['rows'])
    assert any(row['status']=='incompatible' for row in result['selected_checks'])


def test_same_action_generated_token_disagreement_withholds_replay(tmp_path):
    # Real producer emits different token IDs per call; native receipt checks pass.
    from dataclasses import replace
    p,_,runtime=fixture(tmp_path,close=False)
    original=runtime.reader.backend.generate
    def different(*args,**kwargs):
        value=original(*args,**kwargs)
        return replace(value,generated_token_ids=[runtime.reader.backend.calls]*value.generated_tokens)
    runtime.reader.backend.generate=different
    runner.run(p,runtime)
    gold=tmp_path/'synthetic-gold.jsonl'
    for t in runtime.tasks:append_jsonl(gold,GoldRecord(t.task_id,'blue',[('Lamp 0',0)]))
    rows=scoring.score_run(p,Path(p['run_dir']),gold,documents_path=runtime.document_path)
    atomic_json(Path(p['run_dir'])/'analysis.json',statistics.analyze_run(p,rows,runner.load_events(Path(p['run_dir']))))
    result=api().reconstruct(api().admit(Path(p['output_dir'])/'protocol.json'),runtime.retrieval,runtime.models)
    assert all(row['quality'] is None for row in result['policies'])
    assert all(row['source_cost_surrogate_seconds'] is None for row in result['accounting'])


def test_analysis_closure_binds_inputs_and_own_sources(tmp_path):
    p,_,runtime=fixture(tmp_path)
    a=api().admit(Path(p['output_dir'])/'protocol.json')
    result=api().reconstruct(a,runtime.retrieval,runtime.models)
    output=tmp_path/'diagnostic'/'replay.json'
    api().seal(a,result,output)
    marker=protocol._read(output.with_suffix('.closed.json'))
    assert marker['report_sha256']==protocol.file_hash(output)
    assert marker['source_hashes'] and marker['input_hashes']
    assert marker['primary_analysis_sha256']==protocol.file_hash(Path(p['run_dir'])/'analysis.json')
    with pytest.raises(ValueError,match='outside'):
        api().seal(a,result,Path(p['run_dir'])/'new.json')
    (Path(p['run_dir'])/'analysis.json').write_text('{}')
    with pytest.raises(ValueError,match='changed|checksum'):
        api().seal(a,result,tmp_path/'changed.json')


def test_release_required_before_admission_or_model_loading(tmp_path,monkeypatch):
    p,_,_=fixture(tmp_path,close=False)
    module=api()
    assert hasattr(module,'analyze'), 'released standalone analysis missing'
    monkeypatch.setattr(module,'admit',lambda *_:pytest.fail('read run before release'))
    with pytest.raises(ValueError,match='release'):
        module.analyze(Path(p['output_dir'])/'protocol.json',tmp_path/'result.json',None)


def test_standalone_released_analysis_uses_frozen_loader_and_seals(tmp_path,monkeypatch):
    p,parent,runtime=fixture(tmp_path)
    module=api()
    assert hasattr(module,'analyze'), 'released standalone analysis missing'
    # Native setup uses exact existing seals; fixture supplies only model kernel.
    from outcome_poc import protected,retrieval,train
    from outcome_poc.data_runtime import DocumentStore
    documents=protected.selected_documents(p,runtime.document_path)
    protected.realize_index(p,documents,Encoder())
    monkeypatch.setattr(retrieval,'EncoderBackend',lambda _:Encoder())
    monkeypatch.setattr(train,'load_gate',lambda manifest:runtime.models[manifest['family']])
    release=tmp_path/'release.json'
    atomic_json(release,{'protocol_hash':p['protocol_hash'],'parent_protocol_hash':parent['protocol_hash'],
        'source_hashes':module._sources(),'source_review_approved':True,
        'original_collection_state':'stopped_incomplete','a03_collection_state':'closed',
        'authorized_by':'synthetic root','authorization':'Task18 analysis only'})
    output=tmp_path/'diagnostic'/'report.json'
    result=module.analyze(Path(p['output_dir'])/'protocol.json',output,release)
    assert result['status']=='complete'
    report=protocol._read(output)
    assert report['analysis_setup_seconds']>=0
    assert report['analysis_runtime_identity']['index_manifest_hash']==content_hash(runtime.retrieval.manifest)
    assert output.with_suffix('.closed.json').exists()


def test_parent_output_can_be_shared_container_without_reading_original_run(tmp_path):
    p,parent,runtime=fixture(tmp_path)
    # Match the writer's allowed production layout: original output may be a
    # shared artifacts container containing the new protocol and run roots.
    parent['output_dir']=str(tmp_path)
    save(parent)
    path=tmp_path/'protocol.json'
    ref=p['replication']['parent']
    ref.update(protocol_path=str(path),protocol_hash=parent['protocol_hash'],
        protocol_file_sha256=protocol.file_hash(path),sample_file_sha256=protocol.file_hash(tmp_path/'sample.json'),
        scientific_digests=parent['digests'],output_dir=str(tmp_path))
    for name in ('protocol.json','methods.json','sample.json','schedule.json'):
        p['artifact_sha256'][str(tmp_path/name)]=protocol.file_hash(tmp_path/name)
    save(p)
    assert api()._registry(p)==parent


def test_admission_never_parses_gold_or_rescores(tmp_path,monkeypatch):
    p,_,_=fixture(tmp_path)
    original=Path.read_text
    def guarded(path,*args,**kwargs):
        if 'gold' in path.name:pytest.fail('Gold records parsed by adapter')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'read_text',guarded)
    monkeypatch.setattr(scoring.Scorer,'score',lambda *_a,**_k:pytest.fail('rescored'))
    assert api().admit(Path(p['output_dir'])/'protocol.json')['status']=='available'


def test_self_consistent_wrong_reader_request_is_explicitly_incompatible(tmp_path):
    p,_,runtime=fixture(tmp_path)
    a=api().admit(Path(p['output_dir'])/'protocol.json')
    # Change every admitted in-memory request consistently: cross-policy parity
    # alone cannot establish compatibility with the frozen serving settings.
    for receipt in a['receipts'].values():
        for paid in receipt['paid']:paid['request']['max_new_tokens']=123
    result=api().reconstruct(a,runtime.retrieval,runtime.models)
    assert all(policy['quality'] is None for policy in result['policies'])
    assert all('frozen reader' in row['reason'] for policy in result['policies'] for row in policy['rows'])


def test_scorer_source_identity_is_not_an_unchecked_label(tmp_path):
    p,_,_=fixture(tmp_path)
    path=Path(p['run_dir'])/'scores.jsonl.closed.json'
    marker=protocol._read(path);marker['scorer_source_sha256']='f'*64;atomic_json(path,marker)
    with pytest.raises(ValueError,match='scorer source'):api().admit(Path(p['output_dir'])/'protocol.json')


def test_standalone_rejects_output_in_protocol_before_setup(tmp_path,monkeypatch):
    p,_,_=fixture(tmp_path,close=False)
    module=api()
    monkeypatch.setattr(module,'analyze',lambda *_:pytest.fail('executed before output guard'))
    with pytest.raises(ValueError,match='output'):
        module.main(['--protocol',str(Path(p['output_dir'])/'protocol.json'),
            '--output',str(Path(p['output_dir'])/'new-report.json'),'--release',str(tmp_path/'unused')])


def test_amendment_metadata_cannot_authorize_different_settings(tmp_path):
    p,parent,_=fixture(tmp_path)
    module=api()
    assert hasattr(module,'_amendment_metadata'), 'native A03 metadata guard missing'
    amendment=tmp_path/'A03.json'
    deadlines={'latest_launch_utc':'2026-10-15T08:12:52+00:00',
        'collection_deadline_utc':'2026-10-15T10:12:52+00:00',
        'original_project_deadline_utc':'2026-10-15T12:12:52+00:00',
        'original_collector_cutoff_utc':'2026-10-15T06:12:52+00:00'}
    value={'amendment_id':'A03','parent_protocol_hash':parent['protocol_hash'],
           'operational_gate':{**deadlines,'maximum_conditional_replications':1}}
    atomic_json(amendment,value)
    p['source']['sha256'][str(amendment)]=protocol.file_hash(amendment)
    p['methods']['deadline_utc']=deadlines['collection_deadline_utc']
    parent['methods']['deadline_utc']=deadlines['original_project_deadline_utc']
    p['replication'].update(amendment_path=str(amendment),amendment_sha256=protocol.file_hash(amendment),
        deadlines=deadlines,methods_changes={
            'representatives':{'previous':parent['methods']['representatives'],'new':[]},
            'deadline_utc':{'previous':parent['methods']['deadline_utc'],'new':p['methods']['deadline_utc']},
            'retrieval.operational_realization_path':{'previous':parent['methods']['retrieval']['operational_realization_path'],
                'new':p['methods']['retrieval']['operational_realization_path']}})
    module._amendment_metadata(p,parent)
    p['methods']['deadline_utc']='2099-01-01T00:00:00+00:00'
    with pytest.raises(ValueError,match='amendment|deadline'):module._amendment_metadata(p,parent)


def test_legacy_family_validator_remains_incompatible(tmp_path):
    from outcome_poc.robustness import ablate
    p,_,_=fixture(tmp_path)
    a=api().admit(Path(p['output_dir'])/'protocol.json')
    with pytest.raises(ValueError,match='incomplete frozen family roster'):
        ablate(p,a['scores'],a['events'])


def native_completion_fixture(p):
    """Native-shaped completion around a real synthetic producer's closed run.

    No native process or model is launched; these are the exact completion fields
    consumed by validate_run and the new adapter's operational binding capture.
    """
    root=Path(p['run_dir'])
    atomic_json(root/'native-summary.json',{'protocol_hash':p['protocol_hash'],'status':'closed'})
    atomic_json(root/'launch.completed.json',{'protocol_hash':p['protocol_hash'],'returncode':0,
        'hashes':{name:protocol.file_hash(root/name)
                  for name in ('protected-run.closed.json','native-summary.json')}})


@pytest.mark.parametrize('changed',['resources.jsonl','launch.completed.json','native-summary.json'])
def test_operational_closure_mutation_refuses_publication(tmp_path,changed):
    p,_,runtime=fixture(tmp_path)
    if changed!='resources.jsonl':native_completion_fixture(p)
    module=api()
    a=module.admit(Path(p['output_dir'])/'protocol.json')
    result=module.reconstruct(a,runtime.retrieval,runtime.models)
    root=Path(p['run_dir'])
    with (root/changed).open('ab') as stream:stream.write(b'\n')
    if changed=='resources.jsonl':
        from outcome_poc.protected import validate_run
        with pytest.raises(ValueError,match='protected closure checksum'):
            validate_run(p,root)
    output=tmp_path/'diagnostic'/'mutation.json'
    with pytest.raises(ValueError,match='changed|checksum'):
        module.seal(a,result,output)
    assert not output.exists() and not output.with_suffix('.closed.json').exists()


def test_analysis_digest_retains_all_operational_closure_bindings(tmp_path):
    p,_,runtime=fixture(tmp_path)
    native_completion_fixture(p)
    module=api();root=Path(p['run_dir'])
    a=module.admit(Path(p['output_dir'])/'protocol.json')
    result=module.reconstruct(a,runtime.retrieval,runtime.models)
    output=tmp_path/'diagnostic'/'operational.json'
    module.seal(a,result,output)
    closure=protocol._read(output.with_suffix('.closed.json'))
    for marker_name in ('protected-run.closed.json','launch.completed.json'):
        assert closure['input_hashes'][str(root/marker_name)]==protocol.file_hash(root/marker_name)
        for name,digest in protocol._read(root/marker_name)['hashes'].items():
            assert closure['input_hashes'][str(root/name)]==digest

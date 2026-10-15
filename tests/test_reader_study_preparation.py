"""Privileged preparation is exercised exclusively with invented local records."""
import copy
import json
from dataclasses import asdict
from pathlib import Path

import pytest
from outcome_poc.storage import canonical_bytes, content_hash, read_jsonl
from outcome_poc.followup.study import identity, publish


def fixture_config(tmp_path, documents10):
    from test_reader_study_study import authored
    tasks,membership,_=authored(1122)
    for i,t in enumerate(tasks):
        t['candidate_ids']=[d.doc_id for d in documents10]
        t['split']='pilot' if i<32 else 'pilot_reservation' if i<64 else 'fit' if i<320 else 'tune' if i<448 else 'fit_extension'
    prepared=tmp_path/'prepared';(prepared/'gold').mkdir(parents=True)
    def rows(path,values):path.write_bytes(b''.join(canonical_bytes(v)+b'\n' for v in values))
    rows(prepared/'tasks.jsonl',tasks)
    rows(prepared/'documents.jsonl',[asdict(d) for d in documents10])
    rows(prepared/'duplicate-membership.jsonl',membership)
    rows(prepared/'exclusions.jsonl',[])
    ids=[t['task_id'] for t in tasks]
    reservations=dict(pilot=ids[:64],active_pilot=ids[:32],fit=ids[64:320],tune=ids[320:448],
                      protected=[],fit_extension=ids[448:])
    publish(prepared/'development-reservations.json',reservations)
    publish(prepared/'protected-population.json',{'N':0,'task_ids':[]})
    rows(prepared/'gold/gold.jsonl',[dict(task_id=i,answer='authored violet',supporting_facts=[[documents10[0].title,0]]) for i in ids])
    publish(prepared/'manifest.json',dict(fingerprint='authored',reservations=reservations,
        files={str(p.relative_to(prepared)):identity(p) for p in prepared.rglob('*') if p.is_file()}))
    config=json.loads(Path('configs/reader-quality-comparison.json').read_text())
    config['prepared_dir']=str(prepared)
    metadata=tmp_path/'metadata';metadata.mkdir()
    config['old_metadata']=[]
    for i in range(22):
        path=metadata/f'old-{i}.json';publish(path,{'all_reserved':ids[:448]})
        config['old_metadata'].append(str(path))
    config['prior_cohorts']=[]
    prior=dict(diagnosis=ids[448:512],calibration_reserved=ids[512:544],calibration=ids[512:520],headroom=ids[544:672])
    for i in range(2):
        path=metadata/f'followup-{i}.json';publish(path,prior);config['prior_cohorts'].append(str(path))
    path=metadata/'citation.json';publish(path,dict(diagnosis=ids[672:736],comparison=ids[736:992]))
    config['citation_cohorts']=str(path)
    def asset(settings,role):
        folder=tmp_path/role;folder.mkdir();(folder/'LICENSE').write_text('authored fixture bytes')
        files={'LICENSE':identity(folder/'LICENSE')}
        return {**settings,'kind':'model','status':'ok','license':'mit','local_path':str(folder),
                'files':files,'snapshot_hash':content_hash(files)}
    basic=tmp_path/'assets.json';publish(basic,{'required':['reader','encoder'],'assets':{
        'reader':asset(config['readers']['qwen4b-instruct']['settings'],'old-reader'),
        'encoder':asset(config['encoder'],'encoder')}})
    strong=tmp_path/'strong.json';publish(strong,{'assets':{
        'reader':asset(config['readers']['qwen14b-nonthinking']['settings'],'new-reader')}})
    config['asset_manifest']=str(basic);config['strong_asset_manifest']=str(strong)
    path=tmp_path/'config.json';publish(path,config)
    return config,path,prepared


@pytest.fixture
def prepared_study(tmp_path,documents10,monkeypatch):
    from outcome_poc.reader_study import preparation
    config,path,prepared=fixture_config(tmp_path,documents10)
    monkeypatch.setattr(preparation,'EXPECTED_ELIGIBLE_COUNT',130)
    monkeypatch.setattr(preparation,'EXPECTED_ELIGIBLE_HASH',content_hash([f't-{i:04}' for i in range(992,1122)]))
    monkeypatch.setattr(preparation,'EXPECTED_PREPARED_FINGERPRINT','authored')
    monkeypatch.setattr(preparation,'validate_metadata_inventory',lambda c:None)
    monkeypatch.setattr(preparation,'verify_strong_manifest',lambda *args:None)
    monkeypatch.setattr(preparation,'discover_denial_locations',lambda r:{'version':1,'registries':[],
        'conventional_denied':[str(prepared)],'raw_locations':[],'declared_raw_files':[],
        'raw_probes':[],'gold_probes':[str(prepared/'gold/gold.jsonl')]})
    root=tmp_path/'run'
    original=preparation.project_support
    def project_after_freeze(tasks,documents,gold_rows):
        assert (root/'selection-frozen.json').is_file()
        assert len(json.loads((root/'schedule.json').read_text()))==608
        assert (root/'cohorts.json').is_file()
        return original(tasks,documents,gold_rows)
    monkeypatch.setattr(preparation,'project_support',project_after_freeze)
    plan=preparation.prepare(root,path)
    return root,plan,prepared


def test_preparation_binds_reader_leaves_shared_inputs_and_no_gold(prepared_study):
    from outcome_poc.reader_study.study import verify,verify_leaf,leaf_root,read
    root,plan,_=prepared_study
    assert verify(root,privileged=True)==plan
    assert set(read(root/'prompts.json'))=={'baseline'}
    assert len(list(read_jsonl(root/'inputs/confirmation/tasks.jsonl')))==128
    assert not (root/'inputs/confirmation/support-doc-ids.jsonl').exists()
    assert (root/'stages/confirmation/index-setup/denial-sentinel').is_file()
    assert not (root/'stages/confirmation/index-setup/build').exists()
    roster=read(root/'schedule.json')
    for stage in ('development','confirmation'):
        leaves=[]
        for reader in ('qwen4b-instruct','qwen14b-nonthinking'):
            leaf=leaf_root(root,stage,reader)
            lp=read(leaf/'plan.json')
            assert lp['freeze']['scientific_stage']==stage
            assert lp['freeze']['reader_id']==reader
            assert lp['source_origin']['path']==str(root/'source')
            assert not (leaf/'source').exists()
            assert read(leaf/'schedule.json')==[j for j in roster if j['scientific_stage']==stage and j['reader_id']==reader]
            assert read(leaf/'assets.json')['assets']['reader']==read(root/'assets.json')['assets'][reader]
            assert not any('gold' in n for n in lp['files'])
            leaves.append(leaf)
            if stage=='development':assert verify_leaf(root,stage,reader)==lp
        for name in ('tasks.jsonl','documents.jsonl'):
            assert (leaves[0]/'inputs/diagnosis'/name).read_bytes()==(leaves[1]/'inputs/diagnosis'/name).read_bytes()
    profile=plan['freeze']['bindings']['reader_profiles']['qwen14b-nonthinking']
    assert profile['enable_thinking'] is False


def test_common_and_development_verification_never_open_confirmation(prepared_study,monkeypatch):
    from outcome_poc.reader_study.study import verify
    root,plan,original=prepared_study
    original_open=Path.open
    def guarded(path,*args,**kwargs):
        assert not path.is_relative_to(root/'inputs/confirmation')
        assert not path.is_relative_to(root/'leaves/confirmation')
        assert not path.is_relative_to(root/'stages/confirmation')
        assert not path.is_relative_to(original)
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guarded)
    assert verify(root)==plan
    assert verify(root,stage='development')==plan


@pytest.mark.parametrize('name', ['source/src/outcome_poc/reader_study/study.py','assets.json','cohorts.json','schedule.json','prompts.json',
    'leaves/development/qwen4b-instruct/plan.json','inputs/development/tasks.jsonl'])
def test_changed_source_registry_cohort_schedule_leaf_or_inputs_rejected(prepared_study,name):
    from outcome_poc.reader_study.study import verify
    root,_,_=prepared_study
    path=root/name;path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError):verify(root,stage='development')


def test_confirmation_requires_task2_validator_before_input_reads(prepared_study,monkeypatch):
    from outcome_poc.reader_study.study import verify_stage
    root,plan,_=prepared_study
    original_open=Path.open
    def guarded(path,*args,**kwargs):
        assert not path.is_relative_to(root/'inputs/confirmation')
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guarded)
    with pytest.raises(ValueError,match='admission'):verify_stage(root,'confirmation',plan)


def test_production_config_and_mandatory_metadata_cannot_be_weakened():
    from outcome_poc.reader_study.preparation import validate_config,validate_metadata_inventory
    config=json.loads(Path('configs/reader-quality-comparison.json').read_text())
    validate_config(config);validate_metadata_inventory(config)
    for key,value in [('development_n',1),('confirmation_n',2),('seed',1),('eligible_count',2),('eligible_hash','wrong')]:
        with pytest.raises(ValueError):validate_config({**config,key:value})
    for key,value in [('old_metadata',config['old_metadata'][:-1]),('prior_cohorts',[]),('citation_cohorts','absent')]:
        with pytest.raises(ValueError):validate_metadata_inventory({**config,key:value})
    altered=copy.deepcopy(config);altered['readers']['qwen14b-nonthinking']['settings']['enable_thinking']=True
    with pytest.raises(ValueError):validate_config(altered)


def test_fresh_shared_index_and_denial_sentinel_have_separate_seals(prepared_study,monkeypatch):
    from outcome_poc.reader_study import preparation
    from outcome_poc.followup.study import verify_index
    from retrieval_helpers import Encoder
    root,plan,_=prepared_study
    monkeypatch.setattr(preparation,'EncoderBackend',lambda p:Encoder())
    with pytest.raises(ValueError,match='admission'):preparation.index(root,'confirmation')
    seal=preparation.index(root,'development')
    assert verify_index(root/'stages/development/index-setup/build',seal)['offline']['reuse_sources']==[]
    envelope=json.loads((root/'stages/development/index-envelope.json').read_text())
    assert envelope['index_seal_identity']==identity(root/'stages/development/index-setup/build/index-seal.json')
    assert envelope['plan_hash']==plan['plan_hash']
    with pytest.raises(FileExistsError):preparation.index(root,'development')


def test_failure_retains_setup_cost_and_refuses_overwrite(tmp_path):
    from outcome_poc.reader_study.preparation import prepare
    config=json.loads(Path('configs/reader-quality-comparison.json').read_text())
    config['prepared_dir']=str(tmp_path/'absent')
    path=tmp_path/'config.json';publish(path,config);root=tmp_path/'run'
    with pytest.raises(FileNotFoundError):prepare(root,path)
    assert list(read_jsonl(root/'setup.jsonl'))[-1]['status']=='failed'
    with pytest.raises(FileExistsError):prepare(root,path)


def _reseal_outer(root,plan):
    """Only test authors can rewrite attestations; verify semantic links too."""
    plan['plan_hash']=content_hash({k:v for k,v in plan.items() if k!='plan_hash'})
    (root/'plan.json').write_bytes(canonical_bytes(plan))


@pytest.mark.parametrize('mutation',['reader','stage','settings','asset','source'])
def test_leaf_reader_stage_profile_and_origin_cannot_be_swapped_even_with_local_reseal(prepared_study,mutation):
    from outcome_poc.reader_study.study import verify_leaf,leaf_root,read
    root,plan,_=prepared_study
    leaf=leaf_root(root,'development','qwen4b-instruct');lp=read(leaf/'plan.json')
    if mutation=='reader':lp['freeze']['reader_id']='qwen14b-nonthinking'
    elif mutation=='stage':lp['freeze']['scientific_stage']='confirmation'
    elif mutation=='settings':lp['freeze']['settings']['reader']['max_new_tokens']=255
    elif mutation=='source':lp['source_origin']['path']=str(root/'other-source')
    else:
        assets=read(leaf/'assets.json');assets['assets']['reader']=read(root/'assets.json')['assets']['qwen14b-nonthinking']
        (leaf/'assets.json').write_bytes(canonical_bytes(assets));lp['files']['assets.json']=identity(leaf/'assets.json')
    lp['plan_hash']=content_hash({k:v for k,v in lp.items() if k!='plan_hash'})
    (leaf/'plan.json').write_bytes(canonical_bytes(lp))
    plan['leaves']['development']['qwen4b-instruct']={'plan_hash':lp['plan_hash'],'identity':identity(leaf/'plan.json')}
    _reseal_outer(root,plan)
    with pytest.raises(ValueError):verify_leaf(root,'development','qwen4b-instruct')


def test_support_projection_cannot_change_frozen_cohorts_or_job_roster(prepared_study,monkeypatch):
    from outcome_poc.reader_study import preparation
    root,plan,_=prepared_study
    config_path=Path(next(p for p in plan['freeze']['privileged_inputs'] if p.endswith('/config.json')))
    def alternative(tasks,documents,gold):
        assert (root.with_name('alternative')/'selection-frozen.json').is_file()
        return [{'task_id':t['task_id'],'support_doc_ids':[t['candidate_ids'][1]]} for t in tasks]
    monkeypatch.setattr(preparation,'project_support',alternative)
    other=root.with_name('alternative');preparation.prepare(other,config_path)
    assert (root/'cohorts.json').read_bytes()==(other/'cohorts.json').read_bytes()
    assert (root/'schedule.json').read_bytes()==(other/'schedule.json').read_bytes()
    assert (root/'inputs/development/support-doc-ids.jsonl').read_bytes()!=(other/'inputs/development/support-doc-ids.jsonl').read_bytes()


@pytest.mark.parametrize('mutation',['count','hash','prepared','original','followup','citation'])
def test_changed_population_prepared_identity_and_historical_union_are_rejected(prepared_study,monkeypatch,mutation):
    from outcome_poc.reader_study import preparation
    root,plan,_=prepared_study
    config_path=Path(next(p for p in plan['freeze']['privileged_inputs'] if p.endswith('/config.json')))
    config=json.loads(config_path.read_text())
    if mutation=='count':monkeypatch.setattr(preparation,'EXPECTED_ELIGIBLE_COUNT',131)
    elif mutation=='hash':monkeypatch.setattr(preparation,'EXPECTED_ELIGIBLE_HASH','wrong')
    elif mutation=='prepared':monkeypatch.setattr(preparation,'EXPECTED_PREPARED_FINGERPRINT','wrong')
    elif mutation=='original':
        # An additional original alias reserves a new representative and must not be ignored.
        path=Path(config['old_metadata'][0]);value=json.loads(path.read_text());value['all_reserved'].append('t-1100')
        path.write_bytes(canonical_bytes(value))
    elif mutation=='followup':
        # Remove one never-executed calibration reservation from both historical files.
        for name in config['prior_cohorts']:
            path=Path(name);value=json.loads(path.read_text());value['calibration_reserved'].pop()
            path.write_bytes(canonical_bytes(value))
    else:
        path=Path(config['citation_cohorts']);value=json.loads(path.read_text());value['comparison'].pop()
        path.write_bytes(canonical_bytes(value))
    with pytest.raises(ValueError):preparation.prepare(root.with_name('rejected'),config_path)


def test_index_constructor_failure_retains_full_acquisition_envelope(prepared_study,monkeypatch):
    from outcome_poc.reader_study import preparation
    root,_,_=prepared_study
    def failed(path):raise RuntimeError('authored encoder startup failed')
    monkeypatch.setattr(preparation,'EncoderBackend',failed)
    with pytest.raises(RuntimeError,match='encoder startup'):preparation.index(root,'development')
    rows=list(read_jsonl(root/'stages/development/index-setup.jsonl'))
    assert rows[-1]['status']=='failed' and rows[-1]['stop_ns']>=rows[-1]['start_ns']
    with pytest.raises(ValueError,match='incomplete'):preparation.index(root,'development')


def test_sentinel_is_inside_future_index_but_outside_fresh_builder(prepared_study):
    root,plan,_=prepared_study
    assert (root/'stages/confirmation/index-setup/denial-sentinel').is_file()
    assert not (root/'stages/confirmation/index-setup/build').exists()
    assert plan['future_index_sentinel']=={'stages/confirmation/index-setup/denial-sentinel':identity(root/'stages/confirmation/index-setup/denial-sentinel')}


def test_common_verification_rejects_resealed_protocol_and_asset_pin_changes(prepared_study):
    from outcome_poc.reader_study.study import read,make_schedule,verify
    root,plan,_=prepared_study
    freeze=plan['freeze']
    freeze['settings']['seed']=1
    freeze['bindings']['settings']=copy.deepcopy(freeze['settings'])
    freeze['bindings_hash']=content_hash(freeze['bindings'])
    schedule=make_schedule(read(root/'cohorts.json'),freeze['bindings_hash'])
    freeze['schedule_hash']=content_hash(schedule)
    (root/'schedule.json').write_bytes(canonical_bytes(schedule))
    (root/'selection-frozen.json').write_bytes(canonical_bytes(freeze))
    for name in ('schedule.json','selection-frozen.json'):plan['files'][name]=identity(root/name)
    _reseal_outer(root,plan)
    with pytest.raises(ValueError,match='protocol|settings|config'):verify(root)


def test_cli_verify_keeps_privileged_modules_unimported(prepared_study,capsys):
    import subprocess
    import sys
    root,_,_=prepared_study
    script='''import sys
from outcome_poc.reader_study.__main__ import main
main(['verify','--root',sys.argv[1],'--stage','development'])
assert 'outcome_poc.reader_study.preparation' not in sys.modules
assert 'outcome_poc.scoring' not in sys.modules
'''
    result=subprocess.run([sys.executable,'-c',script,str(root)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['status']=='verified'


def test_stage_verification_rejects_changed_shared_index_envelope(prepared_study,monkeypatch):
    from outcome_poc.reader_study import preparation
    from outcome_poc.reader_study.study import verify
    from retrieval_helpers import Encoder
    root,_,_=prepared_study
    monkeypatch.setattr(preparation,'EncoderBackend',lambda p:Encoder())
    preparation.index(root,'development')
    path=root/'stages/development/index-envelope.json'
    envelope=json.loads(path.read_text());envelope['scientific_stage']='confirmation'
    path.write_bytes(canonical_bytes(envelope))
    with pytest.raises(ValueError,match='index'):verify(root,stage='development')

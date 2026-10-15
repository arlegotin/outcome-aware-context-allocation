"""Authored metadata and input fixtures only; never open benchmark assets."""
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
import pytest
from outcome_poc.storage import canonical_bytes, content_hash, read_jsonl


def authored_rows(n):
    tasks = [dict(task_id=f'fresh-{i:04}', split='fit_extension', question=f'Invented {i}?',
                  candidate_ids=['d'] * 10) for i in range(n)]
    membership = [dict(source='train', group_key_hash=content_hash(t['question'].casefold()),
                       representative_id=t['task_id'], member_ids=[t['task_id']], disposition='retained')
                  for t in tasks]
    return tasks, membership


def test_old_duplicate_alias_excluded():
    from outcome_poc.citation_study.study import plan_cohorts
    tasks, membership = authored_rows(5)
    membership[0]['member_ids'].append('unexecuted-prior-reservation')
    # Alias overlap expands through a second group, even when normalized hashes differ.
    membership.append(dict(source='dev', member_ids=['unexecuted-prior-reservation', 'z-bridge'],
                           group_key_hash='dev-group', disposition='excluded', representative_id='bridge'))
    membership[1]['member_ids'].append('z-bridge')
    cohorts = plan_cohorts(tasks, {'unexecuted-prior-reservation'}, membership, diagnosis_n=1, comparison_n=2)
    assert cohorts['eligibility']['count'] == 3
    assert not {'fresh-0000', 'fresh-0001'} & set(cohorts['diagnosis'] + cohorts['comparison'])
    assert cohorts['comparison_population'] == 2


def test_exact_pcg64_selection_and_factor_roster():
    from outcome_poc.citation_study.study import plan_cohorts, make_schedule
    tasks, membership = authored_rows(330)
    cohorts = plan_cohorts(tasks, set(), membership)
    ids = sorted(t['task_id'] for t in tasks)
    permutation = np.random.Generator(np.random.PCG64(20261015)).permutation(len(ids))
    assert cohorts['diagnosis'] == [ids[i] for i in permutation[:64]]
    assert cohorts['comparison'] == [ids[i] for i in permutation[64:320]]
    assert cohorts['eligibility']['sorted_ids_hash'] == content_hash(ids)
    jobs = make_schedule(cohorts, 'source-assets-settings-a')
    assert [sum(j['stage'] == s for j in jobs) for s in ('diagnosis', 'comparison')] == [384, 1024]
    assert len({j['job_id'] for j in jobs}) == 1408
    assert len({(j['stage'],j['task_id'],j['prompt_condition'],j['evidence_arm'],j['repetition']) for j in jobs}) == 1408
    assert all(j['repetition'] == 0 and j['execution_mode'] == 'continuous-resident-v1' for j in jobs)
    first = [j for j in jobs if j['task_id'] == cohorts['diagnosis'][0]]
    expected = sorted([(c,a) for c in ('baseline','chain') for a in ('2','10','support-documents')],
                      key=lambda x:(content_hash([20261015,'citation-chain-v1','diagnosis',cohorts['diagnosis'][0],*x]),*x))
    assert [(j['prompt_condition'],j['evidence_arm']) for j in first] == expected
    changed = make_schedule(cohorts, 'source-assets-settings-b')
    assert not {j['job_id'] for j in jobs} & {j['job_id'] for j in changed}


def fixture_prepared(tmp_path, documents10):
    from outcome_poc.followup.study import identity, publish
    prepared = tmp_path/'prepared'; (prepared/'gold').mkdir(parents=True)
    tasks, membership = authored_rows(330)
    for task in tasks: task['candidate_ids'] = [d.doc_id for d in documents10]
    def rows(path, values):
        path.write_bytes(b''.join(canonical_bytes(v)+b'\n' for v in values))
    rows(prepared/'tasks.jsonl', tasks)
    rows(prepared/'documents.jsonl', [asdict(d) for d in documents10])
    rows(prepared/'duplicate-membership.jsonl', membership)
    rows(prepared/'exclusions.jsonl', [])
    reservations = dict(pilot=[], active_pilot=[], fit=[], tune=[], protected=[],
                        fit_extension=[t['task_id'] for t in tasks])
    publish(prepared/'development-reservations.json', reservations)
    publish(prepared/'protected-population.json', {'N':0,'task_ids':[]})
    rows(prepared/'gold/gold.jsonl', [dict(task_id=t['task_id'], answer='authored violet',
         supporting_facts=[[documents10[0].title,0]]) for t in tasks])
    publish(prepared/'manifest.json', dict(fingerprint='authored', reservations=reservations,
        files={str(p.relative_to(prepared)):identity(p) for p in prepared.rglob('*') if p.is_file()}))
    config = json.loads(Path('configs/citation-chain-reader-study.json').read_text())
    config.update(prepared_dir=str(prepared), old_metadata=[], prior_cohorts=[])
    assets={}
    for role in ('reader','encoder'):
        folder=tmp_path/role; folder.mkdir(); (folder/'LICENSE').write_text('authored model stub')
        inventory={'LICENSE':identity(folder/'LICENSE')}
        assets[role]={**config[role], 'kind':'model','status':'ok','license':'mit',
                      'local_path':str(folder),'snapshot_hash':content_hash(inventory),'files':inventory}
    manifest=tmp_path/'assets.json'; publish(manifest, {'required':list(assets),'assets':assets})
    config['asset_manifest']=str(manifest)
    path=tmp_path/'config.json'; publish(path,config)
    return prepared,path,tasks,membership


def prepare_fixture(tmp_path, documents10, monkeypatch):
    from outcome_poc.citation_study import preparation
    prepared, path, tasks, membership = fixture_prepared(tmp_path, documents10)
    # Only inventory expectations differ in this wholly authored fixture. Production config
    # validation is exercised separately and has no fixture bypass.
    monkeypatch.setattr(preparation,'EXPECTED_ELIGIBLE_COUNT',330)
    monkeypatch.setattr(preparation,'EXPECTED_ELIGIBLE_HASH',content_hash(sorted(t['task_id'] for t in tasks)))
    monkeypatch.setattr(preparation,'EXPECTED_PREPARED_FINGERPRINT','authored')
    monkeypatch.setattr(preparation,'validate_metadata_inventory',lambda config: None)
    root=tmp_path/'study'
    original=preparation.project_support
    def frozen_before_gold(tasks,documents,gold_rows):
        assert (root/'selection-frozen.json').is_file()
        assert len(json.loads((root/'schedule.json').read_text())) == 1408
        assert (root/'prompts.json').is_file()
        return original(tasks,documents,gold_rows)
    monkeypatch.setattr(preparation,'project_support',frozen_before_gold)
    plan=preparation.prepare(root,path)
    return root,plan,prepared


def test_prompt_or_schedule_tampering_rejected(tmp_path, documents10, monkeypatch):
    from outcome_poc.citation_study.study import verify, selected_jobs
    root,plan,prepared=prepare_fixture(tmp_path,documents10,monkeypatch)
    assert verify(root,privileged=True)==plan
    assert len(selected_jobs(root,'diagnosis'))==384
    for name in ('prompts.json','schedule.json'):
        path=root/name; original=path.read_bytes(); path.write_text('{}')
        with pytest.raises(ValueError): verify(root)
        path.write_bytes(original)
    snapshot=root/'source/src/outcome_poc/citation_study/prompts.py'
    original=snapshot.read_bytes(); snapshot.write_text('changed sealed source')
    with pytest.raises(ValueError,match='sealed file changed'): verify(root)
    snapshot.write_bytes(original)
    bindings=plan['freeze']['bindings']
    from outcome_poc.citation_study.study import make_schedule, read
    jobs=read(root/'schedule.json')
    for key in ('source_snapshot','settings','prompts'):
        altered={**bindings,key:{'authored':'changed'}}
        changed=make_schedule(read(root/'cohorts.json'),content_hash(altered))
        assert not {j['job_id'] for j in jobs} & {j['job_id'] for j in changed}
    # Serving verification must never read original inputs, Gold or comparison inputs.
    import shutil
    shutil.rmtree(prepared); shutil.rmtree(root/'inputs/comparison')
    assert verify(root)==plan
    with pytest.raises(FileNotFoundError): verify(root,privileged=True)


def test_stage_stores_and_indexes_are_separate_fresh_and_immutable(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import preparation
    from outcome_poc.citation_study.study import read
    from outcome_poc.followup.study import verify_index
    from retrieval_helpers import Encoder
    root,plan,_=prepare_fixture(tmp_path,documents10,monkeypatch)
    for stage,n in [('diagnosis',64),('comparison',256)]:
        assert len(list(read_jsonl(root/f'inputs/{stage}/tasks.jsonl')))==n
        assert len(list(read_jsonl(root/f'inputs/{stage}/documents.jsonl')))==10
    projection=list(read_jsonl(root/'inputs/diagnosis/support-doc-ids.jsonl'))
    assert len(projection)==64 and all(set(r)=={'task_id','support_doc_ids'} for r in projection)
    assert not (root/'inputs/comparison/support-doc-ids.jsonl').exists()
    monkeypatch.setattr(preparation,'EncoderBackend',lambda path: Encoder())
    before=(root/'plan.json').read_bytes()
    with pytest.raises(ValueError,match='admission'):preparation.index(root,'comparison')
    for stage in ('diagnosis',):
        seal=preparation.index(root,stage)
        assert verify_index(root/f'stages/{stage}/index-setup',seal)['offline']['reused_window_count']==0
        with pytest.raises(FileExistsError): preparation.index(root,stage)
    assert (root/'plan.json').read_bytes()==before


def test_production_config_cannot_weaken_counts_or_reader_settings():
    from outcome_poc.citation_study.preparation import validate_config, validate_metadata_inventory
    config=json.loads(Path('configs/citation-chain-reader-study.json').read_text())
    validate_config(config); validate_metadata_inventory(config)
    with pytest.raises(ValueError): validate_metadata_inventory({**config,'old_metadata':config['old_metadata'][:-1]})
    with pytest.raises(ValueError): validate_metadata_inventory({**config,'prior_cohorts':[]})
    for key,value in [('diagnosis_n',1),('comparison_n',2),('seed',1)]:
        altered={**config,key:value}
        with pytest.raises(ValueError): validate_config(altered)
    config['reader']['max_new_tokens']=255
    with pytest.raises(ValueError): validate_config(config)


def test_preparation_failure_retains_cost_and_refuses_overwrite(tmp_path):
    from outcome_poc.citation_study.preparation import prepare
    config=json.loads(Path('configs/citation-chain-reader-study.json').read_text())
    config['prepared_dir']=str(tmp_path/'absent')
    path=tmp_path/'config.json'; path.write_text(json.dumps(config)); root=tmp_path/'run'
    with pytest.raises(FileNotFoundError): prepare(root,path)
    ledger=list(read_jsonl(root/'setup.jsonl'))
    assert ledger[-1]['status']=='failed' and ledger[-1]['stop_ns']>=ledger[-1]['start_ns']
    with pytest.raises(FileExistsError): prepare(root,path)


def test_declared_decoding_cannot_drift_from_bound_reader(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study.study import verify, read, identity
    root,plan,_=prepare_fixture(tmp_path,documents10,monkeypatch)
    plan['freeze']['decoding_hash']='disconnected-fixed-hash'
    (root/'selection-frozen.json').write_bytes(canonical_bytes(plan['freeze']))
    plan['files']['selection-frozen.json']=identity(root/'selection-frozen.json')
    plan['plan_hash']=content_hash({k:v for k,v in plan.items() if k!='plan_hash'})
    (root/'plan.json').write_bytes(canonical_bytes(plan))
    with pytest.raises(ValueError,match='decoding'): verify(root)


def test_index_constructor_failure_retains_full_setup_envelope(tmp_path,documents10,monkeypatch):
    from outcome_poc.citation_study import preparation
    root,plan,_=prepare_fixture(tmp_path,documents10,monkeypatch)
    def unavailable(path):
        raise RuntimeError('authored encoder startup failure')
    monkeypatch.setattr(preparation,'EncoderBackend',unavailable)
    with pytest.raises(RuntimeError,match='authored encoder startup failure'):
        preparation.index(root,'diagnosis')
    ledger=list(read_jsonl(root/'stages/diagnosis/index-setup.jsonl'))
    assert ledger[-1]['status']=='failed'
    assert ledger[-1]['stop_ns']>=ledger[-1]['start_ns']
    assert ledger[-1]['kind']=='index_setup'
    with pytest.raises(FileExistsError): preparation.index(root,'diagnosis')

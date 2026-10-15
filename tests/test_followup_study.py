"""Authored follow-up cohort/integrity fixtures; no benchmark access."""
from dataclasses import asdict
import json
from pathlib import Path
import pytest
from outcome_poc.storage import content_hash, canonical_bytes


def test_exact_cohorts_and_calibration_extremes():
    from outcome_poc.followup.study import plan_cohorts, make_schedule
    rows = [dict(task_id=f'new-{i}', split='fit_extension', question=f'Invented {i}',
                 candidate_ids=['d']*10) for i in range(230)]
    rows += [dict(task_id='old', split='fit', question='Café OLD', candidate_ids=['d']*10),
             dict(task_id='duplicate', split='fit_extension', question='  CAFE\u0301 old ', candidate_ids=['d']*10),
             dict(task_id='dev', split='protected', question='dev', candidate_ids=['d']*10)]
    cohorts = plan_cohorts(rows, {'old'}, [], {'d': 10})
    ordered = sorted(rows[:230], key=lambda r:(content_hash([20261015,'fresh-development-reader-headroom-v1',r['task_id']]),r['task_id']))
    assert cohorts['diagnosis'] == [r['task_id'] for r in ordered[:64]]
    assert cohorts['calibration_reserved'] == [r['task_id'] for r in ordered[64:96]]
    assert cohorts['headroom'] == [r['task_id'] for r in ordered[96:224]]
    length_order = sorted(cohorts['calibration_reserved'])
    assert cohorts['calibration'] == [length_order[j*31//7] for j in range(8)]
    schedule = make_schedule(cohorts)
    assert len(schedule) == 688
    assert [sum(j['stage']==s for j in schedule) for s in ('calibration','diagnosis','headroom')] == [48,256,384]
    assert len({j['job_id'] for j in schedule}) == 688


def test_projection_rejects_extra_unassigned_and_ambiguous(documents10, task10):
    from outcome_poc.followup.study import validate_projection, project_support
    task = asdict(task10)
    gold = [{'task_id':task10.task_id,'answer':'secret','supporting_facts':[[documents10[0].title,0]]}]
    projection = project_support([task], {d.doc_id:d for d in documents10}, gold)
    assert projection == [{'task_id':task10.task_id,'support_doc_ids':[documents10[0].doc_id]}]
    validate_projection(projection, [task])
    with pytest.raises(ValueError): validate_projection([{**projection[0],'answer':'leak'}],[task])
    with pytest.raises(ValueError): validate_projection([{'task_id':'unassigned','support_doc_ids':['d']}],[task])
    with pytest.raises(ValueError): project_support([task], {d.doc_id:d for d in documents10}, [])


def test_immutable_seal(tmp_path):
    from outcome_poc.followup.study import publish, identity, verify_files
    path=tmp_path/'sealed.json'
    publish(path, {'x':1})
    publish(path, {'x':1})
    with pytest.raises(ValueError): publish(path, {'x':2})
    bindings={str(path):identity(path)}
    verify_files(bindings)
    path.write_text('{}')
    with pytest.raises(ValueError): verify_files(bindings)


def test_no_reuse_physical_index(tmp_path, documents10):
    from outcome_poc.followup.study import build_new_index, verify_index
    from retrieval_helpers import Encoder
    root=tmp_path/'index-setup'; root.mkdir()
    seal=build_new_index(root, documents10, Encoder())
    verify_index(root,seal)
    manifest=root/'index/manifest.json'
    value=json.loads(manifest.read_text()); value['offline'].pop('reuse_sources')
    manifest.write_bytes(canonical_bytes(value))
    with pytest.raises(ValueError): verify_index(root,seal)
    with pytest.raises(ValueError): build_new_index(root, documents10, Encoder())


def test_preparation_failures_leave_setup_cost_and_never_overwrite(tmp_path):
    from outcome_poc.followup.study import prepare, read
    config=Path('configs/followup-reader-headroom.json')
    value=json.loads(config.read_text());value['prepared_dir']=str(tmp_path/'absent')
    path=tmp_path/'config.json';path.write_text(json.dumps(value))
    root=tmp_path/'new-run'
    with pytest.raises(FileNotFoundError):prepare(root,path)
    ledger=list(__import__('outcome_poc.storage',fromlist=['read_jsonl']).read_jsonl(root/'setup.jsonl'))
    assert ledger[-1]['status']=='failed' and ledger[-1]['stop_ns']>=ledger[-1]['start_ns']
    before=(root/'setup.jsonl').read_bytes()
    with pytest.raises(FileExistsError):prepare(root,path)
    assert (root/'setup.jsonl').read_bytes()==before


def test_prepare_freezes_before_annotation_projection_and_ignores_future_reservations(tmp_path, documents10, monkeypatch):
    from outcome_poc.followup import study
    from dataclasses import asdict
    prepared=tmp_path/'prepared';(prepared/'gold').mkdir(parents=True)
    tasks=[dict(task_id=f'fresh-{i}',split='fit_extension',question=f'Authored question {i}',
                candidate_ids=[d.doc_id for d in documents10]) for i in range(230)]
    tasks += [dict(task_id='old-fit',split='fit',question='Old authored question',candidate_ids=tasks[0]['candidate_ids'])]
    def rows(name,values):
        (prepared/name).write_bytes(b''.join(canonical_bytes(v)+b'\n' for v in values))
    rows('tasks.jsonl',tasks);rows('documents.jsonl',[asdict(d) for d in documents10])
    rows('duplicate-membership.jsonl',[{'source':'train','group_key_hash':content_hash(study.normalized(t['question'])),
         'representative_id':t['task_id'],'member_ids':[t['task_id']],'disposition':'retained'} for t in tasks])
    rows('exclusions.jsonl',[])
    reservations={'pilot':[],'tune':[],'fit':['old-fit'],'active_pilot':[],
        'fit_extension':[t['task_id'] for t in tasks[:-1]],'fit_prefixes':{'512':[t['task_id'] for t in tasks]},'protected':[]}
    study.publish(prepared/'development-reservations.json',reservations)
    study.publish(prepared/'protected-population.json',{'N':0,'task_ids':[]})
    rows('gold/gold.jsonl',[{'task_id':t['task_id'],'answer':'invented violet',
                            'supporting_facts':[[documents10[0].title,0]]} for t in tasks])
    files={str(p.relative_to(prepared)):study.identity(p) for p in prepared.rglob('*') if p.is_file()}
    study.publish(prepared/'manifest.json',{'fingerprint':'authored','files':files,'reservations':reservations})
    config=json.loads(Path('configs/followup-reader-headroom.json').read_text())
    config.update(prepared_dir=str(prepared),old_metadata=[])
    assets={}
    for role in ('reader','encoder'):
        folder=tmp_path/role;folder.mkdir();(folder/'LICENSE').write_text('authored stub, no model')
        inventory={'LICENSE':study.identity(folder/'LICENSE')}
        assets[role]={**config[role],'kind':'model','status':'ok','license':'mit','local_path':str(folder),
                      'snapshot_hash':content_hash(inventory),'files':inventory}
    manifest=tmp_path/'assets.json';study.publish(manifest,{'required':list(assets),'assets':assets})
    config['asset_manifest']=str(manifest)
    config_path=tmp_path/'config.json';study.publish(config_path,config)
    root=tmp_path/'new-study'
    original=study.project_support
    def assert_frozen(tasks,documents,gold_rows):
        assert (root/'selection-frozen.json').exists()
        assert len(study.read(root/'schedule.json'))==688
        return original(tasks,documents,gold_rows)
    monkeypatch.setattr(study,'project_support',assert_frozen)
    plan=study.prepare(root,config_path)
    assert study.verify(root)==plan
    assert study.read(root/'cohorts.json')['eligibility']['count']==230
    assert len(list(__import__('outcome_poc.storage',fromlist=['read_jsonl']).read_jsonl(root/'support-doc-ids.jsonl')))==64
    (root/'source/src/outcome_poc/followup/runtime.py').write_text('changed snapshot')
    with pytest.raises(ValueError,match='sealed file changed'):study.verify(root)

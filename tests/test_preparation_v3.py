"""NEW v3 preparation negative controls, using only invented inputs."""
from pathlib import Path
import pytest


def test_science_requires_prospective_precision_and_authentic_native_smoke(tmp_path):
    from outcome_poc.reader_recovery.preparation_v3 import research_gate
    from test_study_v3 import config
    cfg={**config(512),'purpose':'reader-admission'}
    with pytest.raises(ValueError,match='prospective'):
        research_gate(cfg,tmp_path,88235,'eligible')
    cfg['precision']={'path':str(tmp_path/'missing'),'identity':{'bytes':0,'sha256':'absent'}}
    with pytest.raises((OSError,ValueError)):
        research_gate(cfg,tmp_path,88235,'eligible')


def test_every_reserved_protocol_id_is_single_use(tmp_path):
    import json
    from outcome_poc.reader_recovery.preparation_v3 import unused_id
    path=tmp_path/'catalog.json';path.write_text(json.dumps({'protocols':[{'protocol_id':'reserved-v3','status':'reserved'}]}))
    with pytest.raises(ValueError,match='already reserved'):unused_id(path,'reserved-v3')
    unused_id(path,'new-v3')


def test_native_smoke_summary_requires_bound_score_file_bytes(tmp_path):
    import json
    from outcome_poc.reader_recovery.preparation_v3 import smoke_summary
    from outcome_poc.reader_recovery.study import publish,identity
    directory=tmp_path/'scores';directory.mkdir()
    publish(directory/'summary.json',{'assigned_jobs':4,'arms':{}})
    (directory/'scores.jsonl').write_text('authored fixture\n')
    publish(directory/'closed.json',{'plan_hash':'authored','assigned_jobs':4,'files':{n:identity(directory/n) for n in ('summary.json','scores.jsonl')}})
    assert smoke_summary(tmp_path,'authored')['assigned_jobs']==4
    publish(directory/'extra.json',{})
    (directory/'summary.json').write_text('{"assigned_jobs":99}\n')
    with pytest.raises(ValueError,match='identity|changed|checksum'):smoke_summary(tmp_path,'authored')


def test_gate_evidence_and_bound_gold_are_mandatory_retained_roots(tmp_path):
    from outcome_poc.reader_recovery.preparation_v3 import gate_locations
    from outcome_poc.reader_recovery.fresh import validate_output_locations
    from outcome_poc.reader_recovery.study import publish,identity
    from outcome_poc.storage import content_hash
    root=tmp_path/'smoke';root.mkdir();gold=tmp_path/'private-gold';gold.mkdir();(gold/'gold.jsonl').write_text('authored fixture\n')
    plan={'root':str(root),'gold_input':{'path':str(gold/'gold.jsonl'),'identity':identity(gold/'gold.jsonl')}}
    plan['plan_hash']=content_hash(plan);publish(root/'plan.json',plan)
    roots,probes,bindings=gate_locations({'native_smoke':{'root':str(root)}})
    assert root in roots and gold in roots and str(gold/'gold.jsonl') in probes
    assert bindings[str(root/'plan.json')]==identity(root/'plan.json')
    for output in (root/'nested',gold/'nested'):
        with pytest.raises(ValueError,match='overlap'):validate_output_locations(output,roots)
    (root/'plan.json').write_text('{}')
    with pytest.raises((ValueError,KeyError)):gate_locations({'native_smoke':{'root':str(root)}})


def test_gate_roots_include_recursive_native_smoke_gold_ancestry(tmp_path):
    from outcome_poc.reader_recovery.preparation_v3 import gate_locations
    from outcome_poc.reader_recovery.study import publish,identity
    from outcome_poc.storage import content_hash
    old=tmp_path/'older-smoke';old.mkdir();private=tmp_path/'older-private';private.mkdir()
    gold=private/'gold.jsonl';gold.write_text('authored bytes')
    plan={'root':str(old),'config':{},'gold_input':{'path':str(gold),'identity':identity(gold)}}
    publish(old/'plan.json',{**plan,'plan_hash':content_hash(plan)})
    new=tmp_path/'later-gate';new.mkdir();plan={'root':str(new),'config':{'native_smoke':{'root':str(old)}}}
    publish(new/'plan.json',{**plan,'plan_hash':content_hash(plan)})
    roots,probes,bindings=gate_locations({'reader_admission':{'root':str(new)}})
    assert old in roots and new in roots and private in roots and str(gold) in probes
    assert bindings[str(old/'plan.json')]==identity(old/'plan.json') and bindings[str(gold)]==identity(gold)

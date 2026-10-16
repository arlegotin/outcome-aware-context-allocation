"""NEW bounded-index receipt controls; authored software fixtures only."""
import pytest


def authored_proof(root,plan):
    from outcome_poc.reader_recovery.study import publish,identity
    from outcome_poc.storage import content_hash
    control=root/'index-supervision';control.mkdir()
    command=['authored-index-fixture']
    publish(control/'started.json',{'plan_hash':plan['plan_hash'],'boot_id':plan['freeze']['boot_id'],
            'clock':plan['freeze']['clock'],'start_ns':1,'budget_seconds':600,'command':command})
    publish(control/'native-parent-closure.json',{'command_hash':content_hash(command),'stop_ns':2,
            'returncode':0,'group_quiescent':True,'complete_assignment_scoring_allowed':True})
    publish(control/'receipt.json',{'plan_hash':plan['plan_hash'],'index_seal':identity(root/'index-setup/index-seal.json'),
            'parent_closure':identity(control/'native-parent-closure.json')})
    publish(control/'complete.json',{'start_ns':1,'stop_ns':3,'seconds':2e-9,
            'receipt':identity(control/'receipt.json')})


def test_index_budget_receipts_missing_tampered_overbudget_or_unknown_fail(tmp_path):
    from outcome_poc.reader_recovery.index_budget import validate_index_budget
    from outcome_poc.reader_recovery.study import publish,read
    from outcome_poc.storage import canonical_bytes
    root=tmp_path;plan={'plan_hash':'authored','config':{'schema_version':4,'index_budget_seconds':600},
                        'freeze':{'boot_id':'authored','clock':{'name':'authored'}}}
    setup=root/'index-setup';setup.mkdir();publish(setup/'index-seal.json',{'authored':True})
    with pytest.raises(FileNotFoundError):validate_index_budget(root,plan)
    authored_proof(root,plan);assert validate_index_budget(root,plan)['seconds']==2e-9
    path=root/'index-supervision/complete.json';original=read(path)
    path.write_bytes(canonical_bytes({**original,'stop_ns':601_000_000_001,'seconds':601}))
    with pytest.raises(ValueError):validate_index_budget(root,plan)
    path.write_bytes(canonical_bytes(original));publish(root/'index-supervision/native-stage-timeout.json',{'authored':True})
    with pytest.raises(ValueError):validate_index_budget(root,plan)


@pytest.mark.parametrize('invalid',[True,False])
def test_bounded_index_rejection_does_not_modify_retained_root(tmp_path,monkeypatch,invalid):
    from outcome_poc.reader_recovery import preparation_v3
    marker=tmp_path/'retained.txt';marker.write_text('authored retained bytes')
    def verify(root):
        if invalid:raise ValueError('authored input drift')
        return {'config':{'schema_version':3}}
    monkeypatch.setattr(preparation_v3,'verify',verify)
    with pytest.raises(ValueError):preparation_v3.index_bounded(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir())==['retained.txt']
    assert marker.read_text()=='authored retained bytes'

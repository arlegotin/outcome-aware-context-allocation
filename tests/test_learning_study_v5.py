"""NEW v5 frozen fit/held-out schedules; invented metadata, no native data."""
import pytest


def config(smoke=False):
    from test_study_v3 import config as base
    from outcome_poc.reader_recovery.learning_study_v5 import SCREEN
    c=base();c.pop('validation_n')
    return {**c,'schema_version':5,'study_kind':'allocation-routing-signal-v5','protocol_id':'authored-routing-v5',
        'purpose':'authored-routing-smoke' if smoke else 'routing-signal','seed':20261018,'fit_n':2 if smoke else 512,
        'holdout_n':0 if smoke else 256,'arms':['2','10'],'reader_recipe':'evidence-first-v1',
        'native_generation_budget_calls':5 if smoke else 1537,'index_budget_seconds':600,'learning_screen':SCREEN}


def test_learning_schedule_preserves_original_split_authorization_and_heldout_membership():
    from outcome_poc.reader_recovery.study import make_schedule,group_arms,is_fresh_validation
    cfg=config();cohorts={'fit':[f'fit-{i}' for i in range(512)],'learning_holdout':[f'held-{i}' for i in range(256)]}
    roster=make_schedule(cfg,cohorts)
    assert len(roster)==1536 and group_arms(cfg)=={'natural':('2','10')} and not is_fresh_validation(cfg)
    assert {j['stage'] for j in roster if j['task_id'].startswith('fit-')}=={'fit'}
    assert {j['stage'] for j in roster if j['task_id'].startswith('held-')}=={'headroom'}
    assert all({roster[i]['budget'],roster[i+1]['budget']}=={2,10} for i in range(0,len(roster),2))
    for changed in ({**cfg,'study_kind':'renamed'},{**cfg,'holdout_n':128},{**cfg,'reader_recipe':'baseline-v1'},
                    {**cfg,'native_generation_budget_calls':1536},{**cfg,'seed':7},{**cfg,'protocol_id':'reader-evidence-first-v1'}):
        with pytest.raises(ValueError):make_schedule(changed,cohorts)
    with pytest.raises(ValueError):make_schedule(cfg,{**cohorts,'learning_holdout':cohorts['fit'][:256]})


def test_v5_actual_allocation_bridge_and_complete_cap(tmp_path,monkeypatch):
    from test_study_v3 import actual_bridge_fixture
    from outcome_poc.reader_recovery.study import read
    from outcome_poc.reader_recovery.allocation_study import validate_parent
    cfg=config(True);summary=actual_bridge_fixture(tmp_path,monkeypatch,cfg,'fit')
    assert summary['assigned_jobs']==4 and set(summary['arms'])=={'2','10'}
    assert all(v['strict_successes']==2 for v in summary['arms'].values())
    root=tmp_path/'run';plan=read(root/'plan.json')
    validate_parent(root,plan)
    with pytest.raises(ValueError,match='complete native envelope'):
        validate_parent(root,{**plan,'config':{**cfg,'native_budget_seconds':0}})


def test_v5_learning_gate_missing_admission_fails_closed():
    from outcome_poc.reader_recovery.learning_preparation_v5 import learning_gate
    with pytest.raises(ValueError,match='admission'):learning_gate(config(),None,87595,'authored')

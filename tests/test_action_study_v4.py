"""NEW v4 explicit schedules and admission failure controls; invented metadata."""
import pytest


def config(n=128):
    from test_study_v3 import config as reader_config
    c=reader_config(2);c.pop('validation_n')
    return {**c,'schema_version':4,'study_kind':'allocation-action-value-v4','protocol_id':'authored-action-v4',
            'purpose':'action-headroom','development_n':n,'arms':['2','5','10'],
            'reader_recipe':'evidence-first-v1','index_budget_seconds':600,'native_generation_budget_calls':3*n+1,
            'research_screen':{'minimum_R_fraction_saving':.20,'minimum_mean_T_saving_seconds':.25,
                               'planning_routing_seconds':.02,'minimum_strict_discordances':16,'operational_requirements':None}}


def test_action_schedule_is_distinct_exact_and_balances_paid_budgets():
    from outcome_poc.reader_recovery.study import make_schedule,group_arms,is_fresh_validation,is_validation
    cfg=config();ids=[f'authored-{i}' for i in range(128)];cohorts={'development':ids}
    roster=make_schedule(cfg,cohorts)
    assert len(roster)==384 and group_arms(cfg)=={'natural':('2','5','10')}
    assert not is_fresh_validation(cfg) and not is_validation(cfg)
    assert all(j['stage']=='headroom' and j['reader_condition']=='evidence-first' and j['budget']==int(j['arm']) for j in roster)
    for i in ids:assert {j['budget'] for j in roster if j['task_id']==i}=={2,5,10}
    from collections import Counter
    orders=Counter(tuple(j['budget'] for j in roster[i:i+3]) for i in range(0,len(roster),3))
    assert len(orders)==6 and max(orders.values())-min(orders.values())==1
    for changed in ({**cfg,'study_kind':'renamed'},{**cfg,'reader_recipe':'baseline-v1'},
                    {**cfg,'native_generation_budget_calls':384},{**cfg,'protocol_id':'reader-evidence-first-v1'}):
        with pytest.raises(ValueError):make_schedule(changed,cohorts)
    with pytest.raises(ValueError):make_schedule(cfg,{'development':ids[:-1]})


def test_action_preparation_requires_authenticated_admission_and_screen():
    from outcome_poc.reader_recovery.action_preparation_v4 import admission_gate
    with pytest.raises(ValueError,match='admission'):admission_gate(config(),None,87723,'eligible')


def test_actual_allocation_paid_budgets_close_before_action_diagnostics(tmp_path,monkeypatch):
    from test_study_v3 import actual_bridge_fixture
    cfg={**config(2),'purpose':'authored-action-smoke'}
    summary=actual_bridge_fixture(tmp_path,monkeypatch,cfg,'development')
    assert set(summary['arms'])=={'2','5','10'} and summary['assigned_jobs']==6
    assert summary['action_value_screen']['allocation_claim'] is False

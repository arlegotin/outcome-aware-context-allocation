"""NEW bounded research screen; no fabricated native outcomes."""
from outcome_poc.reader_recovery.analysis import summarize
from test_oracle import row
from outcome_poc.reader_recovery.action_study_v4 import SCREEN


def arms(rows):
    return summarize([{'task_id':r.task_id,'arm':str(k),'seconds':t,'joint_em':s,'answer_em':e,'status':'ok'}
        for r in rows for k,t,s,e in ((2,r.small_cost_seconds,r.small_joint_em,r.small_answer_em),
                                      (5,r.full_cost_seconds,r.full_joint_em,r.full_answer_em),
                                      (10,r.full_cost_seconds,r.full_joint_em,r.full_answer_em))])['arms']


def test_simple_equal_quality_saving_does_not_require_training_or_nonzero_discordance():
    from outcome_poc.reader_recovery.action_analysis_v4 import action_value_screen
    rows=[row(str(i),int(i<28),int(i<28),1.,3.) for i in range(128)]
    result=action_value_screen(rows,arms(rows),SCREEN)
    assert result['best_eligible_fixed']=='2' and result['fixed_two_saves_with_empirical_quality_eligibility']
    assert not result['continue_to_learning'] and result['strict_discordance']==0
    assert not result['allocation_claim'] and result['operational_requirements'] is None


def test_both_endpoints_and_routing_allowance_constrain_screen_witness():
    from dataclasses import replace
    from outcome_poc.reader_recovery.action_analysis_v4 import action_value_screen
    rows=[row(str(i),int(i<20),int(20<=i<60),1.,3.) for i in range(128)]
    rows=[replace(r,small_answer_em=1,full_answer_em=1) for r in rows]
    result=action_value_screen(rows,arms(rows),SCREEN)
    assert result['continue_to_learning'] and result['strict_discordance']==60
    witness=result['screen_witness'];assert witness['S']>0 and witness['E']>=result['common_answer_anchor']
    assert witness['R_fraction_saving_with_planning_overhead']>=.2
    assert witness['mean_T_saving_with_planning_overhead']>=.25
    failed=action_value_screen([row('fail',0,0)],arms([row('fail',0,0)]),SCREEN)
    assert not failed['continue_to_learning'] and failed['screen_witness'] is None

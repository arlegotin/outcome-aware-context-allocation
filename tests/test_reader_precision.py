"""NEW prospective planning fixtures, not observed benchmark evidence."""
import pytest


def test_census_planning_obeys_strict_guard_and_failure_rule():
    from outcome_poc.reader_recovery.precision import forecast
    gain=[{'baseline':[0,0,0],'candidate':[1,1,0],'probability':1.}]
    assert forecast(gain,8,8,100,7)['joint_admission_probability']==1.
    identical=[{'baseline':[1,1,0],'candidate':[1,1,0],'probability':1.}]
    assert forecast(identical,8,8,100,7)['joint_admission_probability']==0.
    failures=[{'baseline':[0,0,0],'candidate':[1,1,0],'probability':.5},
              {'baseline':[0,0,0],'candidate':[0,0,1],'probability':.5}]
    assert forecast(failures,8,8,100,7)['joint_admission_probability']==0.


def test_planning_rejects_impossible_strict_states_and_unregistered_sampling():
    from outcome_poc.reader_recovery.precision import forecast
    for state in ([0,1,0],[1,1,1]):
        with pytest.raises(ValueError):forecast([{'baseline':state,'candidate':[0,0,0],'probability':1.}],8,8,100,7)
    with pytest.raises(ValueError):forecast([{'baseline':[0,0,0],'candidate':[1,1,0],'probability':.9}],8,8,100,7)

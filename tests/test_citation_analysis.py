import pytest


def rows(n=4):
    return [dict(task_id=str(i),prompt_condition=c,arm=a,repetition=0,joint_em=int(c=='chain' and i==0),answer_em=1,support_em=0,
        answer_f1=1.,support_f1=0.,support_precision=0.,support_recall=0.,joint_f1=0.,seconds=float(i+1),
        active_seconds=float(i+1),drift_seconds=0.,calls=1,prompt_tokens=10,generated_tokens=2,status='ok',empty=False,truncated=False,
        ordinal=i*4+k) for i in range(n) for k,(c,a) in enumerate((('baseline','2'),('chain','2'),('baseline','10'),('chain','10')))]


def test_paired_finite_population_all_query_ratios_and_zero_success():
    from outcome_poc.citation_study.analysis import summarize
    result=summarize(rows(),'comparison',88843)
    assert result['paired']['10']['joint_em']['difference']==.25
    assert result['paired']['10']['joint_em']['tail_alpha']==.0125
    assert result['paired']['10']['answer_em']['tail_alpha']==.00625
    assert result['paired']['10']['joint_em']['both_success']==0
    assert 'preserved' not in result['paired']['10']['answer_em']
    baseline=result['cells']['baseline/10'];chain=result['cells']['chain/10']
    assert baseline['seconds_per_strict_success'] is None and baseline['ratio_display']=='∞'
    assert chain['seconds_per_strict_success']==10. # All 10 seconds, not successful question's 1 second.
    assert chain['n']==4 and result['assigned_observations']==16
    with pytest.raises(ValueError):summarize(rows()[:-1],'comparison',88843)
    with pytest.raises(ValueError):summarize(rows()+[rows()[0]],'comparison',88843)

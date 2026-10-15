import pytest


def test_zero_success_uses_all_questions_and_null_ratio():
    from outcome_poc.followup.analysis import summarize, frontier
    rows=[dict(task_id=f'q{i}',arm=str(k),joint_em=0,answer_em=0,support_em=0,support_f1=0.,
               seconds=float(k),status='parse_error',prompt_tokens=2,generated_tokens=3,calls=1,
               empty=False,truncated=False,drift_seconds=0.) for i in range(4) for k in (2,5,10)]
    summary=summarize(rows)
    assert summary['arms']['2']['observations']==4
    assert summary['arms']['2']['cost_per_joint_success'] is None
    assert summary['arms']['2']['zero_success_reason']
    assert frontier(rows,'joint_em') == [{'successes':0,'questions':4,'seconds':8.0,'cost_per_success':None}]


def test_frontier_cheapest_measured_action_then_minimum_success_increment():
    from outcome_poc.followup.analysis import frontier
    rows=[dict(task_id='a',arm='2',seconds=5.,joint_em=0),dict(task_id='a',arm='5',seconds=2.,joint_em=0),
          dict(task_id='a',arm='10',seconds=8.,joint_em=1),dict(task_id='b',arm='2',seconds=2.,joint_em=1),
          dict(task_id='b',arm='5',seconds=1.,joint_em=0),dict(task_id='b',arm='10',seconds=9.,joint_em=1)]
    points=frontier(rows,'joint_em')
    assert [(r['successes'],r['seconds']) for r in points] == [(0,3.),(1,4.),(2,10.)]

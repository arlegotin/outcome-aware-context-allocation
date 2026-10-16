"""NEW exact two-endpoint oracle diagnostics checked against tiny exhaustive sets."""
from dataclasses import replace
from itertools import product
import random
import pytest
from test_oracle import row


def exhaustive(rows,minimum_S,minimum_E):
    points=[]
    for choices in product((2,10),repeat=len(rows)):
        S=sum(r.small_joint_em if k==2 else r.full_joint_em for r,k in zip(rows,choices))
        E=sum(r.small_answer_em if k==2 else r.full_answer_em for r,k in zip(rows,choices))
        T=sum(r.small_cost_seconds if k==2 else r.full_cost_seconds for r,k in zip(rows,choices))
        if S>=minimum_S and E>=minimum_E and S:points.append((T/S,T,S,E))
    return min(points) if points else None


def test_two_endpoint_oracle_rejects_answer_harm_and_all_fail_shortcut():
    from outcome_poc.oracle import two_endpoint_frontier,oracle_frontier
    rows=[replace(row('equal-strict',0,0,1.,4.),full_answer_em=1),row('success',1,1,2.,1.)]
    assert oracle_frontier(rows)[0]['total_seconds']==2.
    result=two_endpoint_frontier(rows,minimum_strict_successes=1,minimum_answer_successes=2)
    assert result['minimum_R']['total_T']==5.
    assert result['minimum_R']['choices']==[10,10]
    assert result['service_quality_floor'] is None and not result['allocation_claim']
    failed=two_endpoint_frontier([row('fail',0,0)],minimum_strict_successes=0,minimum_answer_successes=0)
    assert failed['minimum_R'] is None and failed['reason']=='no_nonzero_strict_feasible_schedule'
    assert all(p['R'] is None for p in failed['frontier'])


def test_exact_frontier_matches_exhaustive_costlier_correct_cheaper_full_and_random_cases():
    from outcome_poc.oracle import two_endpoint_frontier
    generator=random.Random(917)
    states=[(0,0),(1,0),(1,1)]
    for number in range(35):
        rows=[]
        for i in range(1+number%7):
            e2,s2=generator.choice(states);e10,s10=generator.choice(states)
            rows.append(replace(row(str(i),s2,s10,float(generator.randrange(1,8)),float(generator.randrange(1,8))),
                                small_answer_em=e2,full_answer_em=e10))
        S=generator.randrange(len(rows)+1);E=generator.randrange(len(rows)+1)
        result=two_endpoint_frontier(rows,minimum_strict_successes=S,minimum_answer_successes=E)
        expected=exhaustive(rows,S,E);best=result['minimum_R']
        assert (best is None)==(expected is None)
        if best is not None:
            assert best['R']==expected[0]
            assert sum(r.small_joint_em if k==2 else r.full_joint_em for r,k in zip(rows,best['choices']))==best['S']
            assert sum(r.small_answer_em if k==2 else r.full_answer_em for r,k in zip(rows,best['choices']))==best['E']
            assert sum(r.small_cost_seconds if k==2 else r.full_cost_seconds for r,k in zip(rows,best['choices']))==best['total_T']
        points=result['frontier']
        assert not any(a['total_T']<=b['total_T'] and a['S']>=b['S'] and a['E']>=b['E'] for a in points for b in points if a is not b)


def test_impossible_endpoint_states_unknown_anchors_and_invalid_costs_fail_closed():
    from outcome_poc.oracle import two_endpoint_frontier
    for rows,minimum_S,minimum_E in (([replace(row('bad',1,1),small_answer_em=0)],0,0),
                                    ([row('a',0,0)],None,0),([row('a',0,0)],0,2),
                                    ([row('a',0,0,float('nan'))],0,0)):
        with pytest.raises(ValueError):two_endpoint_frontier(rows,minimum_strict_successes=minimum_S,minimum_answer_successes=minimum_E)

from dataclasses import replace
import pytest

from outcome_poc.schemas import PairedActionRow


def row(identity, small, full, small_cost=1., full_cost=3.):
    return PairedActionRow(identity, 'Synthetic question?', [], {}, 's', 'f', small, full, small, full,
                           [], [], small_cost, full_cost, 'ok', 'ok')


def test_four_cells_rescue_harm_and_nonmonotone_maximum():
    from outcome_poc.oracle import headroom
    result = headroom([row('a', 0, 0), row('b', 0, 1), row('c', 1, 0), row('d', 1, 1)])
    assert result['cells'] == {'both_fail': 1, 'rescue': 1, 'harm': 1, 'both_success': 1}
    assert sum(result['cells'].values()) == result['n'] == 4
    assert result['net_full_minus_small'] == result['rescues'] - result['harms'] == 0
    assert result['oracle_quality'] == .75


def test_frontier_starts_cheapest_and_only_improves_success_with_cost_tiebreak():
    from outcome_poc.oracle import oracle_frontier
    rows = [row('c', 0, 1, 1., 4.), row('b', 0, 1), row('a', 0, 1),
            row('harm', 1, 0, 4., 1.), row('equal', 0, 0, 5., 1.)]
    frontier = oracle_frontier(rows)
    assert frontier[0]['total_seconds'] == 5.
    assert frontier[0]['successes'] == 0
    assert [point['switched_task_id'] for point in frontier[1:]] == ['a', 'b', 'c', 'harm']
    assert [point['successes'] for point in frontier] == [0, 1, 2, 3, 4]
    assert frontier[-1]['quality'] == .8


def test_zero_discordance_is_insufficient_and_zero_success_ratio_is_json_safe():
    from outcome_poc.oracle import headroom
    result = headroom([row('a', 0, 0), row('b', 0, 0)])
    assert result['evidence'] == 'insufficient_evidence'
    assert result['fixed_two']['seconds_per_success'] is None
    assert result['fixed_two']['reason'] == 'zero_successes'


def test_duplicate_assignments_and_invalid_binary_scores_rejected():
    from outcome_poc.oracle import headroom
    with pytest.raises(ValueError): headroom([row('a', 0, 1), row('a', 1, 1)])
    with pytest.raises(ValueError): headroom([replace(row('a', 0, 1), full_joint_em=2)])

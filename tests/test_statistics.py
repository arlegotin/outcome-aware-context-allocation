"""Invented numerical fixtures; count coverage uses exhaustive finite populations."""

from itertools import combinations
import json
from math import comb

import numpy as np
import pytest

from outcome_poc.statistics import (
    compare_primary, efficiency, finite_population_lower,
    finite_population_upper, paired_quality_bounds, quality_guards,
)


VERIFIED = dict(timing_stationary=True, deterministic_outputs=True, single_dominant=False)


def test_efficiency_keeps_failed_time_and_averages_repetitions():
    result = efficiency(np.array([[2., 4.], [8., 12.], [5., 7.]]), np.array([1, 0, 1]))
    assert result['ratio'] == 9.5  # (3 + 10 + 6) / 2, not average of successful rows
    assert result['quality'] == 2 / 3
    assert result['total_time'] == 19
    assert result['success_count'] == 2


def test_zero_successes_is_json_safe():
    result = efficiency(np.ones((3, 2)), np.zeros(3))
    assert result['ratio'] is None
    assert result['reason'] == 'zero_successes'
    json.dumps(result, allow_nan=False)
    comparison = compare_primary(np.ones((3, 2)), np.ones((3, 2)), np.zeros(3), np.ones(3), 10)
    assert comparison['effect'] is None
    assert comparison['ci'] is None
    assert comparison['status'] == 'inconclusive'
    assert len(comparison['sensitivity']['leave_one_out']) == 3
    json.dumps(comparison, allow_nan=False)


@pytest.mark.parametrize('x,n,N,alpha', [(-1, 2, 5, .05), (3, 2, 5, .05),
    (0, 0, 5, .05), (0, 6, 5, .05), (0, 2, 0, .05), (True, 2, 5, .05),
    (0, 2.5, 5, .05), (0, 2, 5, 0), (0, 2, 5, 1), (0, 2, 5, float('nan'))])
def test_binary_bounds_reject_invalid_inputs(x, n, N, alpha):
    with pytest.raises(ValueError):
        finite_population_upper(x, n, N, alpha)
    with pytest.raises(ValueError):
        finite_population_lower(x, n, N, alpha)


def test_zero_harm_is_not_zero_population_risk():
    assert finite_population_upper(0, 10, 100, .05) > 0
    assert finite_population_upper(4, 20, 20, .05) == 4 / 20
    assert finite_population_lower(4, 20, 20, .05) == 4 / 20
    # For N=5,n=2: P(X=0) at K=3 is 1/10, at K=4 is zero.
    assert finite_population_upper(0, 2, 5, .05) == .6
    assert finite_population_lower(2, 2, 5, .05) == .4


@pytest.mark.parametrize('N,n,alpha', [(5, 2, .05), (8, 3, .1), (10, 7, .05), (6, 6, .05)])
def test_enumerated_one_sided_coverage(N, n, alpha):
    samples = list(combinations(range(N), n))
    worst_upper, worst_lower = 0., 0.
    for K in range(N + 1):
        upper_misses = lower_misses = 0
        # Exhaustive subsets, independently of scipy/the bound implementation.
        for selected in samples:
            x = sum(index < K for index in selected)
            upper_misses += finite_population_upper(x, n, N, alpha) < K / N
            lower_misses += finite_population_lower(x, n, N, alpha) > K / N + 1e-14
        worst_upper = max(worst_upper, upper_misses / comb(N, n))
        worst_lower = max(worst_lower, lower_misses / comb(N, n))
    print(f'coverage N={N} n={n} alpha={alpha}: upper_miss={worst_upper}, lower_miss={worst_lower}')
    assert worst_upper <= alpha + 1e-14
    assert worst_lower <= alpha + 1e-14


@pytest.mark.parametrize('times,successes', [(np.ones(3), np.ones(3)),
    (np.ones((3, 0)), np.ones(3)), (np.ones((0, 2)), np.ones(0)),
    (np.array([[0., 1.]]), np.ones(1)), (np.array([[np.nan, 1.]]), np.ones(1)),
    (np.array([[np.inf, 1.]]), np.ones(1)), (np.ones((3, 2)), np.array([1, 2, 0])),
    (np.ones((3, 2)), np.ones(2)), (np.ones((3, 2)), np.ones((3, 1)))])
def test_efficiency_rejects_incomplete_or_nonbinary_arrays(times, successes):
    with pytest.raises(ValueError):
        efficiency(times, successes)


def test_paired_harm_rescue_identity_and_sparse_bounds():
    a = np.array([1, 1, 1, 0, 0])
    b = np.array([1, 0, 0, 1, 0])
    result = paired_quality_bounds(a, b, 20, .05)
    assert result['rescue_count'] == 2
    assert result['harm_count'] == 1
    assert result['difference'] == .2
    assert result['sampling_variance'] == pytest.approx(.105)
    assert result['sparse'] is True
    assert result['ci'][0] <= .2 <= result['ci'][1]
    swapped = paired_quality_bounds(b, a, 20, .05)
    assert swapped['ci'] == pytest.approx([-result['ci'][1], -result['ci'][0]])


def test_quality_census_and_regular_diagnostic():
    a = np.r_[np.ones(20), np.zeros(20)]
    b = np.r_[np.zeros(10), np.ones(10), np.ones(10), np.zeros(10)]
    result = paired_quality_bounds(a, b, 40, .05)
    assert result['sparse'] is False
    assert result['difference'] == 0
    assert result['ci'] == [0, 0]
    assert result['sampling_variance'] == 0
    assert result['preserved'] is True


def test_identical_subsample_outcomes_do_not_establish_preservation():
    result = paired_quality_bounds(np.ones(10), np.ones(10), 100, .05 / 16)
    assert result['difference'] == 0
    assert result['ci'][0] < 0 < result['ci'][1]
    assert result['preserved'] is False


def test_four_guards_use_simultaneous_tail_allocation():
    # N=100,n=20,x=0: exact upper count is 23 at .05/16
    # (P(X=0|K=23)=.00274724 < .003125), hence bound 22/100.
    rows = [dict(candidate_joint_em=1, comparator_joint_em=1, fixed_ten_joint_em=1,
                 candidate_answer_em=1, comparator_answer_em=1, fixed_ten_answer_em=1)
            for _ in range(20)]
    result = quality_guards(rows, 100)
    assert len(result) == 4
    assert {(r['metric'], r['comparator']) for r in result} == {
        ('joint_em', 'selected'), ('answer_em', 'selected'),
        ('joint_em', 'fixed_ten'), ('answer_em', 'fixed_ten')}
    for guard in result:
        assert guard['tail_alpha'] == .05 / 16
        assert guard['ci'] == [-.22, .22]
        assert guard['preserved'] is False


@pytest.mark.parametrize('rows', [[], [{}], [dict(candidate_joint_em=1)]])
def test_quality_guards_reject_incomplete_family(rows):
    with pytest.raises(ValueError):
        quality_guards(rows, 100)


def test_paired_timing_covariance_and_no_double_counting():
    # Contrast means alternate -1,-3: sample variance 40/39.
    # Contrast repetitions (1,-3) or (-1,-5): mean-noise variance=4.
    a = np.tile([[9., 11.], [7., 9.]], (20, 1))
    b = np.tile([8., 14.], (40, 1))
    result = compare_primary(a, b, np.ones(40), np.ones(40), 80, **VERIFIED)
    assert result['effect'] == -2
    assert result['variance']['sampling'] == pytest.approx(1 / 78)
    assert result['variance']['mean_timing_noise'] == 4
    assert result['variance']['timing_restoration'] == pytest.approx(.05)
    assert result['variance']['total'] == pytest.approx(.06282051282051282)
    assert result['ci'] == pytest.approx([-2.4912457767, -1.5087542233], abs=1e-8)
    assert result['status'] == 'valid'
    assert result['efficiency_advantage'] is True
    swapped = compare_primary(b, a, np.ones(40), np.ones(40), 80, **VERIFIED)
    assert swapped['effect'] == 2
    assert swapped['ci'] == pytest.approx([-result['ci'][1], -result['ci'][0]])
    assert swapped['variance']['total'] == result['variance']['total']


def test_census_retains_timing_variance_and_aa_can_have_uncertainty():
    a = np.tile([9., 11.], (40, 1))
    b = np.tile([7., 13.], (40, 1))
    result = compare_primary(a, b, np.ones(40), np.ones(40), 40, **VERIFIED)
    assert result['effect'] == 0
    assert result['variance']['sampling'] == 0
    assert result['variance']['total'] == .1
    assert result['ci'] == pytest.approx([-.6197950323, .6197950323], abs=1e-9)
    assert result['status'] == 'valid'
    identical = compare_primary(a, a, np.ones(40), np.ones(40), 40, **VERIFIED)
    assert identical['effect'] == 0
    assert identical['ci'] == [0, 0]


def test_perfect_common_timing_noise_cancels():
    a = np.tile([9., 11.], (40, 1))
    b = np.tile([10., 12.], (40, 1))
    result = compare_primary(a, b, np.ones(40), np.ones(40), 80, **VERIFIED)
    assert result['variance']['mean_timing_noise'] == 0
    assert result['variance']['total'] == 0
    assert result['ci'] == [-1, -1]


def test_success_scaling_in_timing_and_ratio():
    a = np.tile([9., 11.], (80, 1))
    b = np.tile([8., 12.], (80, 1))
    sa = np.r_[np.ones(40), np.zeros(40)]
    result = compare_primary(a, b, sa, np.ones(80), 80, **VERIFIED)
    assert result['effect'] == 10  # 800/40 - 800/80
    assert result['variance']['mean_timing_noise'] == 0  # scaled paired noise cancels
    assert result['variance']['total'] == 0


def test_below_30_successes_has_no_gaussian_ci():
    result = compare_primary(np.ones((40, 2)), np.full((40, 2), 2.),
                             np.r_[np.ones(29), np.zeros(11)], np.ones(40), 100, **VERIFIED)
    assert result['effect'] == pytest.approx(40 / 29 - 2)
    assert result['ci'] is None
    assert result['status'] == 'inconclusive'
    assert 'insufficient_successes' in result['reasons']
    json.dumps(result, allow_nan=False)


def test_full_leave_one_out_and_single_question_sign_sensitivity():
    a = np.tile([9., 9.], (40, 1))
    a[0] = [89., 89.]
    b = np.full((40, 2), 10.)
    result = compare_primary(a, b, np.ones(40), np.ones(40), 40, **VERIFIED)
    assert result['effect'] == 1
    loo = result['sensitivity']['leave_one_out']
    assert len(loo) == 40
    assert loo[0]['effect'] == -1
    assert loo[1]['effect'] == pytest.approx(41 / 39)
    assert [r['omitted_index'] for r in loo] == list(range(40))
    assert all('ci' in r and 'interval_conclusion' in r for r in loo)
    assert result['sensitivity']['effect_sign_sensitive'] is True
    assert result['sensitivity']['interval_sign_sensitive'] is True
    assert result['status'] == 'inconclusive'
    assert result['efficiency_advantage'] is False


@pytest.mark.parametrize('flag', ['timing_stationary', 'deterministic_outputs'])
def test_recorded_invalidity_overrides_numerical_interval(flag):
    flags = {**VERIFIED, flag: False}
    result = compare_primary(np.ones((40, 2)), np.full((40, 2), 2.),
                             np.ones(40), np.ones(40), 80, **flags)
    assert result['effect'] == -1
    assert result['ci'] == [-1, -1]
    assert result['status'] == 'invalid'
    assert result['efficiency_advantage'] is False


def test_unverified_flags_and_dominant_review_do_not_certify_run():
    args = (np.ones((40, 2)), np.full((40, 2), 2.), np.ones(40), np.ones(40), 80)
    result = compare_primary(*args)
    assert result['status'] == 'inconclusive'
    assert result['effect'] == -1
    assert result['efficiency_advantage'] is False
    assert compare_primary(*args, **{**VERIFIED, 'single_dominant': True})['status'] == 'inconclusive'


def test_one_repeat_requires_frozen_conservative_noise_with_provenance():
    args = (np.ones((40, 1)), np.full((40, 1), 2.), np.ones(40), np.ones(40), 40)
    with pytest.raises(ValueError):
        compare_primary(*args, **VERIFIED)
    noise = {'covariances': np.tile([[4., 2.], [2., 9.]], (40, 1, 1)),
             'provenance': 'frozen-invented-length-strata-v1', 'conservative': True}
    result = compare_primary(*args, **VERIFIED, one_repeat_timing_noise=noise)
    assert result['variance']['mean_timing_noise'] == 9
    assert result['variance']['total'] == .225
    assert result['sensitivity']['timing_noise_source']['provenance'] == noise['provenance']
    assert result['sensitivity']['timing_noise_source']['limitation']
    with pytest.raises(ValueError):
        compare_primary(*args, **VERIFIED, one_repeat_timing_noise={**noise, 'provenance': ''})


@pytest.mark.parametrize('change', ['population', 'shape', 'repetitions', 'flag', 'successes'])
def test_primary_rejects_malformed_inputs(change):
    a = np.ones((40, 2))
    b = a.copy()
    sa, sb, N, flags = np.ones(40), np.ones(40), 80, dict(VERIFIED)
    if change == 'population':
        N = 39
    elif change == 'shape':
        b = np.ones((39, 2))
    elif change == 'repetitions':
        b = np.ones((40, 3))
    elif change == 'flag':
        flags['timing_stationary'] = 'yes'
    elif change == 'successes':
        sa[0] = .5
    with pytest.raises(ValueError):
        compare_primary(a, b, sa, sb, N, **flags)


def test_ratio_influence_variance_scales_unequal_success_outcomes():
    # pA=pB=3/4, RA=8/3, RB=4. Influences: ten -44/9,
    # twenty 4/9, ten 4; sum squares=10880/27, ddof=1 divides by 39.
    sa = np.r_[np.ones(30), np.zeros(10)]
    sb = np.r_[np.zeros(10), np.ones(30)]
    result = compare_primary(np.full((40, 2), 2.), np.full((40, 2), 3.), sa, sb, 80, **VERIFIED)
    assert result['effect'] == pytest.approx(-4 / 3)
    assert result['variance']['sampling'] == pytest.approx(136 / 1053)
    assert result['sensitivity']['influences'] == pytest.approx([-44 / 9] * 10 + [4 / 9] * 20 + [4] * 10)
    assert result['variance']['timing_restoration'] == 0
    assert result['status'] == 'inconclusive'  # deleting a success leaves only 29
    assert 'leave_one_out_unresolved' in result['reasons']
    assert sum(row['ci'] is None for row in result['sensitivity']['leave_one_out']) == 40


def test_quality_guards_keep_four_different_quality_comparisons():
    rows = [dict(candidate_joint_em=int(i < 20), comparator_joint_em=int(i < 10),
                 fixed_ten_joint_em=int(i < 30), candidate_answer_em=int(i < 30),
                 comparator_answer_em=int(i < 20), fixed_ten_answer_em=int(i < 35))
            for i in range(40)]
    results = quality_guards(rows, 40)
    actual = {(r['metric'], r['comparator']): (r['difference'], r['ci'], r['preserved'])
              for r in results}
    assert actual == {('joint_em', 'selected'): (.25, [.25, .25], True),
                      ('answer_em', 'selected'): (.25, [.25, .25], True),
                      ('joint_em', 'fixed_ten'): (-.25, [-.25, -.25], False),
                      ('answer_em', 'fixed_ten'): (-.125, [-.125, -.125], False)}


@pytest.mark.parametrize('covariance', [[[1., 2.], [2., 1.]], [[1., 2.], [0., 1.]],
                                     [[float('nan'), 0.], [0., 1.]]])
def test_one_repeat_rejects_invalid_development_covariance(covariance):
    noise = {'covariances': np.tile(covariance, (40, 1, 1)),
             'provenance': 'frozen-invented', 'conservative': True}
    with pytest.raises(ValueError):
        compare_primary(np.ones((40, 1)), np.full((40, 1), 2.), np.ones(40), np.ones(40),
                        40, **VERIFIED, one_repeat_timing_noise=noise)


def test_one_repeat_fallback_rescales_noise_in_leave_one_out():
    # 40/80 A successes, 80/80 B; development variance A=1,B=4,cov=0.
    # Full scaled mean-noise variance=8. Deleting an A success changes pA to 39/79.
    noise = {'covariances': np.tile([[1., 0.], [0., 4.]], (80, 1, 1)),
             'provenance': 'frozen-invented', 'conservative': True}
    result = compare_primary(np.ones((80, 1)), np.full((80, 1), 2.),
                             np.r_[np.ones(40), np.zeros(40)], np.ones(80), 80,
                             **VERIFIED, one_repeat_timing_noise=noise)
    assert result['variance']['mean_timing_noise'] == 8
    assert result['variance']['total'] == .1
    # This verifies LOO reweighting retains finite diagnostics rather than reusing
    # an already-scaled contrast-variance estimate from the full sample.
    assert result['sensitivity']['leave_one_out'][0]['effect'] == pytest.approx(1 / 39)
    assert result['sensitivity']['leave_one_out'][40]['effect'] == pytest.approx(-1 / 40)


def test_single_question_quality_variance_is_explicitly_undefined_outside_census():
    partial = paired_quality_bounds(np.ones(1), np.zeros(1), 10, .05)
    assert partial['sampling_variance'] is None
    assert partial['variance_reason'] == 'insufficient_sample_variance'
    census = paired_quality_bounds(np.ones(1), np.zeros(1), 1, .05)
    assert census['ci'] == [1, 1]
    assert census['sampling_variance'] == 0
    json.dumps(partial, allow_nan=False)


def test_derived_overflow_is_rejected_instead_of_emitting_infinity():
    with pytest.raises(ValueError):
        efficiency(np.full((40, 2), 1e308), np.ones(40))

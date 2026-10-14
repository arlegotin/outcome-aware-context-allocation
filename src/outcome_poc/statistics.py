"""Analysis-only uncertainty for a fixed finite benchmark, not future queries.

Timing columns are paired repetitions inside questions. Numerical intervals alone
never certify stationarity, deterministic outcomes or an influence review.
"""

from numbers import Integral, Real

import numpy as np
from scipy.stats import hypergeom


_NORMAL_975 = 1.959963984540054
_GUARD_TAIL_ALPHA = .05 / 16


def _integer(value, name: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')
    return int(value)


def _population(n: int, N: int) -> int:
    N = _integer(N, 'N', 1)
    if not 1 <= n <= N:
        raise ValueError('require 1 <= n <= N')
    return N


def _alpha(alpha: float) -> float:
    if isinstance(alpha, (bool, np.bool_)) or not isinstance(alpha, Real) or not 0 < alpha < 1:
        raise ValueError('tail probability must be finite and strictly between zero and one')
    return float(alpha)


def _real_array(values, name: str) -> np.ndarray:
    array = np.asarray(values)
    if array.dtype.kind not in 'bifu':
        raise ValueError(f'{name} must contain real numbers')
    array = array.astype(np.float64)
    if not np.isfinite(array).all():
        raise ValueError(f'{name} must be complete and finite')
    return array


def _binary(values, name: str) -> np.ndarray:
    array = _real_array(values, name)
    if array.ndim != 1 or not array.size or not np.isin(array, [0, 1]).all():
        raise ValueError(f'{name} must be a nonempty binary vector')
    return array


def _times(values, successes: np.ndarray) -> np.ndarray:
    array = _real_array(values, 'times')
    if array.ndim != 2 or array.shape[0] != len(successes) or array.shape[1] < 1 or not (array > 0).all():
        raise ValueError('times must have shape (n, repetitions), with finite positive entries')
    return array


def _finite(value) -> float:
    value = float(value)
    if not np.isfinite(value):
        raise ValueError('derived numerical result is not finite')
    return value


def efficiency(times: np.ndarray, successes: np.ndarray) -> dict:
    """Sum question-level mean times over successes, retaining all failed work."""
    successes = _binary(successes, 'successes')
    times = _times(times, successes)
    with np.errstate(over='raise', invalid='raise'):
        try:
            total_time = _finite(times.mean(axis=1).sum())
        except FloatingPointError as error:
            raise ValueError('timing arithmetic overflow') from error
    count = int(successes.sum())
    return {'n': len(successes), 'repetitions': times.shape[1], 'success_count': count,
            'quality': count / len(successes), 'total_time': total_time,
            'mean_time': total_time / len(successes),
            'ratio': _finite(total_time / count) if count else None,
            'reason': None if count else 'zero_successes'}


def _count_inputs(x: int, n: int, N: int, alpha: float) -> tuple[int, int, int, float]:
    x, n = _integer(x, 'x'), _integer(n, 'n', 1)
    N, alpha = _population(n, N), _alpha(alpha)
    if x > n:
        raise ValueError('observed count cannot exceed n')
    return x, n, N, alpha


def _upper_count(x: int, n: int, N: int, alpha: float) -> int:
    # Retain the largest feasible K not rejected by P_K(X <= x) < alpha.
    low, high = x, N - n + x
    while low < high:
        middle = (low + high + 1) // 2
        if hypergeom.cdf(x, N, middle, n) >= alpha:
            low = middle
        else:
            high = middle - 1
    return low


def finite_population_upper(x: int, n: int, N: int, alpha: float = .05) -> float:
    """One-sided exact upper proportion bound for sampling without replacement."""
    x, n, N, alpha = _count_inputs(x, n, N, alpha)
    return _upper_count(x, n, N, alpha) / N


def finite_population_lower(x: int, n: int, N: int, alpha: float = .05) -> float:
    """Complement of the exact upper count bound; exact at a census."""
    x, n, N, alpha = _count_inputs(x, n, N, alpha)
    return (N - _upper_count(n - x, n, N, alpha)) / N


def paired_quality_bounds(a: np.ndarray, b: np.ndarray, N: int, tail_alpha: float) -> dict:
    """Exact rescue-minus-harm bounds; normal variance is diagnostic only.

    Each of the four count tails uses tail_alpha. The result describes A-B.
    Sparse means either observed discordance count is below ten.
    """
    a, b = _binary(a, 'a'), _binary(b, 'b')
    if a.shape != b.shape:
        raise ValueError('paired outcomes must have identical shape')
    n, N, tail_alpha = len(a), _population(len(a), N), _alpha(tail_alpha)
    rescue = int(((a == 1) & (b == 0)).sum())
    harm = int(((a == 0) & (b == 1)).sum())
    rescue_lower = finite_population_lower(rescue, n, N, tail_alpha)
    rescue_upper = finite_population_upper(rescue, n, N, tail_alpha)
    harm_lower = finite_population_lower(harm, n, N, tail_alpha)
    harm_upper = finite_population_upper(harm, n, N, tail_alpha)
    variance = 0. if n == N else (_finite((1 - n / N) * np.var(a - b, ddof=1) / n) if n > 1 else None)
    ci = [rescue_lower - harm_upper, rescue_upper - harm_lower]
    return {'n': n, 'N': N, 'difference': (rescue - harm) / n,
            'rescue_count': rescue, 'harm_count': harm,
            'rescue_bounds': [rescue_lower, rescue_upper], 'harm_bounds': [harm_lower, harm_upper],
            'ci': ci, 'tail_alpha': tail_alpha, 'sparse': rescue < 10 or harm < 10,
            'sampling_variance': variance,
            'variance_reason': 'insufficient_sample_variance' if variance is None else None,
            'preserved': ci[0] >= 0}


def quality_guards(rows: list[dict], N: int) -> list[dict]:
    """Fixed four-guard family, with alias duplicates retained conservatively.

    One row per assigned question has candidate_joint_em, comparator_joint_em,
    fixed_ten_joint_em and corresponding *_answer_em values. Comparator is the
    frozen selected B*. All six fields are required; repetitions are not rows.
    """
    if not isinstance(rows, list) or not rows:
        raise ValueError('quality guards require complete assigned-question rows')
    _population(len(rows), N)
    fields = [f'{arm}_{metric}' for arm in ('candidate', 'comparator', 'fixed_ten')
              for metric in ('joint_em', 'answer_em')]
    if any(not isinstance(row, dict) or any(field not in row for field in fields) for row in rows):
        raise ValueError('all six quality fields are required on every row')
    arrays = {field: _binary([row[field] for row in rows], field) for field in fields}
    results = []
    for comparator, arm in [('selected', 'comparator'), ('fixed_ten', 'fixed_ten')]:
        for metric in ('joint_em', 'answer_em'):
            result = paired_quality_bounds(arrays[f'candidate_{metric}'], arrays[f'{arm}_{metric}'],
                                           N, _GUARD_TAIL_ALPHA)
            results.append({'metric': metric, 'comparator': comparator, **result})
    return results


def _noise_input(noise: dict | None, n: int, repetitions: int) -> tuple[np.ndarray | None, dict]:
    if repetitions >= 2:
        if noise is not None:
            raise ValueError('one-repeat fallback cannot override measured repetitions')
        return None, {'kind': 'paired_repetitions', 'provenance': None, 'limitation': None}
    if not isinstance(noise, dict) or noise.get('conservative') is not True:
        raise ValueError('one repetition requires a frozen conservative development noise estimate')
    provenance = noise.get('provenance')
    if not isinstance(provenance, str) or not provenance.strip() or 'covariances' not in noise:
        raise ValueError('one-repeat estimate requires covariance matrices and frozen provenance')
    matrices = _real_array(noise['covariances'], 'development timing covariances')
    if matrices.shape != (n, 2, 2) or not np.array_equal(matrices, matrices.transpose(0, 2, 1)):
        raise ValueError('timing covariances must be symmetric matrices of shape (n, 2, 2)')
    if (np.linalg.eigvalsh(matrices) < 0).any():
        raise ValueError('timing covariance matrices must be positive semidefinite')
    return matrices, {'kind': 'frozen_development_fallback', 'provenance': provenance,
                     'limitation': 'One repetition cannot estimate confirmation timing noise; '
                                   'uses supplied conservative development length-stratum covariance.'}


def _conclusion(ci: list | None) -> str | None:
    if ci is None:
        return None
    if ci[1] < 0:
        return 'negative'
    if ci[0] > 0:
        return 'positive'
    return 'includes_zero'


def _primary_numbers(ta: np.ndarray, tb: np.ndarray, sa: np.ndarray, sb: np.ndarray,
                     N: int, noise: np.ndarray | None) -> dict:
    n = len(sa)
    empty_variance = dict(sampling=None, mean_timing_noise=None, timing_restoration=None, total=None)
    if n == 0 or sa.sum() == 0 or sb.sum() == 0:
        return {'effect': None, 'ci': None, 'variance': empty_variance, 'influences': [],
                'reason': 'empty_sample' if n == 0 else 'zero_successes'}
    pa, pb = sa.mean(), sb.mean()
    ma, mb = ta.mean(axis=1), tb.mean(axis=1)
    ra, rb = ma.mean() / pa, mb.mean() / pb
    effect = _finite(ra - rb)
    z = (ma - ra * sa) / pa - (mb - rb * sb) / pb
    if noise is None:
        v = np.var(ta / pa - tb / pb, axis=1, ddof=1) / ta.shape[1]
    else:
        contrast = np.array([1 / pa, -1 / pb])
        v = np.einsum('i,nij,j->n', contrast, noise, contrast)
        # Roundoff in a PSD quadratic form cannot represent negative variance.
        v = np.maximum(v, 0.)
    mean_noise = _finite(v.mean())
    sampling = 0. if n == N else (_finite((1 - n / N) * np.var(z, ddof=1) / n) if n > 1 else None)
    restoration = _finite(mean_noise / N)  # f * mean(v_i) / n
    total = _finite(sampling + restoration) if sampling is not None else None
    reason = 'insufficient_successes' if min(sa.sum(), sb.sum()) < 30 else None
    ci = None
    if reason is None:
        half_width = _NORMAL_975 * np.sqrt(total)
        ci = [_finite(effect - half_width), _finite(effect + half_width)]
    return {'effect': effect, 'ci': ci, 'reason': reason,
            'variance': {'sampling': sampling, 'mean_timing_noise': mean_noise,
                         'timing_restoration': restoration, 'total': total},
            'influences': [_finite(value) for value in z]}


def compare_primary(times_a: np.ndarray, times_b: np.ndarray, success_a: np.ndarray,
                    success_b: np.ndarray, N: int, *, timing_stationary: bool | None = None,
                    deterministic_outputs: bool | None = None, single_dominant: bool | None = None,
                    one_repeat_timing_noise: dict | None = None) -> dict:
    """Approximate primary A-B ratio interval and complete leave-one-out review.

    Supply recorded timing_stationary/deterministic_outputs assessments and an
    explicit single_dominant influence-review flag. Unknown flags withhold a
    valid claim; false stationarity/determinism invalidates cost inference.
    single_dominant=True makes inference inconclusive, without an invented
    universal influence threshold. Numerical sign changes also gate inference.
    Thirty successes per arm is necessary, not sufficient: if deletion leaves
    fewer than thirty, its LOO interval is suppressed and sensitivity remains
    unresolved. Forecasting must account for this numerical boundary limitation.

    With one repetition, one_repeat_timing_noise must contain frozen conservative
    per-question 2x2 arm timing covariance matrices, conservative=True, and a
    nonempty provenance identifier. Units are seconds squared for one paired
    timing block; success scaling is applied here, including in leave-one-out.
    This contract cannot itself verify the supplied estimate was frozen.
    """
    sa, sb = _binary(success_a, 'success_a'), _binary(success_b, 'success_b')
    ta, tb = _times(times_a, sa), _times(times_b, sb)
    if sa.shape != sb.shape or ta.shape != tb.shape:
        raise ValueError('arms must contain the same questions and paired repetitions')
    n, N = len(sa), _population(len(sa), N)
    flags = dict(timing_stationary=timing_stationary, deterministic_outputs=deterministic_outputs,
                 single_dominant=single_dominant)
    if any(value is not None and not isinstance(value, bool) for value in flags.values()):
        raise ValueError('recorded review flags must be booleans or None')
    noise, noise_source = _noise_input(one_repeat_timing_noise, n, ta.shape[1])
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        try:
            result = _primary_numbers(ta, tb, sa, sb, N, noise)
            loo = []
            for index in range(n):
                keep = np.arange(n) != index
                numbers = _primary_numbers(ta[keep], tb[keep], sa[keep], sb[keep], N,
                                           noise[keep] if noise is not None else None)
                loo.append({'omitted_index': index, 'effect': numbers['effect'], 'ci': numbers['ci'],
                            'interval_conclusion': _conclusion(numbers['ci']), 'reason': numbers['reason']})
        except FloatingPointError as error:
            raise ValueError('primary arithmetic overflow or invalid numerical result') from error
    conclusion = _conclusion(result['ci'])
    effect_sign_sensitive = any(row['effect'] is not None and result['effect'] is not None
                                and np.sign(row['effect']) != np.sign(result['effect']) for row in loo)
    interval_sign_sensitive = any(row['interval_conclusion'] is not None and conclusion is not None
                                  and row['interval_conclusion'] != conclusion for row in loo)
    reasons = [result['reason']] if result['reason'] else []
    for name in ('timing_stationary', 'deterministic_outputs'):
        if flags[name] is None:
            reasons.append(f'{name}_unverified')
        elif flags[name] is False:
            reasons.append('unstable_timing' if name == 'timing_stationary' else 'nondeterministic_outputs')
    if single_dominant is None:
        reasons.append('influence_review_unverified')
    elif single_dominant:
        reasons.append('single_dominant')
    if effect_sign_sensitive:
        reasons.append('effect_sign_sensitive')
    if interval_sign_sensitive:
        reasons.append('interval_sign_sensitive')
    if result['ci'] is not None and any(row['ci'] is None for row in loo):
        reasons.append('leave_one_out_unresolved')
    status = 'invalid' if timing_stationary is False or deterministic_outputs is False else (
        'inconclusive' if reasons else 'valid')
    return {'n': n, 'N': N, 'repetitions': ta.shape[1],
            'arm_a': efficiency(ta, sa), 'arm_b': efficiency(tb, sb),
            'effect': result['effect'], 'ci': result['ci'], 'variance': result['variance'],
            'interval_conclusion': conclusion, 'status': status, 'reasons': reasons,
            'efficiency_advantage': status == 'valid' and conclusion == 'negative',
            'recorded_flags': flags,
            'sensitivity': {'leave_one_out': loo, 'influences': result['influences'],
                            'largest_influence_indices': sorted(range(len(result['influences'])),
                                key=lambda i: abs(result['influences'][i]), reverse=True)[:5],
                            'effect_sign_sensitive': effect_sign_sensitive,
                            'interval_sign_sensitive': interval_sign_sensitive,
                            'timing_noise_source': noise_source}}

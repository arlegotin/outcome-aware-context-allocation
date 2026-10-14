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


def analyze_run(protocol: dict, scored_rows: list, events: list, *, validity_assessment: dict | None = None) -> dict:
    """Closed-run consumer: exact jobs, raw paired repetitions and evidence flags.

    This never trains/selects, changes the sample, or treats repetitions as tasks.
    Unknown stationarity and influence assessments explicitly withhold a claim.
    """
    import json
    from pathlib import Path
    from .protocol import file_hash
    from .protected import validate_run
    from .storage import content_hash, read_jsonl
    from .runner import load_events
    root=Path(protocol['run_dir'])
    validate_run(protocol,root)
    marker=json.loads((root/'scores.jsonl.closed.json').read_text())
    if marker['protocol_hash']!=protocol['protocol_hash'] or any(file_hash(root/name)!=h for name,h in marker['hashes'].items()):
        raise ValueError('analysis score closure checksum mismatch')
    jobs=protocol['schedule']['jobs']; expected=[j['job_id'] for j in jobs]
    if [s.job_id for s in scored_rows]!=expected: raise ValueError('analysis requires full assigned schedule')
    if [content_hash(s) for s in scored_rows]!=[content_hash(r) for r in read_jsonl(root/'scores.jsonl')]:
        raise ValueError('analysis score values differ from closed scores')
    actual_events=load_events(root)
    if sorted(content_hash(e) for e in events)!=sorted(content_hash(e) for e in actual_events):
        raise ValueError('analysis events differ from complete accounted attempts')
    evidence=json.loads((root/'job-evidence.json').read_text())
    byjob={s.job_id:s for s in scored_rows}; info={j['job_id']:j for j in evidence['jobs']}
    if set(info)!=set(expected) or any(info[s.job_id]['score_hash']!=content_hash(s) for s in scored_rows):
        raise ValueError('analysis job evidence mapping mismatch')
    ids=protocol['sample']['task_ids']; reps=protocol['methods']['repetitions']; N=protocol['sample']['N']
    lookup={(j['task_id'],j['scope'],j['arm'],j['repetition_id']):j for j in jobs if j['scope'] in ('primary','anchor')}
    ta=[];tb=[];sa=[];sb=[];quality=[];raw=[];mismatches=[]
    position={j['job_id']:i for i,j in enumerate(jobs)}
    for tid in ids:
        arms={}
        for arm in ('A','B'):
            selected=[lookup[(tid,'primary',arm,r)] for r in range(1,reps+1)]
            rows=[byjob[j['job_id']] for j in selected]
            signatures=[info[j['job_id']]['output_parity_hash'] for j in selected]
            if len(set(signatures))!=1 or len({(s.joint_em,s.answer_em) for s in rows})!=1:
                mismatches.append({'task_id':tid,'arm':arm,'job_ids':[j['job_id'] for j in selected]})
            arms[arm]=(selected,rows)
        aa=[s.total_serving_seconds for s in arms['A'][1]];bb=[s.total_serving_seconds for s in arms['B'][1]]
        ta.append(aa);tb.append(bb)
        a,b=arms['A'][1][0],arms['B'][1][0]
        sa.append(a.joint_em);sb.append(b.joint_em)
        anchor=byjob[lookup[(tid,'anchor',None,0)]['job_id']]
        quality.append({'candidate_joint_em':a.joint_em,'comparator_joint_em':b.joint_em,'fixed_ten_joint_em':anchor.joint_em,
            'candidate_answer_em':a.answer_em,'comparator_answer_em':b.answer_em,'fixed_ten_answer_em':anchor.answer_em})
        raw.append({'task_id':tid,'A_seconds':aa,'B_seconds':bb,'A_joint_em':a.joint_em,'B_joint_em':b.joint_em,
            'pair_order':['AB' if position[x['job_id']]<position[y['job_id']] else 'BA'
                          for x,y in zip(arms['A'][0],arms['B'][0])],
            'pair_positions':[[position[x['job_id']],position[y['job_id']]] for x,y in zip(arms['A'][0],arms['B'][0])],
            'prompt_tokens':[info[j['job_id']]['prompt_tokens'] for arm in ('A','B') for j in arms[arm][0]],
            'first_serving_start_ns':min(info[j['job_id']]['final_serving_start_ns'] for arm in ('A','B') for j in arms[arm][0]),
            'paired_covariance_seconds_squared':np.cov(np.array([aa,bb]),ddof=1).tolist()})
    ta=np.array(ta);tb=np.array(tb);sa=np.array(sa);sb=np.array(sb)
    deterministic=not mismatches
    primary=compare_primary(ta,tb,sa,sb,N,deterministic_outputs=deterministic,
                            timing_stationary=None,single_dominant=None)
    centered=(ta-tb)-(ta-tb).mean(axis=1,keepdims=True)
    order={order:[float(centered[i,r]) for i,row in enumerate(raw) for r,o in enumerate(row['pair_order']) if o==order]
           for order in ('AB','BA')}
    families={}
    for scope in ('representative','anchor','random','oracle-source'):
        configs=sorted({j['method']['config_id'] for j in jobs if j['scope']==scope})
        for config in configs:
            assigned=[j for j in jobs if j['scope']==scope and j['method']['config_id']==config]
            if {j['task_id'] for j in assigned}!=set(ids) or len(assigned)!=len(ids):
                raise ValueError('family assigned denominator incomplete')
            rows=[byjob[j['job_id']] for j in assigned]
            families[scope+':'+config]={**efficiency(np.array([[s.total_serving_seconds] for s in rows]),np.array([s.joint_em for s in rows])),
                'answer_em':sum(s.answer_em for s in rows)/len(rows),'scope':scope,'config_id':config,
                'job_ids':[j['job_id'] for j in assigned]}
    # Descriptive partitions are fixed rank partitions, not post-outcome tests or cutoffs.
    def partitions(key,count):
        ordered=sorted(range(len(raw)),key=lambda i:(key(raw[i]),raw[i]['task_id']))
        output=[]
        for group in range(count):
            members=ordered[len(ordered)*group//count:len(ordered)*(group+1)//count]
            if not members: continue
            differences=[float(ta[i,r]-tb[i,r]) for i in members for r in range(reps)]
            output.append({'group':group,'task_ids':[raw[i]['task_id'] for i in members],
                'paired_difference_seconds':differences,'mean_paired_difference_seconds':float(np.mean(differences))})
        return output
    timing={'question_centered_by_order':order,'question_centered_by_repetition':centered.T.tolist(),
        'chronological_blocks':partitions(lambda r:r['first_serving_start_ns'],4),
        'length_strata':partitions(lambda r:max(r['prompt_tokens']),3),
        'assessment_rule':protocol['methods']['statistics']['actual_run_assessment'],
        'operational_state_hashes':{name:file_hash(root/name) for name in ('resources.jsonl','system-state.jsonl','power.jsonl') if (root/name).exists()}}
    binding={'protocol_hash':protocol['protocol_hash'],
        'prediction_closure_hash':file_hash(root/'predictions.closed.json'),
        'score_closure_hash':file_hash(root/'scores.jsonl.closed.json'),
        'timing_evidence_hash':content_hash({'raw_pairs':raw,'diagnostics':timing}),
        'influence_evidence_hash':content_hash(primary['sensitivity']),
        'assessment_rule_hash':content_hash(protocol['methods']['statistics']['actual_run_assessment'])}
    if validity_assessment is not None:
        if not isinstance(validity_assessment,dict) or any(validity_assessment.get(k)!=v for k,v in binding.items()):
            raise ValueError('validity assessment evidence binding mismatch')
        for field in ('reviewer','timing_rationale','influence_rationale'):
            if not isinstance(validity_assessment.get(field),str) or not validity_assessment[field].strip():
                raise ValueError('validity assessment requires reviewer and rationale')
        for field in ('timing_stationary','single_dominant'):
            if field not in validity_assessment or (validity_assessment[field] is not None and type(validity_assessment[field]) is not bool):
                raise ValueError('invalid assessment flag')
        primary=compare_primary(ta,tb,sa,sb,N,deterministic_outputs=deterministic,
            timing_stationary=validity_assessment['timing_stationary'],single_dominant=validity_assessment['single_dominant'])
    guards=quality_guards(quality,N)
    quality_valid=deterministic and all(g['preserved'] for g in guards)
    return {'protocol_hash':protocol['protocol_hash'],'assigned_unique_tasks':len(ids),'population':N,
        'primary':primary,'quality_guards':guards,'quality_claim_valid':quality_valid,'quality_outcomes_valid':deterministic,
        'repeated_output_mismatches':mismatches,'raw_paired_rows':raw,'families':families,
        'assessment_binding':binding,'validity_assessment':validity_assessment,
        'validity_assessment_hash':content_hash(validity_assessment) if validity_assessment else None,
        'flag_evidence':{'deterministic_outputs':'Exact same-arm raw/parsed/status/evidence/action/prompt/token parity and binary scores across all assigned fresh repetitions',
            'timing_stationary':validity_assessment['timing_rationale'] if validity_assessment else 'Unverified; retain centered paired contrasts/order/repetition/block/resource evidence for documented review',
            'single_dominant':validity_assessment['influence_rationale'] if validity_assessment else 'Unverified; all leave-one-out effects and intervals retained for documented review'},
        'timing_diagnostics':timing,
        'nondeterministic_qualification':None if deterministic else 'Primary invalid; first scheduled repetition binary values are descriptive only, never averaged',
        'total_physical_serving_seconds':sum(s.total_serving_seconds for s in scored_rows),
        'total_physical_experiment_seconds':sum(s.total_experiment_seconds for s in scored_rows),
        'all_family_superiority':'not prespecified',
        'outcome':'qualified positive' if primary['efficiency_advantage'] and quality_valid else 'inconclusive'}

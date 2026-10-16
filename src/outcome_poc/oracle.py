"""Outcome-enabled pilot analysis; never imported by the serving scheduler."""

from .schemas import PairedActionRow, validate_record


def _validate(rows):
    if not rows or len({row.task_id for row in rows}) != len(rows):
        raise ValueError('paired rows require nonempty unique assignments')
    for row in rows:
        validate_record(row)


def _point(n, successes, seconds, task_id=None):
    return {'n': n, 'successes': successes, 'quality': successes/n,
            'total_seconds': seconds, 'seconds_per_success': seconds/successes if successes else None,
            'reason': None if successes else 'zero_successes', 'switched_task_id': task_id}


def oracle_frontier(rows: list[PairedActionRow]) -> list[dict]:
    """Clairvoyant, zero-overhead empirical frontier; allow either cheap action."""
    _validate(rows)
    seconds, successes, switches = 0., 0, []
    for row in rows:
        small_first = row.small_cost_seconds <= row.full_cost_seconds
        cheap_cost, expensive_cost = ((row.small_cost_seconds, row.full_cost_seconds) if small_first
                                      else (row.full_cost_seconds, row.small_cost_seconds))
        cheap_success, expensive_success = ((row.small_joint_em, row.full_joint_em) if small_first
                                            else (row.full_joint_em, row.small_joint_em))
        seconds += cheap_cost
        successes += cheap_success
        if expensive_success > cheap_success:
            switches.append((expensive_cost-cheap_cost, row.task_id))
    result = [_point(len(rows), successes, seconds)]
    for delta, identity in sorted(switches):
        seconds += delta
        successes += 1
        result.append(_point(len(rows), successes, seconds, identity))
    return result


def headroom(rows: list[PairedActionRow]) -> dict:
    _validate(rows)
    cells = {'both_fail': 0, 'rescue': 0, 'harm': 0, 'both_success': 0}
    names = {(0, 0): 'both_fail', (0, 1): 'rescue', (1, 0): 'harm', (1, 1): 'both_success'}
    for row in rows:
        cells[names[row.small_joint_em, row.full_joint_em]] += 1
    small, full = sum(row.small_joint_em for row in rows), sum(row.full_joint_em for row in rows)
    return {'n': len(rows), 'cells': cells, 'rescues': cells['rescue'], 'harms': cells['harm'],
            'net_full_minus_small': full-small,
            'oracle_quality': sum(max(row.small_joint_em, row.full_joint_em) for row in rows)/len(rows),
            'discordance': cells['rescue']+cells['harm'],
            'evidence': 'informative' if cells['rescue']+cells['harm'] else 'insufficient_evidence',
            'fixed_two': _point(len(rows), small, sum(row.small_cost_seconds for row in rows)),
            'fixed_ten': _point(len(rows), full, sum(row.full_cost_seconds for row in rows)),
            'oracle_frontier': oracle_frontier(rows),
            'scope': 'clairvoyant development diagnostic; future outcomes and zero gate overhead'}


def analyze_pilot(run_dir, scores_path, output_dir, remaining_seconds, *, planned_jobs=1920, setup_allowance_seconds=1800,
                  extension_run_dirs=(), extension_scores_paths=()):
    """Analyze a closed ledger and separate scorer output, with no corpus text."""
    import csv
    from collections import Counter
    import json
    from pathlib import Path
    from .pilot import capacity_forecast, job_components
    from .runner import validate_closed_accounting, _prediction
    from .storage import atomic_json, append_jsonl, content_hash, read_jsonl
    root, output = Path(run_dir), Path(output_dir)
    costs = json.loads((root/'pilot_costs.json').read_text())
    schedule = json.loads((root/'schedule.json').read_text())
    predictions = [_prediction(row) for row in read_jsonl(root/'predictions.jsonl')]
    validate_closed_accounting(root, predictions)
    scores_list = list(read_jsonl(Path(scores_path)))
    if len(extension_run_dirs) != len(extension_scores_paths):
        raise ValueError('extension ledgers and score paths must pair exactly')
    source_closures = [{'run_dir': str(root), 'closure': costs['closure']}]
    source_runs = [str(root)]
    for extension_root, extension_scores in zip(extension_run_dirs, extension_scores_paths):
        extension_root = Path(extension_root)
        extra = json.loads((extension_root/'pilot_costs.json').read_text())
        extra_schedule = json.loads((extension_root/'schedule.json').read_text())
        extra_predictions = [_prediction(row) for row in read_jsonl(extension_root/'predictions.jsonl')]
        validate_closed_accounting(extension_root, extra_predictions)
        source_closures.append({'run_dir': str(extension_root), 'closure': extra['closure']})
        source_runs.append(str(extension_root))
        predictions.extend(extra_predictions)
        scores_list.extend(read_jsonl(Path(extension_scores)))
        if set(schedule['assigned_ids']) & set(extra_schedule['assigned_ids']):
            raise ValueError('pilot extension must be disjoint; old pairs cannot be repeated as tasks')
        schedule['assigned_ids'] += extra_schedule['assigned_ids']
        schedule['all_k_ids'] += extra_schedule['all_k_ids']
        costs['observations'] += extra['observations']
        costs['assigned_tasks'] += extra['assigned_tasks']
        costs['scheduled_calls'] += extra['scheduled_calls']
        costs['generation_calls'] += extra['generation_calls']
        costs['determinism']['checks'] += extra['determinism']['checks']
        costs['determinism']['passed'] &= extra['determinism']['passed']
        costs['feature_overhead_seconds_per_task'] = max(costs.get('feature_overhead_seconds_per_task') or 0.,
                                                        extra.get('feature_overhead_seconds_per_task') or 0.)
        costs.setdefault('resource_gate', {})['passed'] = (costs.get('resource_gate', {}).get('passed', False)
                                                         and extra.get('resource_gate', {}).get('passed', False))
        for field in ('working_set_bytes', 'reserve_bytes', 'limit_bytes'):
            if field in extra.get('resource_gate', {}):
                costs['resource_gate'][field] = max(costs['resource_gate'].get(field, 0), extra['resource_gate'][field])
        for field in ('peak_mlx_bytes', 'sampled_parent_worker_rss_bytes', 'swap_used_bytes'):
            if field in extra:
                costs[field] = max(costs.get(field) or 0, extra[field] or 0)
    if extension_run_dirs:
        costs['closure'] = {'record_count': sum(source['closure']['record_count'] for source in source_closures),
                            'source_runs': source_closures, 'kind': 'aggregate_of_separately_closed_disjoint_pilot_runs'}
        costs['private_run_dirs'] = source_runs
        costs['all_k_scope'] = 'four pre-outcome hash tasks in each32-task reserved block; eight total diagnostic tasks'
    scores = {row['job_id']: row for row in scores_list}
    if len(scores) != len(scores_list) or set(scores) != {row.job_id for row in predictions}:
        raise ValueError('scoring does not exactly cover the closed assigned ledger')
    if any(scores[p.job_id]['task_id'] != p.task_id for p in predictions):
        raise ValueError('score task identity mismatch')
    # Regenerate explanatory component metadata from immutable closed receipts;
    # existing scalar serving/experiment costs and outcomes are unchanged.
    by_prediction = {p.job_id: p for p in predictions}
    for source_dir in source_runs:
        source_ids = {p.job_id for p in map(_prediction, read_jsonl(Path(source_dir)/'predictions.jsonl'))}
        for observation in costs['observations']:
            if observation['job_id'] in source_ids:
                observation['components'] = job_components(source_dir, by_prediction[observation['job_id']])
    obs = costs['observations']
    core = {(row['task_id'], row['k']): row for row in obs if row['kind'] == 'primary'}
    pairs = []
    for identity in schedule['assigned_ids']:
        small, full = core[identity, 2], core[identity, 10]
        s, f = scores[small['job_id']], scores[full['job_id']]
        pairs.append(PairedActionRow(identity, 'private question omitted', [], {}, small['job_id'], full['job_id'],
                                    s['joint_em'], f['joint_em'], s['answer_em'], f['answer_em'], [], [],
                                    small['serving_seconds'], full['serving_seconds'], small['status'], full['status']))
    report = headroom(pairs)
    metrics = {}
    for k in range(11):
        rows = [row for row in obs if row['k'] == k and row['kind'] in ('primary', 'all_k', 'no_context')]
        if not rows:
            continue
        scored = [scores[row['job_id']] for row in rows]
        metrics[str(k)] = {'assigned': len(rows), 'status_counts': dict(Counter(row['status'] for row in rows)),
                          'valid_citation_rate': sum(row['status'] == 'ok' for row in rows)/len(rows),
                          **{metric: sum(row[metric] for row in scored)/len(rows)
                             for metric in ('joint_em', 'answer_em', 'support_em', 'joint_f1', 'answer_f1', 'support_f1')},
                          'total_serving_seconds': sum(row['serving_seconds'] for row in rows),
                          'total_experiment_seconds': sum(row['experiment_seconds'] for row in rows),
                          'prompt_tokens': [row['prompt_tokens'] for row in rows],
                          'output_tokens': [row['output_tokens'] for row in rows]}
    primary = [dict(row, planned_jobs=planned_jobs) for row in obs if row['kind'] == 'primary']
    all_k_metrics = {}
    for k in range(1, 11):
        rows = [row for row in obs if row['k'] == k and row['task_id'] in schedule['all_k_ids']
                and row['kind'] in ('primary', 'all_k')]
        if rows:
            all_k_metrics[str(k)] = {'assigned': len(rows),
                                    **{metric: sum(scores[row['job_id']][metric] for row in rows)/len(rows)
                                       for metric in ('joint_em', 'answer_em', 'support_em', 'joint_f1', 'answer_f1', 'support_f1')},
                                    'valid_citation_rate': sum(row['status'] == 'ok' for row in rows)/len(rows),
                                    'total_serving_seconds': sum(row['serving_seconds'] for row in rows)}
    forecast = capacity_forecast(primary, max(0., remaining_seconds-setup_allowance_seconds))
    forecast['actual_remaining_seconds'] = remaining_seconds
    forecast['setup_training_diagnostics_allowance_seconds'] = setup_allowance_seconds
    forecast['known_stage_jobs'] = {'initial_fit_two_ten': 512, 'tune_all_k': 1280, 'tune_judge': 128}
    forecast['confirmation_envelopes'] = [{'tasks': n, 'arms': 2, 'repetitions': repetitions,
                                         'jobs': n*2*repetitions,
                                         'forecast_seconds': n*2*repetitions*forecast['conservative_seconds_per_job'],
                                         'fits_after_known_development': (n*2*repetitions+planned_jobs) <= forecast['maximum_affordable_jobs']}
                                        for n in (128, 256, 512, 1024) for repetitions in (1, 2, 3)]
    for envelope in forecast['confirmation_envelopes']:
        envelope['scope'] = 'two direct arms only; excludes anchor, representative action/judge jobs and their setup'
        envelope['primary_repetition_eligible'] = envelope['repetitions'] >= 2
    forecast['protected_sample_frozen'] = False
    forecast['scope'] = 'known initial development path; confirmation envelopes are planning only, Task13 selects n and repetitions'
    target = report['fixed_ten']['successes']
    matching = next((point for point in report['oracle_frontier'] if point['successes'] >= target), None)
    savings = report['fixed_ten']['total_seconds']-matching['total_seconds'] if matching else 0.
    overhead = costs.get('feature_overhead_seconds_per_task')
    overhead_comparison = [{'seconds_per_task': value, 'oracle_savings_after_overhead_seconds': savings-value*len(pairs),
                            'kind': kind} for value, kind in
                           [(overhead or 0., 'measured_feature_construction_only'), (.001, 'plausible_prediction_envelope_1ms'),
                            (.01, 'plausible_prediction_envelope_10ms')]]
    # Suitability is a descriptive development gate, never a significance test.
    # Fewer than four oracle successes or two discordant tasks is unstable at 32;
    # the declared reservation must be extended before an insensitive-reader stop.
    unstable = report['oracle_quality']*len(pairs) < 4 or report['discordance'] < 2
    resources = costs.get('resource_gate', {}).get('passed', False)
    deterministic = costs['determinism']['passed']
    if unstable and len(pairs) < 64:
        gate = {'status': 'needs_reserved_extension', 'reason': 'small-pilot success/discordance instability',
                'next_stage': 'extend_reserved_pilot_to_64', 'task10_allowed': False}
    elif unstable:
        gate = {'status': 'stop', 'reason': 'reader/strict-joint metric uninformative on declared 64 pilot tasks',
                'next_stage': 'task16_report', 'task10_allowed': False}
    elif not resources or not forecast['feasible'] or not deterministic:
        gate = {'status': 'stop', 'reason': 'runtime/resource/determinism prerequisites not met',
                'next_stage': 'task16_report', 'task10_allowed': False}
    elif target == 0 or savings <= .01*len(pairs):
        gate = {'status': 'stop', 'reason': 'no useful oracle resource headroom at fixed-ten quality',
                'next_stage': 'task16_report', 'task10_allowed': False}
    else:
        gate = {'status': 'continue', 'reason': 'joint reader sensitivity, oracle allocation headroom and resource forecast informative',
                'next_stage': 'task10_index_collect_fit', 'task10_allowed': True}
    gate['development_stability_rule'] = {'min_oracle_successes': 4, 'min_discordant_tasks': 2,
                                           'extension_limit': 64, 'min_savings_envelope_seconds_per_task': .01}
    gate['scope'] = 'development feasibility only; no learned policy or protected claim'
    output.mkdir(parents=True, exist_ok=True)
    with (output/'headroom.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, lineterminator='\n', fieldnames=['task_id', 'small_joint_em', 'full_joint_em', 'small_answer_em', 'full_answer_em',
                                                  'small_cost_seconds', 'full_cost_seconds', 'small_status', 'full_status'])
        writer.writeheader()
        for row in pairs:
            writer.writerow({key: getattr(row, key) for key in writer.fieldnames})
    failure_path = output/'reader_failures.jsonl'
    if failure_path.exists():
        raise ValueError('analysis output already exists')
    failure_path.touch()
    for row in obs:
        score = scores[row['job_id']]
        if row['status'] != 'ok' or not score['joint_em']:
            append_jsonl(failure_path, {'task_id': row['task_id'], 'job_id': row['job_id'], 'k': row['k'],
                         'kind': row['kind'], 'status': row['status'], **{m: score[m] for m in
                          ('answer_em', 'support_em', 'joint_em', 'answer_f1', 'support_f1', 'joint_f1')}})
    summary = {'headroom': report, 'metrics': metrics, 'all_k_slice_metrics': all_k_metrics,
               'gate': gate, 'capacity_forecast': forecast,
               'oracle_overhead_comparison': overhead_comparison, 'oracle_savings_at_fixed_ten_quality_seconds': savings,
               'closed_ledger': costs['closure'], 'score_hash': content_hash(scores_list), 'private_run_dir': str(root),
               'private_run_dirs': source_runs,
               'interpretation': 'inconclusive', 'protected_generation': False}
    atomic_json(output/'pilot_costs.json', costs)
    atomic_json(output/'capacity_forecast.json', forecast)
    atomic_json(output/'wp3-gate.json', summary)
    return summary


def two_endpoint_frontier(rows: list[PairedActionRow], *, minimum_strict_successes: int,
                          minimum_answer_successes: int) -> dict:
    """NEW exact empirical T/S/E frontier with both supplied anchor constraints.

    This privileged optimistic diagnostic assumes zero routing overhead. It is
    neither a policy nor a population bound. The existing strict-only frontier
    retains its historical meaning. Unknown service requirements stay unknown.
    """
    import math
    _validate(rows)
    n=len(rows)
    for floor in (minimum_strict_successes,minimum_answer_successes):
        if type(floor) is not int or not 0<=floor<=n:
            raise ValueError('explicit empirical endpoint anchor counts required')
    for r in rows:
        if (r.small_joint_em>r.small_answer_em or r.full_joint_em>r.full_answer_em or
                any(not math.isfinite(t) or t<0 for t in (r.small_cost_seconds,r.full_cost_seconds))):
            raise ValueError('incoherent strict/answer outcomes or action costs')
    # At each exact (S,E) total, retain the minimum cost and a reconstructible
    # witness. Outcomes, not features, create these choices: never serve them.
    layers=[{(0,0):(0.,None,None)}]
    for r in rows:
        layer={}
        actions=((2,r.small_joint_em,r.small_answer_em,r.small_cost_seconds),
                 (10,r.full_joint_em,r.full_answer_em,r.full_cost_seconds))
        for previous,(cost,_,_) in layers[-1].items():
            for action,s,e,t in actions:
                state=(previous[0]+s,previous[1]+e);proposed=cost+t
                if state not in layer or proposed<layer[state][0]:layer[state]=(proposed,previous,action)
        layers.append(layer)
    # Descending S then E: a prefix-min tree over descending E detects every
    # previously visited point at least as correct on both endpoints.
    tree=[math.inf]*(n+2)
    states=[]
    for state in sorted(layers[-1],reverse=True):
        s,e=state;cost=layers[-1][state][0];index=n-e+1;cursor=index;best=math.inf
        while cursor:
            best=min(best,tree[cursor]);cursor-=cursor&-cursor
        if best>cost:states.append(state)
        while index<len(tree):
            tree[index]=min(tree[index],cost);index+=index&-index
    frontier=[]
    for s,e in sorted(states,key=lambda x:(layers[-1][x][0],x)):
        cost=layers[-1][s,e][0];state=(s,e);choices=[]
        for layer in reversed(layers[1:]):
            _,state,action=layer[state];choices.append(action)
        choices.reverse()
        frontier.append({'n':n,'S':s,'E':e,'Q':s/n,'answer_rate':e/n,'total_T':cost,
                         'R':cost/s if s else None,'choices':choices,
                         'two_actions':choices.count(2),'ten_actions':choices.count(10)})
    feasible=[p for p in frontier if p['S']>=minimum_strict_successes and p['E']>=minimum_answer_successes and p['S']>0]
    best=min(feasible,key=lambda p:(p['R'],p['total_T'],-p['S'],-p['E'])) if feasible else None
    return {'n':n,'frontier':frontier,'minimum_R':best,
            'reason':None if best else 'no_nonzero_strict_feasible_schedule',
            'minimum_strict_successes':minimum_strict_successes,'minimum_answer_successes':minimum_answer_successes,
            'service_quality_floor':None,'routing_overhead_seconds':0.,'allocation_claim':False,
            'scope':'clairvoyant empirical diagnostic with supplied anchor counts; no deployment, population guarantee or service-floor claim'}

"""Privileged, fit-only selection followed by one held-out development analysis.

This module is offline research code. It neither acquires actions nor belongs in
serving. Paired outcomes and proxy Gold are privileged inputs. The original
train.learning_curve remains a resubstitution diagnostic.
"""
from collections import Counter
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
import time
import unicodedata

import numpy as np

from .features import feature_schema
from .policies import FixedPolicy, ThresholdPolicy
from .schemas import validate_record
from .select import select_configuration
from .storage import append_jsonl, atomic_json, content_hash
from .train import feature_matrix, fit_gates, load_gate, outcome_targets, proxy_targets

QUANTILE_LEVELS = tuple(i / 20 for i in range(21))
RULES = ('always_ten', *QUANTILE_LEVELS, 'always_two')
PLANNING_SECONDS = .02
CONTROL_FAMILIES = ('PRE-LINEAR', 'PRE-RF', 'QUERY-ONLY', 'PROXY-LABEL',
                    'SHUFFLED-LABEL-GBM', 'RANDOM-MIXTURE')


def _normalized(question):
    return ' '.join(unicodedata.normalize('NFC', question).casefold().split())


def _group(row):
    return content_hash(_normalized(row.question))


def _threshold_rule(rule, training_predictions):
    if rule in ('always_two', 'always_ten'):
        return {'threshold_mode': rule, 'threshold': None}
    if rule not in QUANTILE_LEVELS:
        raise ValueError('unregistered quantile level')
    values = np.asarray(training_predictions, dtype=np.float64)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all():
        raise ValueError('finite training predictions required')
    return {'threshold_mode': 'numeric', 'threshold': float(np.quantile(values, rule, method='linear'))}


def _random_action(question, probability, seed):
    if not 0 <= probability <= 1:
        raise ValueError('invalid fit-calibrated rate')
    if probability in (0., 1.):
        return 10 if probability else 2
    digest = hashlib.sha256(f'{seed}\n{_normalized(question)}'.encode()).digest()
    return 10 if int.from_bytes(digest, 'big') / 2**256 < probability else 2


def _inner_seconds(row, action, mode):
    observed = row.small_cost_seconds if action == 2 else row.full_cost_seconds
    return observed + (PLANNING_SECONDS if mode == 'numeric' else 0.)


def _family(model_name):
    return 'PRE-LINEAR' if model_name.startswith('PRE-LINEAR-') else model_name


def _config_id(model_name, rule):
    return model_name + ':' + (rule if isinstance(rule, str) else f'q{round(rule * 100):03d}')


def _summarize(rows, actions, seconds):
    selected = [('small' if a == 2 else 'full') for a in actions]
    S = sum(getattr(row, arm + '_joint_em') for row, arm in zip(rows, selected))
    E = sum(getattr(row, arm + '_answer_em') for row, arm in zip(rows, selected))
    n = len(rows)
    total = math.fsum(seconds)
    return {'n': n, 'S': S, 'E': E, 'Q': S / n, 'answer_em': E / n,
            'total_T': total, 'mean_T': total / n, 'R': total / S if S else None,
            'reason': None if S else 'zero_successes',
            'statuses': dict(Counter(getattr(row, arm + '_status') for row, arm in zip(rows, selected))),
            'escalations': sum(a == 10 for a in actions), 'escalation_rate': sum(a == 10 for a in actions) / n,
            'strict_rescue_opportunities': sum(r.full_joint_em > r.small_joint_em for r in rows),
            'strict_rescues_selected': sum(a == 10 and r.full_joint_em > r.small_joint_em for r,a in zip(rows,actions)),
            'strict_harm_opportunities': sum(r.full_joint_em < r.small_joint_em for r in rows),
            'strict_harms_selected': sum(a == 10 and r.full_joint_em < r.small_joint_em for r,a in zip(rows,actions)),
            'answer_rescue_opportunities': sum(r.full_answer_em > r.small_answer_em for r in rows),
            'answer_rescues_selected': sum(a == 10 and r.full_answer_em > r.small_answer_em for r,a in zip(rows,actions)),
            'answer_harm_opportunities': sum(r.full_answer_em < r.small_answer_em for r in rows),
            'answer_harms_selected': sum(a == 10 and r.full_answer_em < r.small_answer_em for r,a in zip(rows,actions))}


def _selection_metrics(rows, definition, actions):
    mode = 'numeric' if isinstance(definition.get('quantile_level'), (int, float)) else definition.get('threshold_mode')
    summary = _summarize(rows, actions, [_inner_seconds(r, a, mode) for r, a in zip(rows, actions)])
    return {**definition, **summary, 'split': 'tune', 'task_ids': [r.task_id for r in rows],
            'mean_time': summary['mean_T'], 'joint_successes': summary['S'], 'answer_successes': summary['E'],
            'assigned_tasks': len(rows), 'total_serving_seconds': summary['total_T']}


def _folds(rows, seed):
    groups = list(dict.fromkeys(_group(r) for r in rows))
    if len(groups) < 4:
        raise ValueError('four distinct duplicate groups required for inner folds')
    order = np.random.Generator(np.random.PCG64(seed)).permutation(len(groups))
    allocation = {groups[int(index)]: position % 4 for position, index in enumerate(order)}
    return [([r for r in rows if allocation[_group(r)] != fold],
             [r for r in rows if allocation[_group(r)] == fold]) for fold in range(4)]


def _choose_prediction(model, model_name, row):
    # One actual policy call per model/validation subject supplies the common
    # clipped predictions. All 21 quantile rules reuse those predictions.
    policy = ThresholdPolicy(model, {'policy_id': model_name, 'threshold_mode': 'numeric',
                                    'threshold': 0., 'feature_schema_hash': feature_schema()['hash']})
    decision = policy.choose(row.question, row.ranked_documents)
    if decision.reason == 'full_fallback' or decision.predicted_delta is None:
        raise ValueError('inner policy failed; silently replacing its model is forbidden')
    return decision.predicted_delta


def _fit_curve(rows, gold, root, seed):
    ids = [r.task_id for r in rows]
    assignments, origins, predictions, thresholds = [], [], {}, {}
    for fold, (training, validation) in enumerate(_folds(rows, seed)):
        assignments.append({'fold': fold, 'train_ids': [r.task_id for r in training],
            'validation_ids': [r.task_id for r in validation],
            'train_group_hashes': sorted({_group(r) for r in training}),
            'validation_group_hashes': sorted({_group(r) for r in validation})})
        origin = fit_gates(training, {r.task_id: gold[r.task_id] for r in training}, root/f'inner-{fold}')
        origins.append(origin)
        for model_name, manifest in origin['models'].items():
            model = load_gate(manifest)
            for row in validation:
                predictions.setdefault(model_name, {})[row.task_id] = _choose_prediction(model, model_name, row)
            for rule in RULES:
                identity = _config_id(model_name, rule)
                thresholds.setdefault(identity, []).append(_threshold_rule(rule, manifest['training_predictions']))
    config_rows, action_map = [], {}
    for model_name in origins[0]['models']:
        for rule in RULES:
            identity = _config_id(model_name, rule)
            actions_by_id = {}
            for fold, assignment in enumerate(assignments):
                config = thresholds[identity][fold]
                for task_id in assignment['validation_ids']:
                    prediction = predictions[model_name][task_id]
                    actions_by_id[task_id] = (2 if config['threshold_mode'] == 'always_two' else 10
                        if config['threshold_mode'] == 'always_ten' else 2 if prediction <= config['threshold'] else 10)
            definition = {'config_id': identity, 'family': _family(model_name), 'model_name': model_name,
                          'threshold_mode': rule if isinstance(rule, str) else 'numeric',
                          'quantile_level': None if isinstance(rule, str) else rule}
            actions = [actions_by_id[i] for i in ids]
            config_rows.append(_selection_metrics(rows, definition, actions))
            action_map[identity] = actions
    for k in (2, 10):
        definition = {'config_id': f'FIXED-{k}', 'family': 'FIXED', 'model_name': None,
                      'threshold_mode': f'always_{"two" if k == 2 else "ten"}', 'quantile_level': None}
        config_rows.append(_selection_metrics(rows, definition, [k] * len(rows)))
        action_map[definition['config_id']] = [k] * len(rows)
    anchor = next(r for r in config_rows if r['config_id'] == 'FIXED-10')
    selection = select_configuration(config_rows, anchor)
    selected_A = selection['A*']
    probability = sum(a == 10 for a in action_map[selected_A['config_id']]) / len(rows)
    random_definition = {'config_id': 'RANDOM-MIXTURE', 'family': 'RANDOM-MIXTURE', 'model_name': None,
                         'threshold_mode': 'numeric' if 0 < probability < 1 else 'always_ten' if probability else 'always_two',
                         'quantile_level': None, 'fit_escalation_probability': probability,
                         'eligible': None, 'selection_pool': False, 'eligibility': 'diagnostic_only'}
    random_actions = [_random_action(r.question, probability, seed) for r in rows]
    random_row = _selection_metrics(rows, random_definition, random_actions)
    random_row['eligible'] = random_row['Q'] >= anchor['Q'] and random_row['answer_em'] >= anchor['answer_em']
    selection['rate_matched_random'] = random_row
    full = fit_gates(rows, {r.task_id: gold[r.task_id] for r in rows}, root/'refit')
    # No holdout inputs have been supplied anywhere in this function.
    representatives = {family: value['representative'] for family,value in selection['families'].items() if family != 'FIXED'}
    representatives.update({'FIXED-2': next(r for r in selection['configurations'] if r['config_id'] == 'FIXED-2'),
                            'FIXED-10': next(r for r in selection['configurations'] if r['config_id'] == 'FIXED-10'),
                            'RANDOM-MIXTURE': random_row})
    refitted = {}
    for family, selected in representatives.items():
        model_name = selected['model_name']
        rule = selected['threshold_mode'] if selected['quantile_level'] is None else selected['quantile_level']
        refitted[family] = {k: selected[k] for k in ('config_id', 'family', 'model_name', 'quantile_level', 'threshold_mode')}
        if model_name:
            manifest = full['models'][model_name]
            refitted[family].update(_threshold_rule(rule, manifest['training_predictions']))
            refitted[family]['artifact_sha256'] = manifest['artifact_sha256']
        else:
            refitted[family]['threshold'] = None
        if family == 'RANDOM-MIXTURE':
            refitted[family]['fit_escalation_probability'] = probability
        refitted[family]['inner_point_quality_eligible'] = selected['Q'] >= anchor['Q'] and selected['answer_em'] >= anchor['answer_em']
        refitted[family]['B_selection_pool'] = selected.get('selection_pool', False) and family != 'PRE-OUTCOME-GBM'
    atomic_json(root/'inner-selection.json', selection)
    atomic_json(root/'inner-oof-predictions.json', {'task_ids': ids, 'model_predictions': predictions,
                'configuration_actions': action_map, 'fold_thresholds': thresholds})
    lock = {'fit_size': len(rows), 'fit_ids': ids, 'folds': assignments,
            'selected_A': {k: selected_A[k] for k in ('config_id','family','model_name','quantile_level','threshold_mode')},
            'selected_B': {k: selection['B*'][k] for k in ('config_id','family','model_name','quantile_level','threshold_mode')},
            'refitted_rules': refitted, 'fit_rows_hash': full['rows_hash'],
            'model_artifact_hashes': {name: manifest['artifact_sha256'] for name,manifest in full['models'].items()},
            'inner_model_artifact_hashes': [{name:m['artifact_sha256'] for name,m in o['models'].items()} for o in origins],
            'fit_random_probability': probability,
            'fit_random_calibration':'selected_A_common_fit_OOF_escalation_rate', 'random_seed': seed}
    return lock, selection, full


def _heldout_methods(rows, lock, full, private_output):
    methods = {}
    for name, rule in lock['refitted_rules'].items():
        if name.startswith('FIXED-'):
            policy = FixedPolicy(int(name.split('-')[1]))
        elif name == 'RANDOM-MIXTURE':
            policy = None
        else:
            model = load_gate(full['models'][rule['model_name']]) if rule['threshold_mode'] == 'numeric' else None
            policy = ThresholdPolicy(model, {**rule, 'policy_id':rule['model_name'],
                                            'feature_schema_hash':feature_schema()['hash']})
        actions, seconds, overheads = [], [], []
        for row in rows:
            started = time.perf_counter_ns()
            if policy is None:
                action = _random_action(row.question, rule['fit_escalation_probability'], lock['random_seed'])
            else:
                chosen = policy.choose(row.question, row.ranked_documents)
                action = chosen.action_k
            elapsed = (time.perf_counter_ns() - started) / 1e9
            decision = (asdict(chosen) if policy is not None else
                        {'reason':'fit_calibrated_question_hash', 'predicted_delta':None})
            if action not in (2, 10):
                raise ValueError('heldout action is not a registered endpoint')
            arm = 'small' if action == 2 else 'full'
            observed = getattr(row, arm + '_cost_seconds')
            actions.append(action); seconds.append(observed + elapsed); overheads.append(elapsed)
            append_jsonl(private_output, {'fit_size':lock['fit_size'], 'method':name, 'config_id':rule['config_id'],
                'task_id':row.task_id, 'action_k':action, 'decision':decision,
                'status':getattr(row,arm+'_status'), 'strict_success':getattr(row,arm+'_joint_em'),
                'answer_success':getattr(row,arm+'_answer_em'),
                'source_prediction_id':getattr(row,arm+'_prediction_id'), 'source_event_ids':getattr(row,arm+'_event_ids'),
                'observed_action_seconds':observed, 'policy_choose_seconds':elapsed,
                'reconstructed_seconds':observed + elapsed})
        summary = _summarize(rows, actions, seconds)
        methods[name] = {**summary, 'config_id':rule['config_id'], 'family':rule['family'],
            'threshold_mode':rule['threshold_mode'], 'quantile_level':rule['quantile_level'],
            'inner_point_quality_eligible':rule['inner_point_quality_eligible'],
            'B_selection_pool':rule['B_selection_pool'],
            'mean_policy_choose_seconds':math.fsum(overheads)/len(rows),
            'cost_kind':'reconstructed_observed_complete_action_plus_measured_individual_choose',
            'retains_original_fixed_routing_overhead':True}
    return methods


def _screen(curve):
    methods = curve['methods']
    A, B, fixed = methods['PRE-OUTCOME-GBM'], methods[curve['selected_B_method']], methods['FIXED-10']
    S, E = max(B['S'],fixed['S']), max(B['E'],fixed['E'])
    comparisons = {}
    for name, other in (('FIXED-10',fixed), ('fit_selected_B',B)):
        valid = A['R'] is not None and other['R'] is not None and other['R'] > 0
        r_saving = 1 - A['R'] / other['R'] if valid else None
        t_saving = other['mean_T'] - A['mean_T']
        comparisons[name] = {'no_point_S_E_deficit':A['S'] >= other['S'] and A['E'] >= other['E'],
            'R_fraction_saving':r_saving, 'mean_T_saving_seconds':t_saving,
            'target_met': bool(valid and r_saving >= .20 and t_saving >= .25 and
                               A['S'] >= other['S'] and A['E'] >= other['E'])}
    matches = [name for name in CONTROL_FAMILIES if methods[name]['R'] is not None and A['R'] is not None
               and methods[name]['S'] >= S and methods[name]['E'] >= E and methods[name]['R'] <= 1.05 * A['R']]
    target = all(c['target_met'] for c in comparisons.values())
    candidates = [name for name in matches if methods[name]['B_selection_pool'] and methods[name]['inner_point_quality_eligible']]
    # Report possible future candidates, without using holdout to select a new B.
    return {'primary_fit_size':curve['fit_size'], 'selected_B_method':curve['selected_B_method'],
        'comparisons':comparisons, 'same_point_quality_anchors':{'S':S,'E':E},
        'matching_controls_within_5_percent_R':matches,
        'matching_controls_from_original_fit_eligible_pool':candidates,
        'outcome_GBM_specific_advantage_rejected':bool(matches),
        'research_target_met_against_both':target,
        'continue_to_common_tuning':target and not matches,
        'retain_admitted_research_anchor':'FIXED-10',
        'reason':'separately registered common tuning permitted' if target and not matches else
                 'stop allocation-label expansion under this hypothesis; no learning-holdout tuning',
        'thirty_successes_is_only_later_inference_implementation_minimum':True,
        'final_efficiency_claim':False, 'population_claim':False, 'operational_claim':False}


def evaluate(rows, training_gold, fit_ids, holdout_ids, output_dir, *, fit_sizes=(128,256,512), seed=20261018):
    """Freeze fit-only models/rules/B, then score every fixed prefix on one holdout.

    IDs are ordered, preassigned memberships; no split is selected from outcomes.
    output_dir must be fresh and private. Only public-summary.json is suitable
    for publication; all other artifacts contain restricted IDs or decisions.
    """
    rows, fit_ids, holdout_ids, fit_sizes = list(rows), list(fit_ids), list(holdout_ids), tuple(fit_sizes)
    by_id = {r.task_id:r for r in rows}
    if (not fit_ids or not holdout_ids or len(by_id) != len(rows) or len(set(fit_ids)) != len(fit_ids)
            or len(set(holdout_ids)) != len(holdout_ids) or set(fit_ids) & set(holdout_ids)
            or set(by_id) != set(fit_ids) | set(holdout_ids)):
        raise ValueError('exact unique disjoint fit/holdout assignment required')
    if (not fit_sizes or any(type(n) is not int or n < 4 for n in fit_sizes)
            or tuple(sorted(set(fit_sizes))) != fit_sizes or fit_sizes[-1] != len(fit_ids)):
        raise ValueError('fixed increasing fit prefixes ending at the complete fit assignment required')
    fitted, heldout = [by_id[i] for i in fit_ids], [by_id[i] for i in holdout_ids]
    if {_group(r) for r in fitted} & {_group(r) for r in heldout}:
        raise ValueError('duplicate group crosses fit and holdout')
    if any(not _normalized(r.question) for r in rows):
        raise ValueError('nonempty normalized question required')
    feature_matrix(rows)
    outcome_targets(rows)
    proxy_targets(fitted, training_gold)
    for row in rows:
        validate_record(row)
        for arm in ('small','full'):
            if getattr(row,arm+'_joint_em') > getattr(row,arm+'_answer_em'):
                raise ValueError('strict success requires answer success')
    for n in fit_sizes:
        _folds(fitted[:n], seed)  # Validate every prefix before creating output.
    root = Path(output_dir).resolve()
    if root.exists():
        raise ValueError('fresh private heldout output required; no automatic overwrite')
    root.mkdir(parents=True, mode=0o700, exist_ok=False)
    private = root/'private'; private.mkdir(mode=0o700, exist_ok=False)
    membership = {'fit_ids':fit_ids, 'holdout_ids':holdout_ids,
                  'fit_group_hashes':sorted({_group(r) for r in fitted}),
                  'holdout_group_hashes':sorted({_group(r) for r in heldout}), 'curves':[]}
    locks, selections, models = [], [], []
    for n in fit_sizes:
        prefix = fitted[:n]
        lock, selection, full = _fit_curve(prefix, {r.task_id:training_gold[r.task_id] for r in prefix}, private/f'fit-{n}', seed)
        locks.append(lock); selections.append(selection); models.append(full)
        membership['curves'].append({k:lock[k] for k in ('fit_size','fit_ids','folds')})
    state = {'evaluation':'fit_only_four_fold_selection', 'seed':seed, 'quantile_levels':list(QUANTILE_LEVELS),
             'inner_planning_seconds':PLANNING_SECONDS, 'feature_schema_hash':feature_schema()['hash'], 'curves':locks}
    atomic_json(private/'memberships.json', membership)
    atomic_json(private/'fit-only-state.json', state)
    # All fitting, preprocessing, threshold rules and the largest-fit B are now
    # persisted. Holdout outcomes enter only the following reporting phase.
    curves = []
    for lock, selection, full in zip(locks,selections,models):
        methods = _heldout_methods(heldout, lock, full, private/'heldout-decisions.jsonl')
        B = selection['B*']
        b_method = B['config_id'] if B['family'] == 'FIXED' else B['family']
        curves.append({'fit_size':lock['fit_size'], 'holdout_n':len(heldout), 'methods':methods,
                       'selected_A_method':'PRE-OUTCOME-GBM', 'selected_B_method':b_method,
                       'selection_source':'common fit-only group-disjoint four-fold OOF',
                       'fit_random_probability':lock['fit_random_probability'],
                       'fit_random_calibration':lock['fit_random_calibration'],
                       'inner_candidate_eligible':selection['A*']['eligible'],
                       'inner_B_eligible':B['eligible']})
    summary = {'evaluation':'heldout_development_research', 'fit_sizes':list(fit_sizes), 'holdout_n':len(heldout),
               'same_holdout_across_curves':True, 'independent_replications':False,
               'inner_split_label_tune_is_analysis_only':True, 'original_task_split_unchanged':True,
               'curves':curves, 'screen':_screen(curves[-1]),
               'selection_eligibility':{'competitive_B':'original select_configuration comparator roster',
                   'SHUFFLED-LABEL-GBM':'diagnostic_only_outside_B_pool', 'RANDOM-MIXTURE':'diagnostic_only_outside_B_pool'},
               'omitted_comparisons':['ADAPTIVE-k-published','ADAPTIVE-k-tuned','POST-OUTCOME','LLM-SUFFICIENCY',
                                      'intermediate_budgets','NO-CONTEXT-DIAGNOSTIC','ALWAYS-ABSTAIN'],
               'limits':['bounded learning futility research', 'one observed timing per action',
                         'reconstructed policy cost requires direct final measurement',
                         'success requires a separate common tuning and powered final protocol',
                         'no all-method superiority or operational efficiency claim']}
    atomic_json(root/'public-summary.json', summary)
    return summary

"""Read-only aggregate verification; publish hashes and numbers, never task text.

This does not rescore Gold or authorize execution. Run the frozen scorer in a
fresh process first. All setup roots, including software-only attempts, are
required so their observed costs cannot disappear from the report.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    raw = Path(path).read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def interval_seconds(values):
    intervals = sorted((v['start_ns'], v['stop_ns']) for v in values)
    if any(a > b for a,b in intervals) or any(b > c for (_,b),(c,_) in zip(intervals, intervals[1:])):
        raise ValueError('invalid/overlapping envelopes; do not add nested costs')
    return sum((b-a)/1e9 for a,b in intervals)


def quantile(values, p):
    values = sorted(values)
    position = (len(values)-1)*p
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (values[high]-values[low])*(position-low)


def build(roots, audit, worktree):
    root = roots[-1]
    summary, schedule = read(root/'scores/summary.json'), read(root/'schedule.json')
    scored = rows(root/'scores/scores.jsonl')
    if len(scored) != 160 or len({s['job_id'] for s in scored}) != len(scored):
        raise ValueError('entire 160-job diagnosis required')
    if {s['job_id'] for s in scored} != {j['job_id'] for j in schedule}:
        raise ValueError('assigned/scored inventory mismatch')
    if len({s['task_id'] for s in scored}) != 32:
        raise ValueError('questions, not repeated arms, are the sample unit')
    details = {}
    for arm, published in summary['arms'].items():
        values = [s for s in scored if s['arm']==arm]
        successes = sum(s['joint_em'] for s in values)
        total = sum(s['seconds'] for s in values)
        if (len(values)!=32 or successes!=published['strict_successes'] or
                sum(s['answer_em'] for s in values)!=published['answer_successes'] or
                not math.isclose(total,published['total_T'],rel_tol=1e-12)):
            raise ValueError('independent aggregate verification failed')
        expected_R = total/successes if successes else None
        if expected_R != published['R'] or published['Q'] != successes/len(values):
            raise ValueError('ratio/denominator mismatch')
        details[arm] = {**published,
            'answer_f1': sum(s['answer_f1'] for s in values)/32,
            'support_em_count': sum(s['support_em'] for s in values),
            **{k:sum(s[k] for s in values)/32 for k in ('support_f1','support_precision','support_recall')},
            'p95_seconds': quantile([s['seconds'] for s in values],.95),
            'p99_seconds': quantile([s['seconds'] for s in values],.99),
            'max_seconds': max(s['seconds'] for s in values),
            'prompt_tokens': sum(s['prompt_tokens'] for s in values),
            'output_tokens': sum(s['generated_tokens'] for s in values),
            'correct_answer_without_strict_success': sum(bool(s['answer_em'] and not s['joint_em']) for s in values)}
    inventory, setup_intervals = [], []
    cohorts = read(root/'cohorts.json')
    for index, setup in enumerate(roots):
        if read(setup/'cohorts.json') != cohorts:
            raise ValueError('setup handoff changed reservations')
        if setup!=root and (setup/'jobs').exists():
            raise ValueError('software-only attempt contains assigned jobs')
        attempt = read(setup/'plan.json')
        setup_intervals.extend(rows(setup/'setup-attempts.jsonl'))
        names = ['plan.json','cohorts.json','selection-frozen.json','config.json','source.diff',
                 'setup-attempts.jsonl','index-setup/index-seal.json','index-setup/index-attempts.jsonl',
                 'index-setup/index/manifest.json']
        inventory.append({'setup_ordinal':index+1,'private_root':str(setup),'plan_hash':attempt['plan_hash'],
            'assigned_jobs':160 if setup==root else 0,
            'files':{n:identity(setup/n) for n in names}})
    launch, scoring = rows(root/'launches.jsonl'), rows(root/'scoring-attempts.jsonl')
    preflight = read(audit/'native-preflight.json')
    all_envelopes = setup_intervals + launch + scoring + preflight
    costs = {'four_index_setup_envelopes_seconds':interval_seconds(setup_intervals),
        'native_launcher_envelopes_seconds':interval_seconds(launch),
        'scoring_envelopes_seconds':interval_seconds(scoring),
        'preflight_envelopes_seconds':interval_seconds(preflight),
        'observed_disjoint_envelopes_seconds':interval_seconds(all_envelopes),
        'nested_resident_seconds':summary['costs']['resident_session_seconds'],
        'nested_service_seconds':sum(s['seconds'] for s in scored),
        'preparation_engineering_tests_historical_and_total_project_seconds':None,
        'cost_scope':'Observed setup/launcher/scoring/preflight only; nested service/resident/warmup not added again. Preparation and engineering remain unknown.',
        'incremental_adaptation_seconds':None,'break_even_queries':None,
        'break_even_reason':'No learned-policy saving or complete attributable adaptation cost'}
    for n in ('launches.jsonl','scoring-attempts.jsonl','schedule.json','scores/scores.jsonl','scores/summary.json','scores/closed.json',
              'blind-review-packet.json','blind-review-key.json','blind-review-results.json','human-adjudication-packet.json'):
        inventory[-1]['files'][n] = identity(root/n)
    resources = {}
    for group in ('natural','oracle'):
        stage = root/'stages'/group
        measured, gates = rows(stage/'resources.jsonl'), rows(stage/'memory-gates.jsonl')
        warmup = read(stage/'warmup/result.json')['result']
        if warmup['status']!='ok' or warmup['answer']!='violet light' or warmup['citations']!=[['D0',0]]:
            raise ValueError('authored native warmup did not answer/cite correctly')
        resources[group] = {'samples':len(measured),'all_request_memory_gates_pass':all(g['passed'] for g in gates),
            'maximum_conservative_working_set_bytes':max(g['working_set_bytes'] for g in gates),
            'reserve_bytes':gates[0]['reserve_bytes'],'limit_bytes':gates[0]['limit_bytes'],
            'system_swap_used_range_bytes':[min(s['swap_used_bytes'] for s in measured),max(s['swap_used_bytes'] for s in measured)],
            'authored_warmup_correct':True,'denials':read(stage/'denials.json')}
        inventory[-1]['files']['stages/'+group+'/closed.json'] = identity(stage/'closed.json')
    key = read(root/'blind-review-key.json')
    review = read(root/'blind-review-results.json')
    by_case = {c['case_id']:c for c in review['cases']}
    flagged = [k for k in key['key'] if k['strict_success'] and by_case[k['case_id']]['citations_sufficient']=='no']
    qualitative = {'sampling':key['manifest'],'reviewer':'auxiliary Codex agent; not independent human certification',
        'categories':review['aggregate_categorical_counts'],
        'strict_success_outputs_flagged_insufficient':len(flagged),
        'unique_questions_among_these_flags':len({k['task_id'] for k in flagged}),
        'semantic_validity':'unresolved; no Gold repair or replacement endpoint',
        'scope':'Enriched qualitative observations only, no population rate or admission decision'}
    result = {'protocol_id':'reader-recovery-v1','assigned_questions':32,'assigned_calls':160,
        'arms':details,'statuses':dict(Counter(s['status'] for s in scored)),
        'paired_diagnostics':summary['paired_diagnostics'],'clairvoyant_headroom':summary['clairvoyant_headroom'],
        'costs':costs,'resources':resources,'qualitative_review':qualitative,
        'claims':summary['claims'],'operational_requirements':None,
        'source_role':'new observation; no revised reader or learned router evaluated'}
    audit_names = sorted(p.name for p in audit.iterdir() if p.is_file())
    source = {str(p.relative_to(worktree)):identity(p) for p in sorted((worktree/'src/outcome_poc').rglob('*.py'))}
    test_sources = {str(p.relative_to(worktree)):identity(p) for p in sorted((worktree/'tests').rglob('*.py'))}
    dirty_diff = subprocess.check_output(['git','diff','--binary'],cwd=worktree)
    frozen_source = {str(p.relative_to(root/'source')):identity(p) for p in sorted((root/'source').rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    plan = read(root/'plan.json')
    manifest = {'generated_utc':datetime.now(timezone.utc).isoformat(),'publication_scope':'Hashes/aggregates only; raw text, Gold, reserved IDs, predictions and assets remain private',
        'base_commit':plan['source_commit'],'measured_plan_hash':plan['plan_hash'],
        'measured_source_snapshot_hash':summary['source_snapshot_hash'],'measured_source_files':frozen_source,
        'current_source_files':source,'current_source_note':'Includes post-run pre-Gold index guard; measured snapshot remains immutable and was explicitly admitted with verify_index before scoring.',
        'current_test_sources':test_sources,
        'current_tracked_dirty_diff_identity':{'sha256':hashlib.sha256(dirty_diff).hexdigest(),'bytes':len(dirty_diff)},
        'untracked_source_binding':'Current/measured source inventories include untracked package files; git diff alone is not their identity.',
        'aggregate_script_identity':identity(Path(__file__)),
        'config_identity':identity(root/'config.json'),'cohorts_identity':identity(root/'cohorts.json'),
        'eligible_population':cohorts['eligibility_count'],'eligible_ids_hash':cohorts['eligible_ids_hash'],
        'reservation_counts':{'historical':cohorts['historical_reservation_counts'],'diagnosis':32,'validation_untouched':64,'evaluation_untouched':128},
        'data_and_reservation_input_identities':read(root/'selection-frozen.json')['inputs'],
        'gold_identity':plan['gold_input']['identity'],'assets_identity':identity(root/'assets.json'),
        'assets_verified':read(audit/'assets-reservations.json'),'clock':plan['freeze'],
        'prompt_hash':plan['prompt_hash'],'prompt_examples':[],'setup_attempts':inventory,
        'audit_files':{n:identity(audit/n) for n in audit_names},
        'aggregate_verification':'Independent sums from all160 scored rows, checked against summary and exact assignment; not a third Gold recomputation.',
        'native_controlled_suspend':'not performed','operational_requirements':None,
        'statuses':{'implementation':'completed bounded diagnosis and lineage correction',
            'technical_checks':'native suite and real local diagnosis; limitations in report',
            'reader_improvement':'not demonstrated; no candidate admitted',
            'allocation_improvement':'not demonstrated; no new labels acquired',
            'operational_success':'withheld; requirements unavailable'}}
    return result,manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,action='append',required=True,help='each retained setup root in order; assigned run last')
    parser.add_argument('--audit-dir',type=Path,required=True)
    parser.add_argument('--worktree',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True,help='new aggregate-only directory')
    args = parser.parse_args()
    if len(args.root)!=4:
        parser.error('all four reader-recovery-v1 setup roots are required')
    result,manifest = build(args.root,args.audit_dir,args.worktree)
    args.output_dir.mkdir(parents=True,exist_ok=False)
    for name,value in [('results.json',result),('evidence-manifest.json',manifest)]:
        (args.output_dir/name).write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')
    (args.output_dir/'closed.json').write_text(json.dumps({n:identity(args.output_dir/n) for n in ('results.json','evidence-manifest.json')},sort_keys=True,indent=2)+'\n')
    print(json.dumps({'assigned_calls':160,'assigned_questions':32,'claims':result['claims']}))


if __name__=='__main__':
    main()

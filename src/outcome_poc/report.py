"""Analysis-only reporting and fresh scoring; never imports a native backend.

Operational incompleteness and known wall-clock failure outrank numerical results.
Supplied state is a sanitized evidence handoff, not permission to change a protocol.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import time

from .storage import atomic_json, canonical_bytes, content_hash, read_jsonl

OUTCOMES = ('qualified positive', 'efficiency/quality tradeoff',
            'no advantage over existing methods', 'evidence against the tested mechanism',
            'inconclusive', 'blocked by prerequisites')
PRIVATE_FIELDS = {'raw_output', 'question', 'sentences', 'supporting_facts', 'citations',
                  'prompt_token_ids', 'generated_token_ids', 'access_token', 'password'}


def _hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    result = json.loads(Path(path).read_text(), object_pairs_hook=unique)
    canonical_bytes(result)
    return result


def _number(value, name, *, nullable=False, nonnegative=True):
    if value is None and nullable:
        return value
    if type(value) not in (int, float) or not math.isfinite(value) or (nonnegative and value < 0):
        raise ValueError('invalid ' + name)
    return value


def _count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError('invalid ' + name)
    return value


def ratio_summary(times, successes):
    if not times or len(times) != len(successes):
        raise ValueError('complete question-level times and outcomes required')
    for t in times:
        _number(t, 'time')
    if any(type(s) is not int or s not in (0, 1) for s in successes):
        raise ValueError('binary question outcomes required')
    total = sum(times)
    count = sum(successes)
    return {'n': len(times), 'successes': count, 'quality': count / len(times),
            'total_seconds': total, 'mean_seconds': total / len(times),
            'ratio': total / count if count else None,
            'reason': None if count else 'zero_successes'}


def break_even(adaptation_seconds, mean_a, mean_b):
    _number(adaptation_seconds, 'adaptation', nullable=True)
    _number(mean_a, 'mean A', nullable=True)
    _number(mean_b, 'mean B', nullable=True)
    delta = mean_b - mean_a if mean_a is not None and mean_b is not None else None
    reason = ('unknown_per_query_saving' if delta is None else 'nonpositive_saving' if delta <= 0 else
              'unknown_adaptation_cost' if adaptation_seconds is None else None)
    return {'queries': adaptation_seconds / delta if reason is None else None,
            'reason': reason, 'delta_t': delta}


def cost_inventory(rows):
    """Physical rows are independent of method allocations and nested breakdowns."""
    sources = {}
    for row in rows:
        identity = row['physical_id']
        namespace = row.get('run_identity')
        origin = row.get('original_physical_id')
        if namespace is not None and (not isinstance(namespace, str) or not namespace):
            raise ValueError('run identity must identify protocol/root')
        if origin is not None and (not isinstance(origin, str) or not origin):
            raise ValueError('original physical identity must be nonempty')
        if origin:
            identity = 'origin:' + origin
        elif namespace:
            identity = namespace + ':' + identity
        if not isinstance(identity, str) or not identity:
            raise ValueError('physical source identity required')
        seconds = _number(row.get('seconds'), 'physical seconds', nullable=True)
        if seconds is None and not row.get('reason'):
            raise ValueError('unknown cost requires a reason')
        source = {key: row.get(key) for key in ('seconds', 'parent_id', 'category', 'reason')}
        if source['parent_id'] and namespace:
            source['parent_id'] = namespace + ':' + source['parent_id']
        if identity in sources and sources[identity] != source:
            raise ValueError('conflicting physical source identity')
        sources[identity] = source
    for identity in sources:
        seen = {identity}
        parent = sources[identity]['parent_id']
        while parent:
            if parent in seen or parent not in sources:
                raise ValueError('cyclic or missing enclosing cost source')
            seen.add(parent)
            parent = sources[parent]['parent_id']
    roots = sorted(k for k, row in sources.items() if not row['parent_id'])
    unknown = [k for k in roots if sources[k]['seconds'] is None]
    total = sum(sources[k]['seconds'] for k in roots if sources[k]['seconds'] is not None)
    return {'known_physical_seconds': total, 'total_physical_seconds': None if unknown or not roots else total,
            'reason': 'no_cost_sources' if not roots else 'unknown_costs' if unknown else None,
            'unknown_physical_ids': unknown, 'counted_physical_ids': roots,
            'sources': sources, 'rule': 'unique physical roots only; nested components and reused allocations excluded'}


def _claims(state):
    analysis = state.get('analysis') or {}
    primary = analysis.get('primary') or {}
    flags = primary.get('recorded_flags') or {}
    ci = primary.get('ci')
    interval = isinstance(ci, list) and len(ci) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in ci) and ci[0] <= ci[1]
    complete = state.get('execution_status') == 'complete'
    valid = (complete and state.get('wall_time_valid') is True and primary.get('status') == 'valid'
             and flags.get('timing_stationary') is True and flags.get('deterministic_outputs') is True
             and flags.get('single_dominant') is False and interval)
    timing = state.get('timing_validation') or {}
    efficiency = bool(valid and primary.get('efficiency_advantage') is True and ci[1] < 0
                      and timing.get('status') == 'passed' and timing.get('evidence'))
    guards = analysis.get('quality_guards') or []
    pairs = {(g.get('comparator'), g.get('metric')) for g in guards}
    exact = len(guards) == 4 and pairs == {(c, m) for c in ('selected', 'fixed_ten') for m in ('joint_em', 'answer_em')}
    def bounds(g):
        values = g.get('ci')
        return (isinstance(values, list) and len(values) == 2
                and all(type(v) in (int, float) and math.isfinite(v) for v in values)
                and -1 <= values[0] <= values[1] <= 1 and g.get('tail_alpha') == .05 / 16)
    exact = exact and all(bounds(g) for g in guards)
    regressions = state.get('regressions') or {}
    preserved = bool(complete and analysis.get('quality_outcomes_valid') is True and exact
                     and all(g['ci'][0] >= 0 for g in guards)
                     and regressions.get('failure_clear') is True and regressions.get('latency_clear') is True
                     and state.get('wall_time_valid') is True)
    loss = bool(exact and any(g['ci'][1] < 0 for g in guards))
    return {'efficiency': efficiency, 'quality_preserved': preserved,
            'quality_loss_supported': loss, 'primary_valid': bool(valid)}


def classify_outcome(evidence: dict) -> str:
    if evidence.get('execution_status') == 'blocked' and evidence.get('missing_prerequisites'):
        return 'blocked by prerequisites'
    claims = _claims(evidence)
    if not claims['primary_valid']:
        return 'inconclusive'
    if claims['efficiency']:
        return 'efficiency/quality tradeoff' if claims['quality_loss_supported'] else 'qualified positive'
    ci = evidence['analysis']['primary']['ci']
    if ci[0] > 0:
        # A worse selected pair is narrower evidence than falsifying a mechanism.
        return 'no advantage over existing methods'
    return 'inconclusive'


def method_rows(protocol, scores, predictions, events, evidence):
    """Every role keeps its assignment; primary repetitions are averaged within q."""
    jobs = protocol['schedule']['jobs']
    expected = [j['job_id'] for j in jobs]
    def unique(values, key):
        mapping = {getattr(row, key): row for row in values}
        if len(mapping) != len(values):
            raise ValueError('duplicate scheduled record')
        return mapping
    byscore, byprediction = unique(scores, 'job_id'), unique(predictions, 'job_id')
    byevent = unique(events, 'event_id')
    info = {row['job_id']: row for row in evidence['jobs']}
    if len(set(expected)) != len(expected) or any(set(m) != set(expected) for m in (byscore, byprediction, info)):
        raise ValueError('full assigned schedule required')
    if len(info) != len(evidence['jobs']):
        raise ValueError('duplicate job evidence')
    groups = defaultdict(list)
    for job in jobs:
        groups[(job['scope'], job.get('arm'), job['method']['config_id'])].append(job)
    n = len(protocol['sample']['task_ids'])
    result = []
    for (scope, arm, config), assigned in groups.items():
        byquestion = defaultdict(list)
        for job in assigned:
            score = byscore[job['job_id']]
            if score.task_id != job['task_id'] or score.repetition_id != job['repetition_id']:
                raise ValueError('score differs from assigned identity')
            byquestion[job['task_id']].append(score)
        repetitions = protocol['methods']['repetitions'] if scope == 'primary' else 1
        if set(byquestion) != set(protocol['sample']['task_ids']) or any(len(v) != repetitions for v in byquestion.values()):
            raise ValueError('method assigned denominator incomplete')
        ordered = [sorted(byquestion[q], key=lambda s: s.repetition_id) for q in protocol['sample']['task_ids']]
        times = [sum(s.total_serving_seconds for s in v) / repetitions for v in ordered]
        successes = [v[0].joint_em for v in ordered]
        deterministic = all(len({(s.joint_em, s.answer_em) for s in v}) == 1 for v in ordered)
        ratios = ratio_summary(times, successes)
        ids = [j['job_id'] for j in assigned]
        owned = [event_id for jid in ids for event_id in info[jid]['event_ids']]
        if len(owned) != len(set(owned)) or any(eid not in byevent for eid in owned):
            raise ValueError('incomplete or duplicate paid event ownership')
        generations = [byevent[eid] for eid in owned if byevent[eid].role.startswith('generation:')]
        status = Counter(byprediction[jid].status for jid in ids)
        ordered_times = sorted(times)
        result.append({'scope': scope, 'arm': arm, 'config_id': config, 'assigned_n': n,
            'repetitions': repetitions, 'assigned_jobs': len(ids), 'joint_em': ratios['quality'],
            'joint_successes': ratios['successes'], 'answer_em': sum(v[0].answer_em for v in ordered) / n,
            'support_f1': sum(sum(s.support_f1 for s in v) / repetitions for v in ordered) / n,
            'mean_seconds': ratios['mean_seconds'], 'p95_seconds': ordered_times[max(0, math.ceil(.95*n)-1)],
            'ratio': ratios['ratio'], 'reason': ratios['reason'],
            'prompt_tokens': sum(e.prompt_tokens for e in generations),
            'output_tokens': sum(e.output_tokens for e in generations), 'paid_calls': len(generations),
            'failure_rate': 1 - status.get('ok', 0) / len(ids), 'statuses': dict(status),
            'adaptation_seconds': None, 'adaptation_reason': 'method attribution supplied separately',
            'deterministic_scores': deterministic,
            'outcome_convention': 'first repetition diagnostic only' if not deterministic else 'fixed binary within question',
            'latency_convention': 'nearest-rank p95 of within-question mean; paid token/call totals include all attempts'})
    return result


def _assignment(protocol):
    return {'assigned_questions': len(protocol['sample']['task_ids']),
            'assigned_jobs': len(protocol['schedule']['jobs'])}


def _admit(protocol, root):
    from .protocol import verify_protocol
    from .protected import validate_run
    from .schemas import ScoredTask
    if verify_protocol(Path(protocol['output_dir']) / 'protocol.json') != protocol:
        raise ValueError('report protocol mismatch')
    predictions, context = validate_run(protocol, root)
    marker = _read(root / 'scores.jsonl.closed.json')
    required = {'scores.jsonl', 'scores.gold.jsonl', 'job-evidence.json',
                'predictions.closed.json', 'protected-run.closed.json'}
    if (marker.get('protocol_hash') != protocol['protocol_hash'] or
            marker.get('paid_receipt_coverage') != 'forward_v2' or
            not required.issubset(marker.get('hashes', {}))):
        raise ValueError('complete score receipt required')
    for name, digest in marker['hashes'].items():
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()) or _hash(path) != digest:
            raise ValueError('score receipt checksum/path mismatch')
    scores = [ScoredTask(**r) for r in read_jsonl(root / 'scores.jsonl')]
    expected = [j['job_id'] for j in protocol['schedule']['jobs']]
    if ([s.job_id for s in scores] != expected or marker['record_count'] != len(expected)
            or marker['assigned_unique_tasks'] != len(protocol['sample']['task_ids'])):
        raise ValueError('full assigned score denominator required')
    names = sorted(required | {'scores.jsonl.closed.json', 'analysis.json'})
    return predictions, context, scores, {name: _hash(root / name) for name in names}


def rescore_predictions(predictions, gold_records, documents, root, context):
    """Use unchanged scoring math and the already validated complete accounting."""
    from .scoring import Scorer
    if {p.task_id for p in predictions} != set(gold_records):
        raise ValueError('exact assigned gold required')
    scores = [Scorer().score(p, gold_records[p.task_id], documents,
                            run_dir=root, accounting_context=context) for p in predictions]
    context.verify_unchanged()
    return scores


def reproduce(protocol: dict | None, run_dir: Path | None, scores_only: bool = True) -> dict:
    if scores_only is not True:
        raise ValueError('reproduction is scores-only; new timing requires separate authorization/provenance')
    if protocol is None:
        return {'status': 'unavailable', 'reason': 'no_frozen_protocol', 'gold_opened': False}
    root = Path(run_dir or protocol['run_dir'])
    if root.resolve() != Path(protocol['run_dir']).resolve():
        raise ValueError('frozen run directory mismatch')
    assignment = _assignment(protocol)
    if not (root / 'protected-run.closed.json').exists():
        return {'status': 'unavailable', 'reason': 'incomplete_run', 'gold_opened': False,
                'protocol_hash': protocol['protocol_hash'], **assignment}
    started = time.perf_counter()
    predictions, context, original, hashes = _admit(protocol, root)
    from .data_runtime import DocumentStore
    from .schemas import GoldRecord, validate_record
    from .statistics import analyze_run
    from .runner import load_events
    # Original projection is itself sealed; prove it equals the assigned source.
    prepared = Path(protocol['methods']['retrieval']['prepared_dir'])
    gold_path = prepared / 'gold/gold.jsonl'
    manifest = _read(prepared / 'manifest.json')
    if _hash(gold_path) != manifest['files']['gold/gold.jsonl']['sha256']:
        raise ValueError('prepared gold checksum changed')
    assigned = set(protocol['sample']['task_ids'])
    gold = {}
    for row in read_jsonl(gold_path):
        if row['task_id'] not in assigned:
            continue
        row['supporting_facts'] = [tuple(p) for p in row['supporting_facts']]
        value = GoldRecord(**row)
        validate_record(value)
        if value.task_id in gold:
            raise ValueError('duplicate assigned gold')
        gold[value.task_id] = value
    if set(gold) != assigned:
        raise ValueError('missing assigned gold')
    projection = list(read_jsonl(root / 'scores.gold.jsonl'))
    if content_hash(projection) != content_hash([gold[q] for q in protocol['sample']['task_ids']]):
        raise ValueError('assigned gold projection differs from source')
    documents = DocumentStore(root / 'selected-documents.jsonl')
    expected_documents = {d for t in protocol['sample']['tasks'] for d in t['candidate_ids']}
    if set(documents.offsets) != expected_documents:
        raise ValueError('exact selected documents required')
    scores = rescore_predictions(predictions, gold, documents, root, context)
    if content_hash(scores) != content_hash(original):
        raise ValueError('fresh score digest differs from original')
    analysis = analyze_run(protocol, scores, load_events(root))
    if content_hash(analysis) != content_hash(_read(root / 'analysis.json')):
        raise ValueError('fresh analysis digest differs from original')
    context.verify_unchanged()
    if any(_hash(root / name) != digest for name, digest in hashes.items()):
        raise ValueError('reproduction inputs changed')
    return {'status': 'reproduced', 'gold_opened': True, 'protocol_hash': protocol['protocol_hash'],
            **assignment, 'score_digest': content_hash(scores), 'analysis_digest': content_hash(analysis),
            'input_hashes': hashes, 'source_sha256': _hash(__file__), 'analysis_seconds': time.perf_counter()-started,
            'method': 'fresh frozen Scorer.score and analyze_run; no cached score_run or generation',
            'limitation': 'deterministic scoring reproduction does not validate the original wall-time endpoint'}


def _sanitize(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in PRIVATE_FIELDS:
                raise ValueError('private/raw evidence cannot enter public report: ' + key)
            _sanitize(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _sanitize(item)


def _display(value):
    if value is None:
        return 'unavailable'
    if isinstance(value, float):
        return f'{value:.6g}'
    return str(value).replace('|', '\\|').replace('\n', ' ')


def _table(rows, columns):
    return '\n'.join(['| ' + ' | '.join(columns) + ' |', '| ' + ' | '.join('---' for _ in columns) + ' |'] +
                     ['| ' + ' | '.join(_display(r.get(k)) for k in columns) + ' |' for r in rows])


def report(state: dict, output_path: Path) -> dict:
    """Render a sanitized handoff; missing evidence stays explicit and nonclaiming."""
    canonical_bytes(state)
    _sanitize(state)
    state = deepcopy(state)
    status = state.get('execution_status', 'development_only')
    if status not in ('complete', 'incomplete', 'blocked', 'development_only', 'unexecuted'):
        raise ValueError('unknown execution status')
    state['execution_status'] = status
    n = _count(state.get('assigned_questions', 0), 'assigned questions')
    jobs = _count(state.get('assigned_jobs', 0), 'assigned jobs')
    completed = state.get('completed_jobs')
    if completed is not None and _count(completed, 'completed jobs') > jobs:
        raise ValueError('completed jobs exceeds assignment')
    if status == 'complete' and (not n or not jobs or completed != jobs):
        raise ValueError('complete status requires full assigned closure')
    if status != 'complete' and (state.get('analysis') or state.get('methods')):
        raise ValueError('incomplete/unclosed primary cannot report subset scores')
    rows = state.get('methods', [])
    if any(r['assigned_n'] != n for r in rows):
        raise ValueError('method assigned denominator differs')
    state['assigned_questions'], state['assigned_jobs'] = n, jobs
    state['analysis'] = state.get('analysis')
    state['claims'] = _claims(state)
    for row in rows:
        row['primary_interval'] = ((state.get('analysis') or {}).get('primary') or {}).get('ci') if row.get('scope') == 'primary' else None
        row['interval_scope'] = 'A minus frozen B; approximate diagnostic if invalid' if row.get('scope') == 'primary' else 'not a prespecified primary comparison'
    state['outcome'] = classify_outcome(state)
    if state['claims']['efficiency'] and (not state.get('scope') or not all((state.get('selected') or {}).get(a) for a in ('A', 'B'))):
        raise ValueError('positive claim requires tested scope and selected pair')
    state['timing'] = {'wall_time_valid': state.get('wall_time_valid'),
        'reason': state.get('wall_time_reason', 'wall-time assessment unavailable'),
        'interpretation': 'active-compute diagnostic only' if state.get('wall_time_valid') is False else
                          'wall-time evidence verified' if state.get('wall_time_valid') is True else 'timing validity unresolved'}
    if 'cost_sources' in state:
        state['physical_costs'] = cost_inventory(state['cost_sources'])
    economics = state.get('economics')
    if economics:
        state['break_even'] = (break_even(economics.get('adaptation_seconds'), economics.get('mean_a'), economics.get('mean_b'))
                              if state.get('wall_time_valid') is True else
                              {'queries': None, 'delta_t': None, 'reason': 'wall_time_invalid_or_unverified'})
    missing = list(state.get('remaining_risks', []))
    for key in ('environment', 'assets', 'dependencies', 'population', 'memory', 'adaptation',
                'attribution', 'transfer', 'amendments', 'rulings', 'reproduction'):
        if key not in state:
            missing.append(key + ': unavailable in supplied evidence')
    state['remaining_risks'] = missing
    text = ['# Outcome-aware context allocation — experimental report', '',
            'We test whether a cheap controller can choose two or ten already-retrieved paragraphs before answering. '
            'The primary success requires both the correct answer and supporting citations. Reading savings are not web-search savings.', '',
            'Scope: ' + state.get('scope', 'Scope unavailable; no generalization claim.'), '',
            f'Execution: {status}. Assigned questions: {n}; assigned pipeline jobs: {jobs}; completed jobs: {_display(completed)}.', '',
            state['timing']['reason'] + '. ' + state['timing']['interpretation'] + '.', '']
    if status != 'complete':
        text += ['Primary scores and inference are unavailable. The original assignment is retained; no complete-case subset is scored.', '']
    if state['claims']['efficiency']:
        text += ['The valid selected-pair comparison supports lower seconds per benchmark-supported success within the stated scope. '
                 + ('All four quality guards and regression checks passed.' if state['claims']['quality_preserved'] else
                    'However, quality preservation remains unresolved.'), '']
    else:
        text += ['No wall-time efficiency claim is established. '
                 + ('All four quality guards and regression checks passed.' if state['claims']['quality_preserved'] else
                    'The required quality preservation remains unresolved without all four guards and regression clearance.'), '']
    if rows:
        display_rows = deepcopy(rows)
        for row in display_rows:
            if row.get('reason') == 'zero_successes':
                row['ratio'] = 'infinity (zero successes)'
        text += ['## Same-assignment method table', '', _table(display_rows, [
            'scope', 'arm', 'config_id', 'assigned_n', 'repetitions', 'joint_em', 'answer_em', 'support_f1',
            'mean_seconds', 'p95_seconds', 'ratio', 'prompt_tokens', 'output_tokens', 'paid_calls', 'failure_rate', 'adaptation_seconds', 'primary_interval']), '',
                 'All repetitions remain within their assigned question. Paid calls/tokens include failed attempts; '
                 'p95 is the nearest rank of per-question mean times. Nondeterministic binary outcomes use '
                 'the first scheduled value for descriptive display only; their primary inference is invalid.', '']
    analysis = state.get('analysis') or {}
    if analysis:
        primary = analysis.get('primary', {})
        text += ['## Primary approximate interval and validity', '',
                 'The interval includes finite-population sampling and paired timing uncertainty; repetitions are within questions. '
                 'A numerical interval cannot override incomplete work, clock failure, output nondeterminism or unresolved influence/stationarity.', '',
                 '```json', json.dumps(primary, indent=2, ensure_ascii=False, allow_nan=False), '```', '',
                 '## Four simultaneous quality guards', '',
                 _table(analysis.get('quality_guards', []), ['comparator', 'metric', 'harm_count', 'rescue_count', 'ci', 'tail_alpha']), '']
    # These fields are explicit sanitized metadata; raw records are rejected above.
    sections = ('selected', 'work_packages', 'environment', 'assets', 'dependencies', 'population', 'protocol',
                'tuning', 'memory', 'physical_costs', 'adaptation', 'break_even', 'direct_replay', 'post_cache',
                'attribution', 'transfer', 'diagnostics', 'amendments', 'rulings', 'provenance', 'reproduction',
                'timing_validation', 'regressions', 'remaining_risks')
    for key in sections:
        if key in state:
            text += ['## ' + key.replace('_', ' ').capitalize(), '', '```json',
                     json.dumps(state[key], indent=2, ensure_ascii=False, allow_nan=False), '```', '']
    text += ['Annotation agreement is not certified truth. Citation limitations, public pretraining contamination, '
             'packet-only retrieval and this hardware constrain interpretation. Unexecuted transfer does not establish generalization.', '',
             state['outcome'], '']
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # The report content and machine-readable state have the same decision.
    path.write_text('\n'.join(text))
    atomic_json(path.parent / 'summary.json', state)
    atomic_json(path.parent / 'remaining-risks.json', {'risks': missing})
    if rows:
        columns = list(rows[0])
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, allow_nan=False) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()} for row in rows)
        (path.parent / 'baseline-table.csv').write_text(stream.getvalue())
    return state


def closed_state(protocol, supplemental=None):
    """Read only complete, already scored evidence; does not open gold records."""
    root = Path(protocol['run_dir'])
    supplemental = deepcopy(supplemental or {})
    reserved = {'execution_status', 'assigned_questions', 'assigned_jobs', 'completed_jobs',
                'analysis', 'methods', 'selected', 'protocol'}
    if reserved & supplemental.keys():
        raise ValueError('supplemental reporting metadata cannot replace frozen results')
    state = {**supplemental, **_assignment(protocol),
             'selected': protocol['methods']['selected'],
             'protocol': {'protocol_hash': protocol['protocol_hash'], 'digests': protocol['digests']}}
    if not (root / 'protected-run.closed.json').exists():
        return {**state, 'execution_status': 'incomplete', 'analysis': None, 'methods': [],
                'scope': supplemental.get('scope', 'Original frozen assignment; no subset scoring')}
    predictions, context, scores, hashes = _admit(protocol, root)
    from .runner import load_events
    from .statistics import analyze_run
    events = load_events(root)
    analysis = analyze_run(protocol, scores, events)
    if content_hash(analysis) != content_hash(_read(root / 'analysis.json')):
        raise ValueError('base analysis differs from closed inputs')
    assessment = supplemental.pop('validity_assessment', None)
    if assessment is not None:
        analysis = analyze_run(protocol, scores, events, validity_assessment=assessment)
    rows = method_rows(protocol, scores, predictions, events, _read(root / 'job-evidence.json'))
    context.verify_unchanged()
    if any(_hash(root / name) != digest for name, digest in hashes.items()):
        raise ValueError('report inputs changed')
    # Keep per-question/private payloads out of public state; the analysis hash
    # binds the full influence/LOO/raw paired evidence, retained in the run.
    public_analysis = {k: analysis[k] for k in ('primary', 'quality_guards', 'quality_outcomes_valid',
                       'assessment_binding', 'validity_assessment_hash', 'flag_evidence')}
    return {**state, 'execution_status': 'complete', 'completed_jobs': len(scores),
            'methods': rows, 'analysis': public_analysis,
            'provenance': {'run_dir': str(root), 'input_hashes': hashes, 'analysis_digest': content_hash(analysis)}}


def main(args):
    protocol = _read(Path(args.protocol)) if getattr(args, 'protocol', None) else None
    if args.command == 'reproduce':
        result = reproduce(protocol, Path(args.run_dir) if getattr(args, 'run_dir', None) else None)
        output = Path(args.output) if getattr(args, 'output', None) else Path('artifacts/runs/task16-reproduce/receipt.json')
        if protocol and output.resolve().is_relative_to(Path(protocol['run_dir']).resolve()):
            raise ValueError('reproduction output must not modify the original run')
        atomic_json(output, result)
        print(json.dumps(result, allow_nan=False))
        return 0
    if getattr(args, 'state', None):
        if protocol:
            raise ValueError('choose state or protocol')
        state = _read(Path(args.state))
    elif protocol:
        if getattr(args, 'run_dir', None) and Path(args.run_dir).resolve() != Path(protocol['run_dir']).resolve():
            raise ValueError('frozen run directory mismatch')
        supplemental = _read(Path(args.config)) if getattr(args, 'config', None) else {}
        state = closed_state(protocol, supplemental)
    else:
        raise ValueError('report requires --state or --protocol')
    output = Path(args.output) if getattr(args, 'output', None) else Path('artifacts/final_report.md')
    if protocol and output.resolve().is_relative_to(Path(protocol['run_dir']).resolve()):
        raise ValueError('report output must not modify the original run')
    result = report(state, output)
    print(json.dumps({'outcome': result['outcome'], 'report': str(output)}))
    return 0

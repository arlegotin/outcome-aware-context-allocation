"""Recompute actual Scorer metrics only after the entire diagnosis closes."""
from dataclasses import asdict
from pathlib import Path
import sys
import numpy as np

from ..data_runtime import DocumentStore
from ..schemas import Prediction, GoldRecord, PairedActionRow, validate_record
from ..scoring import Scorer, score_answer, score_support, EVALUATOR_PROVENANCE
from ..statistics import paired_quality_bounds
from ..oracle import headroom
from ..storage import canonical_bytes, content_hash, read_jsonl, append_jsonl
from ..followup.clock import continuous_ns
from ..followup.runtime import completion, session_accounting
from ..followup.study import verify_index
from ..reader_probe.study import inventory
from .analysis import summarize,validation_admission
from .study import verify, read, identity, publish, verify_files, GROUP_ARMS, jobs,group_arms


def closed_records(root):
    root = Path(root).resolve()
    plan = verify(root)
    # Gold-enabled recomputation may run from a live checkout only when every
    # loaded project module has exactly the frozen source bytes.
    for name,module in list(sys.modules.items()):
        if name.startswith('outcome_poc') and getattr(module,'__file__',None):
            relative = Path(*name.split('.'))
            expected = root/'source/src'/relative
            expected = expected/'__init__.py' if hasattr(module,'__path__') else expected.with_suffix('.py')
            if identity(Path(module.__file__)) != identity(expected):
                raise ValueError(f'scorer loaded source drift: {name}')
    records = []
    expected = {j['job_id'] for j in read(root/'schedule.json')}
    if not (root/'jobs').exists() or {p.name for p in (root/'jobs').iterdir()} != expected:
        raise ValueError('entire assigned diagnosis incomplete or contains extra jobs; Gold forbidden')
    for group in group_arms(plan['config']):
        closure = read(root/'stages'/group/'closed.json')
        roster = jobs(root,group)
        stage_files = {k:v for k,v in inventory(root/'stages'/group).items() if k!='closed.json'}
        if stage_files != closure['stage_files']:
            raise ValueError('closed recovery stage telemetry changed')
        if (closure['plan_hash']!=plan['plan_hash'] or closure['assigned_jobs']!=len(roster) or
                closure['job_ids_hash']!=content_hash([j['job_id'] for j in roster]) or
                closure['session_accounting']!=session_accounting(root,group,plan,require_closed=True) or
                closure['session_accounting']['status']!='complete' or closure['session_accounting']['sessions']!=1):
            raise ValueError('diagnosis closure/accounting mismatch')
        forecast = None
        if plan['config']['protocol_id']=='reader-evidence-first-v1':
            forecast = read(root/'stages'/group/'render-forecast.json')
            settings = plan['config']['reader']
            if (set(forecast['jobs'])!={j['job_id'] for j in roster} or
                    forecast['boot_id']!=plan['freeze']['boot_id'] or forecast['clock_domain']!='mach_continuous_time' or
                    not 0<=forecast['start_ns']<=forecast['stop_ns'] or forecast['assigned_generations_so_far']!=0 or
                    forecast['max_context_tokens']!=settings['max_context_tokens'] or forecast['max_new_tokens']!=settings['max_new_tokens'] or
                    forecast['maximum_input_tokens']+settings['max_new_tokens']>settings['max_context_tokens']):
                raise ValueError('invalid complete prompt forecast')
        for job in roster:
            if inventory(root/'jobs'/job['job_id']) != closure['jobs'][job['job_id']]:
                raise ValueError('closed recovery job changed')
            value = completion(root,plan,job)
            if value is None:
                raise ValueError('incomplete assigned recovery job')
            boundary = read(root/'stages'/group/'requests'/f"{job['job_id']}.json")
            receipt = value[1]
            if forecast is not None:
                predicted = forecast['jobs'][job['job_id']]
                if (forecast['stop_ns']>receipt['start_ns'] or predicted['prompt_hash']!=value[0]['prompt_hash'] or
                        predicted['prompt_tokens']!=value[0]['result']['prompt_tokens']):
                    raise ValueError('paid prompt/token identity differs from pre-answer forecast')
            if (boundary['boot_id']!=plan['freeze']['boot_id'] or boundary['clock_domain']!='mach_continuous_time' or
                    boundary['start_ns']!=receipt['start_ns'] or boundary['stop_ns']<receipt['stop_ns'] or
                    boundary['seconds']!=(boundary['stop_ns']-boundary['start_ns'])/1e9 or
                    boundary['receipt']!=identity(root/'jobs'/job['job_id']/'receipt.json')):
                raise ValueError('complete durable request boundary mismatch')
            records.append((job,*value))
    verify_index(root/'index-setup')
    return plan,records


def score(root):
    root = Path(root).resolve()
    # No scorer output directory and no Gold read before complete-assignment
    # validation. Reinvocation recomputes; it never returns cached scores.
    plan,records = closed_records(root)
    start = continuous_ns()
    error = None
    try:
        gold_path = Path(plan['gold_input']['path'])
        if identity(gold_path) != plan['gold_input']['identity']:
            raise ValueError('Gold source changed')
        assigned = {j['task_id'] for j,_,_ in records}
        gold = {}
        for row in read_jsonl(gold_path):
            if row['task_id'] not in assigned:
                continue
            if row['task_id'] in gold:
                raise ValueError('duplicate assigned Gold')
            value = GoldRecord(row['task_id'],row['answer'],[tuple(v) for v in row['supporting_facts']])
            validate_record(value)
            gold[value.task_id] = value
        if set(gold)!=assigned:
            raise ValueError('assigned Gold missing')
        documents = DocumentStore(root/'documents.jsonl')
        asset = read(root/'assets.json')['assets']['reader']
        rows = []
        for job,payload,receipt in records:
            boundary = read(root/'stages'/job['group']/'requests'/f"{job['job_id']}.json")
            result = payload['result']
            prediction = Prediction(plan['config']['protocol_id'],job['task_id'],job['arm'],plan['plan_hash'],job['job_id'],1,0,
                payload['evidence_ids'],result['raw_output'],result['answer'],[tuple(c) for c in result['citations']],result['status'],
                asset['revision'],payload['prompt_hash'] or 'unavailable','greedy',boundary['seconds'],
                result['prompt_tokens'],result['generated_tokens'],payload['calls'],['continuous enclosing receipt'])
            measured = Scorer().score(prediction,gold[job['task_id']],documents)
            # Scorer's diagnostic elapsed fallback is deliberately supplied the
            # authoritative continuous enclosing receipt, not legacy event sums.
            pairs = {(documents.get(d).title,i) for d,i in prediction.citations}
            support = score_support(pairs,set(gold[job['task_id']].supporting_facts))
            answer = score_answer(prediction.answer or '',gold[job['task_id']].answer)
            row = {**{k:v for k,v in asdict(measured).items() if k!='total_experiment_seconds'},
                'arm':job['arm'],'seconds':boundary['seconds'],'status':result['status'],
                'active_seconds':boundary['active_seconds'],'drift_seconds':boundary['seconds']-boundary['active_seconds'],
                'prompt_tokens':result['prompt_tokens'],'generated_tokens':result['generated_tokens'],'calls':payload['calls'],
                'support_precision':support['precision'],'support_recall':support['recall'],
                'answer_precision':answer['precision'],'answer_recall':answer['recall'],
                'missing_reference_supports':len(set(gold[job['task_id']].supporting_facts)-pairs),
                'excess_reference_citations':len(pairs-set(gold[job['task_id']].supporting_facts)),
                'evidence_membership_valid':all(d in payload['view'] and i in payload['view'][d] for d,i in prediction.citations),
                'relation_review':'unassessed; missing/excess reference citations do not establish semantic causality'}
            if not row['evidence_membership_valid']:
                row['joint_em'],row['joint_f1'] = 0,0.
            rows.append(row)
        summary = summarize(rows)
        cohorts = read(root/'cohorts.json')
        by_cell = {(r['task_id'],r['arm']):r for r in rows}
        summary['paired_diagnostics'] = {}
        validation = plan['config']['protocol_id']=='reader-evidence-first-v1'
        active = cohorts['validation' if validation else 'diagnosis']
        contrasts = (('evidence-first','baseline'),) if validation else (
            ('support-sentences','support-documents'),('support-documents','10'),('10','2'),('5','10'))
        for a,b in contrasts:
            summary['paired_diagnostics'][a+'-minus-'+b] = {
                endpoint:paired_quality_bounds(np.array([by_cell[i,a][endpoint] for i in active]),
                    np.array([by_cell[i,b][endpoint] for i in active]),
                    cohorts['eligibility_count'],.003125 if validation else .0125) for endpoint in ('joint_em','answer_em')}
        if validation:
            summary['reader_validation'] = validation_admission(rows,cohorts['eligibility_count'])
        else:
            tasks = {t['task_id']:t for t in read_jsonl(root/'tasks.jsonl')}
            paired = [PairedActionRow(task_id=i,question=tasks[i]['question'],ranked_documents=[],features={},
                        small_prediction_id=by_cell[i,'2']['job_id'],full_prediction_id=by_cell[i,'10']['job_id'],
                        small_joint_em=by_cell[i,'2']['joint_em'],full_joint_em=by_cell[i,'10']['joint_em'],
                        small_answer_em=by_cell[i,'2']['answer_em'],full_answer_em=by_cell[i,'10']['answer_em'],
                        small_event_ids=[],full_event_ids=[],small_cost_seconds=by_cell[i,'2']['seconds'],
                        full_cost_seconds=by_cell[i,'10']['seconds'],small_status=by_cell[i,'2']['status'],
                        full_status=by_cell[i,'10']['status']) for i in active]
            summary['clairvoyant_headroom'] = headroom(paired)
            summary['clairvoyant_headroom']['answer_guard'] = 'not enforced by frontier; no deployable/quality-preserving allocation claim'
        summary.update(plan_hash=plan['plan_hash'],assigned_jobs=len(rows),assigned_questions=len(assigned),
            population=cohorts['eligibility_count'],evaluator=EVALUATOR_PROVENANCE,
            source_commit=plan['source_commit'],source_snapshot_hash=content_hash(inventory(root/'source')),
            reserved_validation=0 if validation else len(cohorts['validation_reserved']),reserved_evaluation=len(cohorts['evaluation_reserved']))
        # Disjoint setup and resident envelopes; nested service/lifecycle/warmup
        # are disclosed separately, never added a second time.
        summary['costs'] = {'resident_session_seconds':sum(session_accounting(root,g,plan,require_closed=True)['exact_seconds'] for g in group_arms(plan['config'])),
            'index_setup_seconds':sum((r['stop_ns']-r['start_ns'])/1e9 for r in read_jsonl(root/'setup-attempts.jsonl')),
            'service_seconds':sum(r['seconds'] for r in rows),'nested_scope':'service and warmup already inside resident envelopes',
            'project_engineering_and_historical_adaptation_seconds':None,'break_even':None,
            'break_even_reason':'no measured learned-policy saving or attributable incremental adaptation cost'}
        output = root/'scores'
        output.mkdir(exist_ok=True)
        payload = b''.join(canonical_bytes(r)+b'\n' for r in rows)
        path = output/'scores.jsonl'
        if path.exists() and path.read_bytes()!=payload:
            raise ValueError('fresh recomputation differs from immutable scores')
        if not path.exists():path.write_bytes(payload)
        publish(output/'summary.json',summary)
        closed_records(root)
        publish(output/'closed.json',{'plan_hash':plan['plan_hash'], 'assigned_jobs':len(rows),
            'files':{n:identity(output/n) for n in ('scores.jsonl','summary.json')},
            'prediction_closures':{g:identity(root/'stages'/g/'closed.json') for g in group_arms(plan['config'])},
            'scorer_source':identity(Path(__file__))})
        return summary
    except BaseException as caught:
        error = caught
        raise
    finally:
        append_jsonl(root/'scoring-attempts.jsonl',{'start_ns':start,'stop_ns':continuous_ns(),
            'status':'failed' if error else 'ok','error':str(error) if error else None,'clock_domain':'mach_continuous_time'})

"""Gold-enabled scoring stage, isolated from serving imports."""

from collections import Counter
import re
import string
import time
import hashlib
import json
from pathlib import Path

from .data_runtime import DocumentStore
from .schemas import GoldRecord, Prediction, ScoredTask, validate_record
from .storage import append_jsonl, read_jsonl


EVALUATOR_PROVENANCE = {
    'repository': 'hotpotqa/hotpot',
    'revision': 'fa3a36370899e1d85822de61e58c85ea19993154',
    'source_url': 'https://raw.githubusercontent.com/hotpotqa/hotpot/fa3a36370899e1d85822de61e58c85ea19993154/hotpot_evaluate_v1.py',
    'source_sha256': 'd35fc91a6db21d791dbdda11daf3856e9359f5701d54e3eefba20d88fecc02c0',
    'source_bytes': 4257,
    'parity_method': 'source-derived synthetic fixtures; external evaluator never executed',
}


def normalize_answer(text: str) -> str:
    lowered = text.lower().translate(str.maketrans('', '', string.punctuation))
    return ' '.join(re.sub(r'\b(a|an|the)\b', ' ', lowered).split())


def _metrics(em: int, precision: float, recall: float) -> dict:
    return {'em': em, 'f1': 2 * precision * recall / (precision + recall) if precision + recall else 0.,
            'precision': precision, 'recall': recall}


def score_answer(prediction: str, gold: str) -> dict:
    prediction, gold = normalize_answer(prediction), normalize_answer(gold)
    em = int(prediction == gold)
    special = {'yes', 'no', 'noanswer'}
    if prediction != gold and (prediction in special or gold in special):
        return _metrics(em, 0., 0.)
    predicted_tokens, gold_tokens = prediction.split(), gold.split()
    overlap = sum((Counter(predicted_tokens) & Counter(gold_tokens)).values())
    if not overlap:
        return _metrics(em, 0., 0.)
    return _metrics(em, overlap / len(predicted_tokens), overlap / len(gold_tokens))


def score_support(predicted: set[tuple[str, int]], gold: set[tuple[str, int]]) -> dict:
    predicted, gold = set(predicted), set(gold)
    overlap = len(predicted & gold)
    return _metrics(int(predicted == gold), overlap / len(predicted) if predicted else 0.,
                    overlap / len(gold) if gold else 0.)


def joint_f1(answer: dict, support: dict) -> float:
    precision = answer['precision'] * support['precision']
    recall = answer['recall'] * support['recall']
    return _metrics(0, precision, recall)['f1']


class Scorer:
    def score(self, prediction: Prediction, gold: GoldRecord, documents: DocumentStore, *,
              run_dir: Path | None = None, accounting_context=None) -> ScoredTask:
        validate_record(prediction)
        validate_record(gold)
        if prediction.task_id != gold.task_id:
            raise ValueError('prediction and gold task IDs differ')
        answer = score_answer(prediction.answer or '', gold.answer)
        support_pairs, valid = set(), prediction.status == 'ok' and bool((prediction.answer or '').strip())
        for doc_id, index in prediction.citations:
            try:
                doc = documents.get(doc_id)
                if doc_id not in prediction.evidence_ids or not 0 <= index < len(doc.sentences):
                    valid = False
                else:
                    support_pairs.add((doc.title, index))
            except KeyError:
                valid = False
        support = score_support(support_pairs, set(gold.supporting_facts))
        # Backward-compatible diagnostic fallback; experimental callers must
        # supply the complete durable run ledger and fail on any missing event.
        if run_dir is None:
            serving_seconds=experiment_seconds=prediction.elapsed_seconds
        else:
            from .runner import accounting
            costs=accounting_context.costs(prediction) if accounting_context is not None else accounting(run_dir,prediction)
            serving_seconds=costs['total_serving_seconds']
            experiment_seconds=costs['total_experiment_seconds']
        result = ScoredTask(prediction.run_id, prediction.task_id, prediction.policy_id,
                            prediction.job_id, prediction.repetition_id, answer['em'], support['em'],
                            answer['em'] * support['em'] if valid else 0,
                            answer['f1'], support['f1'], joint_f1(answer, support) if valid else 0.,
                            serving_seconds, experiment_seconds)
        validate_record(result)
        return result


def main(args) -> int:
    if getattr(args, 'protocol', None):
        from .protocol import _read
        from .runner import load_events
        from .statistics import analyze_run
        from .protected import immutable_json
        protocol=_read(Path(args.protocol))
        if any(getattr(args,name,None) for name in ('predictions','gold','documents','output','run_dir')):
            raise ValueError('protocol scoring uses its frozen assigned paths only')
        root=Path(protocol['run_dir'])
        gold=Path(protocol['methods']['retrieval']['prepared_dir'])/'gold/gold.jsonl'
        scores=score_run(protocol,root,gold)
        result=analyze_run(protocol,scores,load_events(root))
        immutable_json(root/'analysis.json',result)
        print(json.dumps({'status':'scored_closed_run','assigned_jobs':len(scores),
            'assigned_unique_tasks':result['assigned_unique_tasks'],'primary_status':result['primary']['status'],
            'outcome':result['outcome']}))
        return 0
    if any(not getattr(args,name,None) for name in ('predictions','gold','documents','output')):
        raise ValueError('development scoring requires predictions, gold, documents and output')
    started = time.perf_counter()
    predictions_path = Path(args.predictions)
    closure_path = predictions_path.with_suffix('.closed.json')
    if not closure_path.is_file():
        raise ValueError('scoring requires a closed prediction file')
    closure = json.loads(closure_path.read_text())
    if closure.get('prediction_sha256') != hashlib.sha256(predictions_path.read_bytes()).hexdigest():
        raise ValueError('closed prediction file digest mismatch')
    predictions = []
    for row in read_jsonl(predictions_path):
        row['citations'] = [(citation['doc_id'], citation['sentence_index']) for citation in row['citations']]
        prediction = Prediction(**row)
        validate_record(prediction)
        predictions.append(prediction)
    if closure.get('record_count') != len(predictions):
        raise ValueError('closed prediction count mismatch')
    accounting_context=None
    if getattr(args,'run_dir',None):
        from .runner import validate_closed_accounting
        accounting_context=validate_closed_accounting(Path(args.run_dir),predictions)
        if accounting_context.receipt_coverage=='legacy_unsealed':
            raise ValueError('complete-ledger scoring requires paid receipt coverage or explicit legacy seal')
        accounting_context.verify_unchanged()
    # All prediction payloads and optional complete accounting have been closed before gold is opened.
    gold_records = {}
    assigned_task_ids={prediction.task_id for prediction in predictions}
    for row in read_jsonl(Path(args.gold)):
        if row['task_id'] not in assigned_task_ids:
            continue  # Project only assigned annotations; never construct unassigned GoldRecord values.
        row['supporting_facts'] = [tuple(pair) for pair in row['supporting_facts']]
        gold = GoldRecord(**row)
        validate_record(gold)
        if gold.task_id in gold_records:
            raise ValueError('duplicate gold task ID')
        gold_records[gold.task_id] = gold
    if set(gold_records)!=assigned_task_ids: raise ValueError('assigned gold records incomplete')
    documents = DocumentStore(Path(args.documents))
    output = Path(args.output)
    if output.exists():
        raise ValueError('score output already exists')
    gold_projection = output.with_suffix('.gold.jsonl')
    if gold_projection.exists(): raise ValueError('scorer gold projection already exists')
    for task_id in sorted({prediction.task_id for prediction in predictions}):
        append_jsonl(gold_projection, gold_records[task_id])
    scores = [Scorer().score(prediction, gold_records[prediction.task_id], documents, run_dir=Path(args.run_dir) if getattr(args,'run_dir',None) else None, accounting_context=accounting_context) for prediction in predictions]
    for score in scores:
        append_jsonl(output, score)
    from .storage import atomic_json
    atomic_json(output.with_suffix(output.suffix+'.closed.json'), {
        'kind':'separate_closed_run_scorer',
        'scores_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'prediction_sha256':closure['prediction_sha256'],
        'prediction_closure_sha256':hashlib.sha256(closure_path.read_bytes()).hexdigest(),
        'gold_projection_sha256':hashlib.sha256(gold_projection.read_bytes()).hexdigest(),
        'record_count':len(scores), 'scoring_seconds':time.perf_counter()-started,
        'timing_kind':'complete_ledger' if getattr(args,'run_dir',None) else 'diagnostic_interval_fallback',
        'paid_receipt_coverage':accounting_context.receipt_coverage if accounting_context else None,
        'scorer_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    print(json.dumps({'assigned_predictions': len(scores), 'joint_successes': sum(score.joint_em for score in scores),
                      'timing_kind':'complete_ledger' if getattr(args,'run_dir',None) else 'diagnostic_interval_fallback',
        'paid_receipt_coverage':accounting_context.receipt_coverage if accounting_context else None,
        'scorer_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}))
    return 0


def score_run(protocol: dict, run_dir: Path, gold_path: Path, *, documents_path=None) -> list[ScoredTask]:
    """Validate the entire frozen run before opening the assigned gold projection."""
    from .protocol import verify_protocol, file_hash
    from .protected import validate_run, job_evidence, immutable_json
    from .storage import canonical_bytes, content_hash
    root=Path(run_dir)
    if verify_protocol(Path(protocol['output_dir'])/'protocol.json') != protocol:
        raise ValueError('scorer protocol mismatch')
    predictions,context=validate_run(protocol,root)
    closure=root/'scores.jsonl.closed.json'
    if closure.exists():
        marker=json.loads(closure.read_text())
        if marker['protocol_hash']!=protocol['protocol_hash'] or any(file_hash(root/p)!=h for p,h in marker['hashes'].items()):
            raise ValueError('score closure checksum changed')
        return [ScoredTask(**r) for r in read_jsonl(root/'scores.jsonl')]
    assigned=set(protocol['sample']['task_ids'])
    records={}
    if not protocol['fixture']:
        prepared=Path(protocol['methods']['retrieval']['prepared_dir'])
        if Path(gold_path).resolve()!=(prepared/'gold/gold.jsonl').resolve():
            raise ValueError('protected scorer requires frozen prepared gold source')
        manifest=json.loads((prepared/'manifest.json').read_text())
        if file_hash(gold_path)!=manifest['files']['gold/gold.jsonl']['sha256']:
            raise ValueError('prepared gold source checksum changed')
    # Gold is opened only after every prediction, attempt and receipt has closed.
    for row in read_jsonl(Path(gold_path)):
        if row['task_id'] not in assigned: continue
        row['supporting_facts']=[tuple(v) for v in row['supporting_facts']]
        gold=GoldRecord(**row);validate_record(gold)
        if gold.task_id in records: raise ValueError('duplicate assigned gold task')
        records[gold.task_id]=gold
    if set(records)!=assigned: raise ValueError('assigned gold records incomplete')
    documents=DocumentStore(Path(documents_path) if documents_path else root/'selected-documents.jsonl')
    expected_documents={d for task in protocol['sample']['tasks'] for d in task['candidate_ids']}
    if set(documents.offsets)!=expected_documents: raise ValueError('scorer requires exact selected documents')
    started=time.perf_counter()
    scores=[Scorer().score(p,records[p.task_id],documents,run_dir=root,accounting_context=context) for p in predictions]
    context.verify_unchanged()
    def publish_jsonl(path, rows):
        import os
        import tempfile
        payload=b''.join(canonical_bytes(r)+b'\n' for r in rows)
        if path.exists():
            if path.read_bytes()!=payload: raise ValueError('immutable scoring output differs')
            return
        with tempfile.NamedTemporaryFile(dir=root,prefix='score-staging-',delete=False) as stream:
            temporary=Path(stream.name);stream.write(payload);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    publish_jsonl(root/'scores.gold.jsonl',[records[i] for i in protocol['sample']['task_ids']])
    publish_jsonl(root/'scores.jsonl',scores)
    immutable_json(root/'job-evidence.json',job_evidence(protocol,root,predictions,scores))
    immutable_json(closure,{'kind':'protected_complete_schedule_scorer','protocol_hash':protocol['protocol_hash'],
        'record_count':len(scores),'assigned_unique_tasks':len(assigned),'paid_receipt_coverage':context.receipt_coverage,
        'scorer_source_sha256':file_hash(Path(__file__)),'scoring_seconds':time.perf_counter()-started,
        'hashes':{name:file_hash(root/name) for name in ('scores.jsonl','scores.gold.jsonl','job-evidence.json',
                    'predictions.closed.json','protected-run.closed.json')}})
    return scores

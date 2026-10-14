"""Gold-enabled scoring stage, isolated from serving imports."""

from collections import Counter
import re
import string
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
    def score(self, prediction: Prediction, gold: GoldRecord, documents: DocumentStore) -> ScoredTask:
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
        # Cost-ledger reconstruction is a later runner task. Here these fields
        # carry the prediction's supplied diagnostic interval only.
        result = ScoredTask(prediction.run_id, prediction.task_id, prediction.policy_id,
                            prediction.job_id, prediction.repetition_id, answer['em'], support['em'],
                            answer['em'] * support['em'] if valid else 0,
                            answer['f1'], support['f1'], joint_f1(answer, support) if valid else 0.,
                            prediction.elapsed_seconds, prediction.elapsed_seconds)
        validate_record(result)
        return result


def main(args) -> int:
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
    # All prediction payloads have been read and closed before gold is opened.
    gold_records = {}
    for row in read_jsonl(Path(args.gold)):
        row['supporting_facts'] = [tuple(pair) for pair in row['supporting_facts']]
        gold = GoldRecord(**row)
        validate_record(gold)
        if gold.task_id in gold_records:
            raise ValueError('duplicate gold task ID')
        gold_records[gold.task_id] = gold
    documents = DocumentStore(Path(args.documents))
    output = Path(args.output)
    if output.exists():
        raise ValueError('score output already exists')
    scores = [Scorer().score(prediction, gold_records[prediction.task_id], documents) for prediction in predictions]
    for score in scores:
        append_jsonl(output, score)
    print(json.dumps({'assigned_predictions': len(scores), 'joint_successes': sum(score.joint_em for score in scores)}))
    return 0

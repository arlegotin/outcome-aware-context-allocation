"""Private v5 offline evaluator. Invoke with PYTHONPATH=<closed-root>/source/src.

The exact frozen acquisition and actual-Scorer closure are verified before any
Gold read. Output must be fresh and private; only public-summary.json contains
publication-safe aggregates. No acquisition, retry, replay, or native inference
is performed here. Read-only source/run inventories are checked again at exit.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True


def _paired_rows(root, records, scores, tasks, fit_ids, holdout_ids):
    from outcome_poc.data_runtime import DocumentStore
    from outcome_poc.features import build_features, validate_ranking
    from outcome_poc.schemas import PairedActionRow, RankedDocument
    from outcome_poc.storage import read_jsonl
    from outcome_poc.train import FEATURE_NAMES, feature_matrix
    root = Path(root)
    ids = list(fit_ids) + list(holdout_ids)
    if len(set(ids)) != len(ids) or set(tasks) != set(ids):
        raise ValueError('exact disjoint v5 task membership required')
    by_job = {s['job_id']:s for s in scores}
    expected = {job['job_id'] for job,_,_ in records}
    if len(expected) != len(records) or len(by_job) != len(scores) or set(by_job) != expected or len(records) != 2*len(ids):
        raise ValueError('complete unique paired score roster required')
    documents = DocumentStore(root/'documents.jsonl')
    cells = {}
    for job,payload,_ in records:
        task_id, k = job['task_id'], job['budget']
        if (task_id not in tasks or k not in (2,10) or job['arm'] != str(k) or
                job['stage'] != ('fit' if task_id in set(fit_ids) else 'headroom') or
                tasks[task_id]['split'] != 'fit_extension' or payload.get('actual_allocation_runner') is not True):
            raise ValueError('v5 paired action/split/stage provenance mismatch')
        if (task_id,k) in cells:
            raise ValueError('duplicate paired action cell')
        score = by_job[job['job_id']]
        boundary = json.loads((root/'stages'/job['group']/'requests'/f'{job["job_id"]}.json').read_text())
        if ((score['task_id'],score['arm'],score['status']) != (task_id,str(k),payload['result']['status']) or
                score['seconds'] != boundary['seconds']):
            raise ValueError('scored action identity/status/complete cost mismatch')
        ranking = [RankedDocument(**r) for r in payload['ranking']]
        validate_ranking(ranking)
        if len(ranking) != 10 or {r.doc_id for r in ranking} != set(tasks[task_id]['candidate_ids']):
            raise ValueError('complete original candidate packet required')
        for ranked in ranking:
            doc = documents.get(ranked.doc_id)
            if (ranked.title,ranked.character_count,ranked.sentence_count) != (
                    doc.title,len(doc.title)+doc.character_count,len(doc.sentences)):
                raise ValueError('ranking/document observable metadata mismatch')
        inner = list(read_jsonl(root/'jobs'/job['job_id']/'allocation/predictions.jsonl'))
        if len(inner) != 1:
            raise ValueError('one actual inner allocation prediction required')
        prediction = inner[0]
        if ((prediction['job_id'],prediction['task_id'],prediction['status']) != (job['job_id'],task_id,score['status']) or
                prediction['evidence_ids'] != payload['evidence_ids'] or
                payload['evidence_ids'] != [r.doc_id for r in ranking[:k]] or not prediction['event_ids']):
            raise ValueError('actual inner prediction/event/evidence provenance mismatch')
        cells[task_id,k] = (job,payload,score,prediction,ranking)
    rows = []
    for task_id in ids:
        if (task_id,2) not in cells or (task_id,10) not in cells:
            raise ValueError('missing paired endpoint')
        small,full = cells[task_id,2],cells[task_id,10]
        if small[4] != full[4]:
            raise ValueError('paired observable ranking changed')
        question, ranked = tasks[task_id]['question'],small[4]
        rows.append(PairedActionRow(task_id,question,ranked,
            dict(zip(FEATURE_NAMES,map(float,build_features(question,ranked)))),small[0]['job_id'],full[0]['job_id'],
            small[2]['joint_em'],full[2]['joint_em'],small[2]['answer_em'],full[2]['answer_em'],
            small[3]['event_ids'],full[3]['event_ids'],small[2]['seconds'],full[2]['seconds'],
            small[2]['status'],full[2]['status']))
    feature_matrix(rows)
    return rows


def analyze(root, output):
    # Imports intentionally happen after command-line parsing and bytecode denial.
    import outcome_poc
    from outcome_poc.reader_recovery.scoring import closed_records
    from outcome_poc.reader_recovery.study import read,identity,verify_files
    from outcome_poc.reader_recovery.learning_study_v5 import is_learning
    from outcome_poc.reader_probe.study import inventory
    from outcome_poc.storage import atomic_json,content_hash,read_jsonl
    root = Path(root).resolve(strict=True)
    output = Path(output).resolve()
    if not Path(outcome_poc.__file__).resolve().is_relative_to(root/'source/src'):
        raise ValueError('load exact closed v5 frozen source using PYTHONPATH=<root>/source/src')
    metadata = read(root/'plan.json')
    retained = {root,Path(__file__).resolve().parents[1],Path(metadata['config']['historical_checkout']).resolve(),
                *(Path(p).resolve() for p in metadata['denied_paths'])}
    if any(p.is_relative_to(output) or output.is_relative_to(p) for p in retained):
        raise ValueError('private output overlaps retained input roots')
    if output.exists():
        raise ValueError('fresh private evaluator output required')
    before = inventory(root)
    # No Gold or paired outcomes have been opened before complete closure checks.
    plan,records = closed_records(root)
    config = plan['config']
    if (not is_learning(config) or config['purpose'] != 'routing-signal' or config['seed'] != 20261018
            or (config['fit_n'],config['holdout_n']) != (512,256)):
        raise ValueError('exact completed prespecified v5 research study required')
    closure = read(root/'scores/closed.json')
    if (closure['plan_hash'] != plan['plan_hash'] or closure['assigned_jobs'] != len(records) or
            closure['scorer_source'] != identity(root/'source/src/outcome_poc/reader_recovery/scoring.py') or
            closure['prediction_closures'] != {'natural':identity(root/'stages/natural/closed.json')}):
        raise ValueError('actual-Scorer closure does not match complete frozen acquisition')
    verify_files({str(root/'scores'/name):expected for name,expected in closure['files'].items()})
    if set(closure['files']) != {'scores.jsonl','summary.json'}:
        raise ValueError('exact scorer output closure required')
    scores = list(read_jsonl(root/'scores/scores.jsonl'))
    cohorts = read(root/'cohorts.json')
    fit_ids,holdout_ids = cohorts['fit'],cohorts['learning_holdout']
    task_rows = list(read_jsonl(root/'tasks.jsonl'))
    tasks = {t['task_id']:t for t in task_rows}
    if len(tasks) != len(task_rows):
        raise ValueError('duplicate task records')
    rows = _paired_rows(root,records,scores,tasks,fit_ids,holdout_ids)
    gold_path = Path(plan['gold_input']['path'])
    if identity(gold_path) != plan['gold_input']['identity']:
        raise ValueError('Gold source identity changed after closure')
    from outcome_poc.schemas import GoldRecord,validate_record
    gold,fit_set = {},set(fit_ids)
    for item in read_jsonl(gold_path):
        if item['task_id'] not in fit_set:
            continue
        if item['task_id'] in gold:
            raise ValueError('duplicate fit Gold')
        record = GoldRecord(item['task_id'],item['answer'],[tuple(p) for p in item['supporting_facts']])
        validate_record(record)
        gold[record.task_id] = record
    if set(gold) != fit_set:
        raise ValueError('incomplete fit-only Gold projection')
    from outcome_poc.heldout import evaluate
    summary = evaluate(rows,gold,fit_ids,holdout_ids,output)
    # The additional offline imports must also match the frozen source seal.
    closed_records(root)
    if inventory(root) != before:
        raise ValueError('offline evaluator modified retained input evidence')
    atomic_json(output/'private/acquisition-provenance.json', {
        'plan_hash':plan['plan_hash'],'source_snapshot_hash':plan['source_snapshot_hash'],
        'input_inventory_hash':content_hash(before),'retained_inputs_unchanged':True,
        'identities':{name:identity(root/name) for name in ('plan.json','cohorts.json','schedule.json',
            'scores/scores.jsonl','scores/closed.json','stages/natural/closed.json','native-parent-closure.json')},
        'Gold_source_identity':plan['gold_input']['identity'],'Gold_projection_scope':'exact fit IDs only',
        'tool_identity':identity(Path(__file__)), 'paired_rows_hash':content_hash([asdict(r) for r in rows])})
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.root,args.output),allow_nan=False))


if __name__ == '__main__':
    main()

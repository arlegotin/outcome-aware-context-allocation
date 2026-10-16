"""NEW read-only, fresh-process/fresh-output recovery rescore.

Run with PYTHONPATH=<retained-root>/source/src and the pinned interpreter.
No historical score stage is invoked and no historical attempt log is appended.
Only aggregate metrics/identities may be published; output rows remain private.
"""
import argparse
from dataclasses import asdict
import math
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode=True


def audit(root, output):
    root,output=Path(root).resolve(strict=True),Path(output).resolve()
    source=Path(__file__).resolve().parents[1]
    metadata=json.loads((root/'plan.json').read_bytes())
    retained_roots={root,source,Path(metadata['config']['historical_checkout']).resolve(),
                    *(Path(p).resolve() for p in metadata['denied_paths'])}
    retained_roots.add(Path(metadata['gold_input']['path']).resolve().parent.parent)
    for path in (source/'experiments').glob('*/evidence/retention.json'):
        record=json.loads(path.read_bytes())
        retained_roots.update(Path(p).resolve() for p in record['source_roots'])
        archive=Path(record['private_archive_path']).resolve();retained_roots.add(archive)
        if archive.parent.name=='runs' and archive.parent.parent.name=='artifacts':
            retained_roots.add(archive.parent.parent.parent)
    for retained in retained_roots:
        if output.is_relative_to(retained) or retained.is_relative_to(output):
            raise ValueError('fresh audit output overlaps retained source/evidence')
    output.mkdir(parents=True,exist_ok=False)
    from outcome_poc.reader_recovery.scoring import closed_records
    from outcome_poc.scoring import Scorer
    from outcome_poc.data_runtime import DocumentStore
    from outcome_poc.schemas import GoldRecord,Prediction
    from outcome_poc.followup.study import read,identity,publish
    from outcome_poc.reader_probe.study import inventory,environment_identity
    from outcome_poc.storage import canonical_bytes,content_hash,read_jsonl

    before=inventory(root)
    plan,records=closed_records(root)  # Exact assignment, frozen source, receipts, full closure.
    gold_path=Path(plan['gold_input']['path'])
    if identity(gold_path)!=plan['gold_input']['identity']:raise ValueError('bound Gold identity changed')
    assigned={j['task_id'] for j,_,_ in records}
    gold={}
    for row in read_jsonl(gold_path):
        if row['task_id'] in assigned:
            if row['task_id'] in gold:raise ValueError('duplicate assigned Gold')
            gold[row['task_id']]=GoldRecord(row['task_id'],row['answer'],[tuple(c) for c in row['supporting_facts']])
    if set(gold)!=assigned:raise ValueError('incomplete assigned Gold')
    existing=list(read_jsonl(root/'scores/scores.jsonl'))
    previous={r['job_id']:r for r in existing}
    if len(previous)!=len(existing) or set(previous)!={j['job_id'] for j,_,_ in records}:
        raise ValueError('retained score assignment mismatch')
    docs=DocumentStore(root/'documents.jsonl');asset=read(root/'assets.json')['assets']['reader']
    recomputed=[]
    for job,payload,receipt in records:
        result=payload['result'];boundary=read(root/'stages'/job['group']/'requests'/f"{job['job_id']}.json")
        prediction=Prediction(plan['config']['protocol_id'],job['task_id'],job['arm'],plan['plan_hash'],job['job_id'],1,0,
            payload['evidence_ids'],result['raw_output'],result['answer'],[tuple(c) for c in result['citations']],result['status'],
            asset['revision'],payload['prompt_hash'] or 'unavailable','greedy',boundary['seconds'],
            result['prompt_tokens'],result['generated_tokens'],payload['calls'],['continuous enclosing receipt'])
        score=Scorer().score(prediction,gold[job['task_id']],docs)
        measured={k:v for k,v in asdict(score).items() if k!='total_experiment_seconds'}
        membership=all(d in payload['view'] and i in payload['view'][d] for d,i in prediction.citations)
        if not membership:measured['joint_em'],measured['joint_f1']=0,0.
        if any(previous[job['job_id']].get(k)!=v for k,v in measured.items()):
            raise ValueError('fresh actual Scorer differs from retained metrics')
        for k,v in {'seconds':boundary['seconds'],'calls':payload['calls'],'status':result['status'],
                    'prompt_tokens':result['prompt_tokens'],'generated_tokens':result['generated_tokens'],
                    'evidence_membership_valid':membership}.items():
            if previous[job['job_id']].get(k)!=v:raise ValueError('retained cost/status/token/membership mismatch')
        recomputed.append({**measured,'arm':job['arm'],'seconds':boundary['seconds'],'status':result['status']})
    path=output/'scores.jsonl'
    with path.open('xb') as stream:
        stream.write(b''.join(canonical_bytes(r)+b'\n' for r in recomputed))
        stream.flush()
        os.fsync(stream.fileno())
    arms={}
    retained_summary=read(root/'scores/summary.json')['arms']
    for arm in sorted({r['arm'] for r in recomputed}):
        values=[r for r in recomputed if r['arm']==arm]
        n=len(values);successes=sum(r['joint_em'] for r in values);answers=sum(r['answer_em'] for r in values)
        total=math.fsum(r['seconds'] for r in values)
        arms[arm]={'n':n,'S':successes,'E':answers,'total_T':total,'mean_T':total/n,'Q':successes/n,
                   'R':total/successes if successes else None}
        expected=retained_summary[arm]
        if (successes!=expected['strict_successes'] or answers!=expected['answer_successes'] or
                not math.isclose(total,expected['total_T'],rel_tol=1e-13,abs_tol=1e-12)):
            raise ValueError('independent aggregate sums differ')
    after=inventory(root)
    if before!=after:raise ValueError('retained inputs changed during read-only audit')
    report={'format_version':1,'root':str(root),'plan_hash':plan['plan_hash'],'source_commit':plan['source_commit'],
            'frozen_source_inventory_hash':content_hash(inventory(root/'source')),
            'input_inventory_hash':content_hash(before),'retained_inputs_unchanged':True,
            'environment':environment_identity(),'tool':identity(Path(__file__)),
            'retained_scores':identity(root/'scores/scores.jsonl'),'recomputed_scores':identity(path),
            'assigned_jobs':len(records),'assigned_questions':len(assigned),'arms':arms,
            'interpretation':'historical benchmark reproduction only; no new inference, admission or efficiency claim'}
    if plan['config']['protocol_id']=='reader-evidence-first-v1':
        from outcome_poc.reader_recovery.analysis import validation_admission
        report['reader_validation']=validation_admission(recomputed,read(root/'cohorts.json')['eligibility_count'])
    publish(output/'audit.json',report)
    return {k:report[k] for k in ('plan_hash','assigned_jobs','assigned_questions','arms','retained_inputs_unchanged')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(audit(args.root,args.output),allow_nan=False))


if __name__=='__main__':main()

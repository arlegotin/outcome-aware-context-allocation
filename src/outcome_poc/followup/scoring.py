"""Privileged, complete-stage-only official-equivalent scoring."""
from pathlib import Path
from ..data_runtime import DocumentStore
from ..schemas import GoldRecord, validate_record
from ..scoring import score_answer, score_support, joint_f1, EVALUATOR_PROVENANCE
from ..storage import read_jsonl, content_hash, canonical_bytes, append_jsonl
from .study import identity, read, publish, verify_files
from .runtime import validate_closed_stage
from .clock import continuous_ns
from .analysis import summarize


def _score_stage(root, stage):
    root=Path(root).resolve()
    # Close and validate ALL assigned predictions before opening any Gold.
    plan, records=validate_closed_stage(root,stage)
    output=root/'scores'/stage
    output.mkdir(parents=True,exist_ok=True)
    marker=output/'closed.json'
    if marker.exists():
        seal=read(marker)
        if seal['plan_hash']!=plan['plan_hash'] or seal['prediction_closure']!=identity(root/'stages'/stage/'closed.json'):
            raise ValueError('scorer closure binding mismatch')
        verify_files({str(output/n):v for n,v in seal['files'].items()})
    assigned={j['task_id'] for j,_,_ in records}
    gold={}
    start=continuous_ns()
    for row in read_jsonl(Path(plan['gold_input']['path'])):
        if row['task_id'] not in assigned:continue
        record=GoldRecord(row['task_id'],row['answer'],[tuple(p) for p in row['supporting_facts']])
        validate_record(record)
        if record.task_id in gold:raise ValueError('duplicate assigned Gold')
        gold[record.task_id]=record
    if set(gold)!=assigned:raise ValueError('assigned Gold incomplete')
    docs=DocumentStore(root/'documents.jsonl')
    scores=[]
    for job,payload,receipt in records:
        result=payload['result']; reference=gold[job['task_id']]
        answer=score_answer(result['answer'] or '',reference.answer)
        support=set();valid=result['status']=='ok' and bool((result['answer'] or '').strip())
        for doc_id,index in result['citations']:
            doc=docs.get(doc_id)
            if doc_id not in payload['evidence_ids'] or type(index) is not int or not 0<=index<len(doc.sentences):
                valid=False
            else:support.add((doc.title,index))
        support_score=score_support(support,set(reference.supporting_facts))
        scores.append({'job_id':job['job_id'],'task_id':job['task_id'],'arm':job['arm'],
           'repetition':job['repetition'],'status':result['status'],
           'answer_em':answer['em'],'answer_f1':answer['f1'],'support_em':support_score['em'],
           'support_f1':support_score['f1'],'joint_em':answer['em']*support_score['em'] if valid else 0,
           'joint_f1':joint_f1(answer,support_score) if valid else 0.,
           'seconds':receipt['seconds'],'active_seconds':receipt['active_seconds'],
           'drift_seconds':receipt['drift_seconds'],'prompt_tokens':result['prompt_tokens'],
           'generated_tokens':result['generated_tokens'],'calls':payload['calls'],
           'reference_support_documents_present':{title for title,_ in reference.supporting_facts} <= {docs.get(d).title for d in payload['evidence_ids']},
           'empty':not bool(result['raw_output'].strip()),
           'truncated':result['status']=='budget_exhausted' or result['stop_reason'] in {'length','max_tokens'}})
    summary=summarize(scores,repeated=stage=='calibration')
    summary.update(stage=stage,assigned_observations=len(records),assigned_unique_questions=len(assigned),
       reserved_questions=32 if stage=='calibration' else len(assigned),plan_hash=plan['plan_hash'],
       evaluator=EVALUATOR_PROVENANCE)
    payload=b''.join(canonical_bytes(r)+b'\n' for r in scores)
    path=output/'scores.jsonl'
    if path.exists() and path.read_bytes()!=payload:raise ValueError('immutable score output differs')
    if not path.exists():
        import os,tempfile
        with tempfile.NamedTemporaryFile(dir=output,delete=False) as stream:
            staging=Path(stream.name);stream.write(payload);stream.flush();os.fsync(stream.fileno())
        os.replace(staging,path)
    publish(output/'summary.json',summary)
    validate_closed_stage(root,stage)
    if marker.exists():
        return summary
    publish(marker,{'plan_hash':plan['plan_hash'],'stage':stage,'assigned_observations':len(scores),
        'prediction_closure':identity(root/'stages'/stage/'closed.json'),
        'files':{n:identity(output/n) for n in ('scores.jsonl','summary.json')},
        'start_ns':start,'stop_ns':continuous_ns(),'clock_domain':'mach_continuous_time',
        'scorer_source':identity(Path(__file__))})
    return summary


def score_stage(root,stage):
    root=Path(root).resolve()
    # Refuse incomplete or corrupt stages before Gold and before creating scoring output.
    validate_closed_stage(root,stage,privileged=False)
    start=continuous_ns();error=None
    try:
        return _score_stage(root,stage)
    except BaseException as caught:
        error=caught
        raise
    finally:
        append_jsonl(root/'scoring-attempts.jsonl',{'stage':stage,'start_ns':start,'stop_ns':continuous_ns(),
            'status':'failed' if error else 'ok','error':str(error) if error else None,
            'clock_domain':'mach_continuous_time','kind':'separate scoring physical envelope'})

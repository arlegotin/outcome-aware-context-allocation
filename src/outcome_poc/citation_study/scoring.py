"""Privileged official scoring. Never imported by serving coordinator or worker."""
from pathlib import Path
from ..data_runtime import DocumentStore
from ..schemas import GoldRecord,validate_record
from ..scoring import score_answer,score_support,joint_f1,EVALUATOR_PROVENANCE
from ..storage import read_jsonl,canonical_bytes,append_jsonl
from .study import read,publish,identity,verify_files
from .runtime import validate_closed_stage,FATAL,session_accounting,continuous_ns
from .analysis import summarize


def score_stage(root,stage):
    root=Path(root).resolve()
    start=continuous_ns();error=None
    try:
        plan,records=validate_closed_stage(root,stage) # Timed and retained, always before Gold.
        assigned={j['task_id'] for j,_,_ in records};gold={}
        for row in read_jsonl(Path(plan['gold_input']['path'])):
            if row['task_id'] not in assigned:continue
            record=GoldRecord(row['task_id'],row['answer'],[tuple(p) for p in row['supporting_facts']]);validate_record(record)
            if record.task_id in gold:raise ValueError('duplicate assigned Gold')
            gold[record.task_id]=record
        if set(gold)!=assigned:raise ValueError('assigned Gold incomplete')
        docs=DocumentStore(root/'inputs'/stage/'documents.jsonl');rows=[]
        for job,payload,receipt in records:
            result=payload['result'];reference=gold[job['task_id']]
            answer=score_answer(result['answer'] or '',reference.answer)
            support=set();valid=result['status']=='ok' and bool((result['answer'] or '').strip())
            for doc_id,index in result['citations']:
                doc=docs.get(doc_id)
                if doc_id not in payload['evidence_ids'] or type(index) is not int or not 0<=index<len(doc.sentences):valid=False
                else:support.add((doc.title,index))
            sp=score_support(support,set(reference.supporting_facts))
            rows.append({**{k:job[k] for k in ('job_id','task_id','arm','prompt_condition','repetition','ordinal')},
                'status':result['status'],'answer_em':answer['em'],'answer_f1':answer['f1'],
                'support_em':sp['em'],'support_f1':sp['f1'],'support_precision':sp['precision'],'support_recall':sp['recall'],
                'joint_em':answer['em']*sp['em'] if valid else 0,'joint_f1':joint_f1(answer,sp) if valid else 0.,
                **{k:receipt[k] for k in ('seconds','active_seconds','drift_seconds')},
                **{k:result[k] for k in ('prompt_tokens','generated_tokens')},'calls':payload['calls'],
                'empty':not bool(result['raw_output'].strip()),'truncated':result['status']=='budget_exhausted' or result['stop_reason'] in {'length','max_tokens'}})
        cohorts=read(root/'cohorts.json');N=cohorts['comparison_population'] if stage=='comparison' else cohorts['eligibility']['count']
        summary=summarize(rows,stage,N);summary.update(plan_hash=plan['plan_hash'],evaluator=EVALUATOR_PROVENANCE)
        output=root/'scores'/stage;output.mkdir(parents=True,exist_ok=True)
        marker=output/'closed.json'
        if marker.exists():validate_score_seal(root,stage,plan,len(records))
        data=b''.join(canonical_bytes(r)+b'\n' for r in rows);path=output/'scores.jsonl'
        if path.exists():
            if path.read_bytes()!=data:raise ValueError('immutable score output differs')
        else:
            with path.open('xb') as stream:stream.write(data)
        publish(output/'summary.json',summary)
        validate_closed_stage(root,stage)
        if not marker.exists():publish(marker,{'plan_hash':plan['plan_hash'],'stage':stage,'assigned_observations':len(rows),
            'prediction_closure':identity(root/'stages'/stage/'closed.json'),
            'files':{n:identity(output/n) for n in ('scores.jsonl','summary.json')},'scorer_source':identity(Path(__file__))})
        return summary
    except BaseException as caught:error=caught;raise
    finally:append_jsonl(root/'scoring-attempts.jsonl',{'stage':stage,'start_ns':start,'stop_ns':continuous_ns(),
        'status':'failed' if error else 'ok','error':str(error) if error else None})


def validate_score_seal(root,stage,plan,count):
    output=root/'scores'/stage;seal=read(output/'closed.json')
    if (seal['plan_hash']!=plan['plan_hash'] or seal['stage']!=stage or seal['assigned_observations']!=count or
        seal['prediction_closure']!=identity(root/'stages'/stage/'closed.json') or
        set(seal['files'])!={'scores.jsonl','summary.json'} or seal['scorer_source']!=identity(Path(__file__))):
        raise ValueError('score closure binding mismatch')
    verify_files({str(output/n):v for n,v in seal['files'].items()})
    return seal


def admit(root):
    root=Path(root).resolve();plan,records=validate_closed_stage(root,'diagnosis')
    validate_score_seal(root,'diagnosis',plan,len(records))
    summary=read(root/'scores/diagnosis/summary.json');cells=summary['cells']
    healthy=execution_health(root,plan,records)
    joint=cells['chain/10']['counts']['joint_em']>cells['baseline/10']['counts']['joint_em']
    guards=all(cells['chain/'+a]['counts']['answer_em']>=cells['baseline/'+a]['counts']['answer_em'] for a in ('2','10'))
    decision={'plan_hash':plan['plan_hash'],'decision':'admit' if healthy and joint and guards else 'defer',
        'healthy':healthy,'strict_natural10_joint_improvement':joint,'nonlower_natural_answers':guards,
        'diagnosis_scores':identity(root/'scores/diagnosis/closed.json'),'diagnosis_summary':identity(root/'scores/diagnosis/summary.json'),
        'diagnosis_predictions':identity(root/'stages/diagnosis/closed.json'),'assigned_observations':len(records)}
    publish(root/'comparison-decision.json',decision)
    if decision['decision']=='admit':publish(root/'comparison-admission.json',{'kind':'citation-comparison-admission-v1',
        'plan_hash':plan['plan_hash'],'boot_id':plan['freeze']['boot_id'],'decision':'admit',
        'decision_identity':identity(root/'comparison-decision.json'),
        'diagnosis_prediction_closure':identity(root/'stages/diagnosis/closed.json'),
        'scorer_closure_identity':identity(root/'scores/diagnosis/closed.json')})
    return decision


def execution_health(root,plan,records):
    """Only validated native session/probe/resource receipts can admit comparison."""
    from .runtime import denial_paths,sandbox_profile,worker_identity_unknown
    root=Path(root);directory=root/'stages/diagnosis'
    sessions=session_accounting(root,'diagnosis',plan,require_closed=True)
    setup=list(read_jsonl(directory/'setup.jsonl'))
    starts=[read(p) for p in directory.glob('session-start-*.json')]
    healthy=(len(records)==384 and all(p['calls']==1 and p['result']['status'] not in FATAL and
        not p.get('cleanup_error') and not p.get('synchronization_error') for _,p,_ in records)
        and sessions['status']=='complete' and bool(starts))
    probes=[]
    for path in directory.glob('launch-*/denial-probe.json'):
        probe=read(path);binding_path=path.parent/'binding.json';binding=read(binding_path)
        expected={'plan_hash':plan['plan_hash'],'stage':'diagnosis','boot_id':plan['freeze']['boot_id'],
            'profile':identity(path.parent/'native.sb'),'denial_paths':denial_paths(plan,'diagnosis')}
        if (binding!=expected or probe.get('binding')!=identity(binding_path) or probe.get('profile')!=binding['profile'] or
            probe.get('network_denied') is not True or probe.get('file_denials')!=len(binding['denial_paths']) or
            probe.get('boot_id')!=plan['freeze']['boot_id'] or (path.parent/'native.sb').read_text()!=sandbox_profile(root,
                plan['freeze']['denied_paths']+plan['freeze']['comparison_denied_paths'])):
            return False
        probes.append(probe)
    for state in starts:
        if worker_identity_unknown(directory,state,plan):return False
        if not any(p.get('pid')==state['parent_pid'] for p in probes):return False
        for kind in ('memory_gate','post_warmup_memory_gate'):
            if not any(r.get('session')==state['session'] and r.get('kind')==kind and r.get('passed') is True for r in setup):return False
    return healthy

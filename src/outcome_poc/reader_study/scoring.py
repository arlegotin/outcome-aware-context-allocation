"""Privileged deterministic reader-factor scoring; never imported by serving."""
from collections import Counter
from pathlib import Path
import numpy as np
from ..data_runtime import DocumentStore
from ..schemas import GoldRecord, validate_record
from ..scoring import score_answer, score_support, joint_f1, EVALUATOR_PROVENANCE
from ..statistics import paired_quality_bounds
from ..storage import read_jsonl, canonical_bytes, content_hash, append_jsonl, atomic_json
from ..followup.study import verify_files
from ..followup.runtime import stage_lock
from .study import read, publish, identity, verify, leaf_root, READERS, STAGES, ADMISSION
from .runtime import (validate_closed_stage, session_accounting, continuous_ns, completion,
    denial_paths, sandbox_profile, FATAL, SLOT)

METRICS=('joint_em','answer_em','support_em','joint_f1','answer_f1','support_f1','support_precision','support_recall')


def summarize(rows,stage,population_N):
    arms=('2','10','support-documents') if stage=='development' else ('2','10')
    if stage not in STAGES or not rows: raise ValueError('empty/unknown scientific stage')
    by={}
    for row in rows:
        key=(row['task_id'],row['reader_id'],row['arm'])
        if key in by or row['repetition']!=0 or row['scientific_stage']!=stage: raise ValueError('duplicate/unassigned factor')
        by[key]=row
    ids=sorted({r['task_id'] for r in rows})
    if set(by)!={(i,r,a) for i in ids for r in READERS for a in arms}: raise ValueError('incomplete paired observations')
    cells={};paired={};oracle={}
    for reader in READERS:
        for arm in arms:
            group=[by[i,reader,arm] for i in ids];total=sum(r['seconds'] for r in group);successes=sum(r['joint_em'] for r in group)
            cells[reader+'/'+arm]={'n':len(group),'counts':{k:sum(r[k] for r in group) for k in METRICS[:3]},
                'means':{k:float(np.mean([r[k] for r in group])) for k in METRICS},
                'total_seconds':total,'mean_seconds':total/len(group),'p95_seconds':float(np.quantile([r['seconds'] for r in group],.95)),
                'seconds_per_strict_success':total/successes if successes else None,
                'ratio_reason':None if successes else 'zero strict successes; all assigned work retained',
                'calls':sum(r['calls'] for r in group),'prompt_tokens':sum(r['prompt_tokens'] for r in group),
                'generated_tokens':sum(r['generated_tokens'] for r in group),
                'statuses':dict(sorted(Counter(r['status'] for r in group).items())),
                'failures':sum(r['status']!='ok' for r in group),'empty':sum(r['empty'] for r in group),
                'truncated':sum(r['truncated'] for r in group),'abstentions':sum(r['status']=='abstain' for r in group)}
        two=np.array([by[i,reader,'2']['joint_em'] for i in ids]);ten=np.array([by[i,reader,'10']['joint_em'] for i in ids])
        oracle[reader]={'n':len(ids),'both_success':int(((two==1)&(ten==1)).sum()),
            'two_only':int(((two==1)&(ten==0)).sum()),'ten_only':int(((two==0)&(ten==1)).sum()),
            'neither_success':int(((two==0)&(ten==0)).sum()),'union_success':int(((two==1)|(ten==1)).sum()),
            'interpretation':'clairvoyant union; descriptive and unavailable to deployment'}
    for arm in arms:
        pair={}
        for metric in METRICS[:3]:
            old=np.array([by[i,'qwen4b-instruct',arm][metric] for i in ids])
            new=np.array([by[i,'qwen14b-nonthinking',arm][metric] for i in ids])
            bounds=paired_quality_bounds(new,old,population_N,.00625 if metric=='answer_em' and arm in ('2','10') else .0125)
            bounds.pop('preserved',None)
            bounds.update(both_success=int(((new==1)&(old==1)).sum()),neither_success=int(((new==0)&(old==0)).sum()),
                difference_percentage_points=100*bounds['difference'],ci_percentage_points=[100*x for x in bounds['ci']],
                interpretation='confirmation finite-population contrast' if stage=='confirmation' else 'explanatory only; reused development questions')
            pair[metric]=bounds
        paired[arm]=pair
    return {'scientific_stage':stage,'population_N':population_N,'assigned_observations':len(rows),
        'assigned_unique_questions':len(ids),'cells':cells,'paired':paired,'oracle':oracle,
        'primary':'natural10 joint_em qwen14b-nonthinking minus qwen4b-instruct' if stage=='confirmation' else None,
        'timing':{'repetitions':1,'max_absolute_drift_seconds':max(abs(r['drift_seconds']) for r in rows),
            'interpretation':'descriptive only; sequential model blocks and cold/shape/swap effects; no efficiency interval'},
        'interpretation':'Reader-profile contrast only; no allocation, quality preservation, provider or business inference.'}


def scorer_identity():
    import outcome_poc.scoring as metrics
    import outcome_poc.statistics as statistics
    return {module.__name__:identity(Path(module.__file__)) for module in (metrics,statistics)} | {'reader_study.scoring':identity(Path(__file__))}


def _seal(root,stage,plan,count):
    output=root/'scores'/stage
    return {'plan_hash':plan['plan_hash'],'scientific_stage':stage,'assigned_observations':count,
        'prediction_closure':identity(root/'stages'/stage/'closed.json'),'gold':plan['gold_input'],
        'source_snapshot_hash':content_hash(plan['freeze']['bindings']['source_snapshot']),
        'scorer_source':scorer_identity(),'files':{n:identity(output/n) for n in ('scores.jsonl','summary.json')}}


def validate_score_seal(root,stage,plan=None):
    root=Path(root).resolve();closed=validate_closed_stage(root,stage);plan=plan or closed['plan']
    if identity(plan['gold_input']['path'])!=plan['gold_input']['identity']: raise ValueError('Gold identity changed')
    marker=root/'scores'/stage/'closed.json'
    if not marker.exists(): raise ValueError('score closure missing')
    seal=read(marker)
    if seal!=_seal(root,stage,plan,len(closed['records'])): raise ValueError('score closure binding mismatch')
    return seal


def score_stage(root,stage):
    with stage_lock(Path(root)):
        return _score_stage(root,stage)


def _score_stage(root,stage):
    root=Path(root).resolve();start=continuous_ns();error=None
    try:
        closed=validate_closed_stage(root,stage);plan=closed['plan'];records=closed['records']
        # Gold and original source are scorer-only. Serving validates its sealed snapshot.
        if identity(plan['gold_input']['path'])!=plan['gold_input']['identity']: raise ValueError('Gold identity changed')
        verify_files(plan['freeze']['source_files'])
        output=root/'scores'/stage;marker=output/'closed.json'
        if marker.exists(): validate_score_seal(root,stage,plan)
        assigned={j['task_id'] for j,p,r in records};gold={}
        for row in read_jsonl(Path(plan['gold_input']['path'])):
            if row['task_id'] not in assigned: continue
            record=GoldRecord(row['task_id'],row['answer'],[tuple(p) for p in row['supporting_facts']]);validate_record(record)
            if record.task_id in gold: raise ValueError('duplicate assigned Gold')
            gold[record.task_id]=record
        if set(gold)!=assigned: raise ValueError('assigned Gold incomplete')
        docs=DocumentStore(root/'inputs'/stage/'documents.jsonl');rows=[]
        for job,payload,receipt in records:
            result=payload['result'];reference=gold[job['task_id']]
            answer=score_answer(result['answer'] or '',reference.answer)
            support=set();truncated=result['status']=='budget_exhausted' or result['stop_reason'] in {'length','max_tokens'} or result['generated_tokens']>=256
            valid=result['status']=='ok' and bool((result['answer'] or '').strip()) and not truncated
            for doc_id,index in result['citations']:
                if doc_id not in payload['evidence_ids'] or type(index) is not int:
                    valid=False;continue
                doc=docs.get(doc_id)
                if not 0<=index<len(doc.sentences): valid=False
                else: support.add((doc.title,index))
            sp=score_support(support,set(reference.supporting_facts))
            rows.append({**{k:job[k] for k in ('job_id','task_id','arm','reader_id','scientific_stage','prompt_condition','repetition','ordinal')},
                'status':result['status'],'answer_em':answer['em'],'answer_f1':answer['f1'],
                'support_em':sp['em'],'support_f1':sp['f1'],'support_precision':sp['precision'],'support_recall':sp['recall'],
                'joint_em':answer['em']*sp['em'] if valid else 0,'joint_f1':joint_f1(answer,sp) if valid else 0.,
                **{k:receipt[k] for k in ('seconds','active_seconds','drift_seconds')},
                **{k:result[k] for k in ('prompt_tokens','generated_tokens')},'calls':payload['calls'],
                'empty':not bool(result['raw_output'].strip()),'truncated':truncated})
        N=plan['freeze']['settings']['statistics']['confirmation_population'] if stage=='confirmation' else len(assigned)
        summary=summarize(rows,stage,N);summary.update(plan_hash=plan['plan_hash'],evaluator=EVALUATOR_PROVENANCE)
        output.mkdir(parents=True,exist_ok=True);data=b''.join(canonical_bytes(r)+b'\n' for r in rows);path=output/'scores.jsonl'
        if path.exists():
            if path.read_bytes()!=data: raise ValueError('immutable score output differs')
        else:
            with path.open('xb') as stream: stream.write(data)
        publish(output/'summary.json',summary)
        validate_closed_stage(root,stage)
        publish(marker,_seal(root,stage,plan,len(rows)))
        return rows
    except BaseException as caught: error=caught;raise
    finally: append_jsonl(root/'scoring-attempts.jsonl',{'scientific_stage':stage,'start_ns':start,
        'stop_ns':continuous_ns(),'status':'failed' if error else 'ok','error':str(error) if error else None})


def execution_health(root,plan,records):
    """Allow only exact, isolated pre-paid startup failures to precede healthy work."""
    if len(records)!=96 or any(p['calls']!=1 or p['result']['status'] in FATAL or
        p.get('interrupted') or p.get('cleanup_error') or p.get('synchronization_error') or p.get('retrieval_error') for j,p,r in records): return False
    from ..followup.runtime import _worker_identity_unknown
    session_states=[]
    for reader in READERS:
        leaf=leaf_root(root,'development',reader);lp=read(leaf/'plan.json');directory=leaf/'stages'/SLOT
        if session_accounting(leaf,SLOT,lp,require_closed=True)['status']!='complete': return False
        starts=[read(p) for p in directory.glob('session-start-*.json')]
        if not starts: return False
        for state in starts:
            sid=state['session'];receipt=read(directory/f'session-accounting-{sid}.json')
            acquired=(directory/f'acquisition-{sid}.json').exists()
            attempts=[p for p in (leaf/'jobs').glob('*/started.json') if read(p).get('session')==sid]
            startup_only=(receipt['status']=='failed' and not attempts and not (directory/f'warmup-{sid}').exists())
            if (not state.get('native_execution') or receipt['stop_ns'] is None or receipt.get('cleanup_error') or
                (receipt['status']!='ok' and not startup_only) or
                _worker_identity_unknown(directory,state,lp,require_identity=acquired)): return False
            gate_path=directory/f'gates-{sid}'/'gates.jsonl'
            gates=list(read_jsonl(gate_path)) if gate_path.exists() else []
            if any(g.get('passed') is not True for g in gates): return False
            required={'before_acquisition'}
            if not startup_only:
                required|={'after_acquisition','before_warmup','after_warmup'}
                required|={boundary+'_'+p.parent.name for p in attempts for boundary in ('before','after')}
            if not required<={g['boundary'] for g in gates}: return False
            for role in (('coordinator','worker') if acquired else ('coordinator',)):
                path=directory/f'{role}-probes-{sid}.json'
                if not path.exists(): return False
                probe=read(path)
                if any(probe.get(k)!=v for k,v in {'plan_hash':plan['plan_hash'],'scientific_stage':'development',
                    'reader_id':reader,'leaf_plan_hash':lp['plan_hash'],'profile':lp['freeze']['leaf_binding'],
                    'session':sid,'network_denied':True,'snapshot_origins':True,
                    'file_denials':len(denial_paths(plan,'development',probes=True)),
                    'import_denials':plan['freeze']['denied_modules']}.items()): return False
                if role=='coordinator' and probe.get('pid')!=state['parent_pid']: return False
                if role=='worker' and not any(read(w).get('pid')==probe.get('pid') for w in directory.glob(f'session-worker-{sid}-*.json')): return False
            if not startup_only:
                expected={'reader_id':reader,'scientific_stage':'development','profile':lp['freeze']['leaf_binding'],
                    'settings':lp['freeze']['settings']['reader'],'paid':identity(directory/f'warmup-{sid}'/'paid.json')}
                if not acquired or read(directory/f'warmup-profile-{sid}.json')!=expected: return False
            session_states.append((state,receipt,startup_only))
    launches=list((root/'stages/development').glob('launch-*'))
    if not launches: return False
    covered=set()
    for directory in launches:
        launched=read(directory/'launch.json');exited=read(directory/'exit.json')
        contained=[(state,receipt,startup) for state,receipt,startup in session_states
                   if launched['start_ns']<=state['start_ns']<=receipt['stop_ns']<=exited['stop_ns']]
        if not contained or (exited['returncode']!=0 and not all(startup for _,_,startup in contained)): return False
        covered.update(state['session'] for state,_,_ in contained)
        if launched['binding']!=identity(directory/'binding.json'): return False
        if (directory/'native.sb').read_text()!=sandbox_profile(root,denial_paths(plan,'development')): return False
        if read(directory/'binding.json')!={'plan_hash':plan['plan_hash'],'scientific_stage':'development',
            'boot_id':plan['freeze']['boot_id'],'profile':identity(directory/'native.sb'),
            'denial_probes':denial_paths(plan,'development',probes=True)}: return False
    return covered=={state['session'] for state,_,_ in session_states}


def admit(root):
    with stage_lock(Path(root)):
        return _admit(root)


def _admit(root):
    root=Path(root).resolve();closed=validate_closed_stage(root,'development');plan=closed['plan']
    seal=validate_score_seal(root,'development',plan);summary=read(root/'scores/development/summary.json')
    counts={r:{a:summary['cells'][r+'/'+a]['counts'] for a in ('2','10')} for r in READERS}
    old=counts['qwen4b-instruct'];new=counts['qwen14b-nonthinking']
    healthy=execution_health(root,plan,closed['records'])
    joint=new['10']['joint_em']>old['10']['joint_em'];guards=all(new[a]['answer_em']>=old[a]['answer_em'] for a in ('2','10'))
    decision={'plan_hash':plan['plan_hash'],'rule':ADMISSION,'decision':'admit' if healthy and joint and guards else 'defer',
        'healthy':healthy,'strict_natural10_joint_improvement':joint,'nonlower_natural_answers':guards,'natural_counts':counts,
        'assigned_observations':len(closed['records']),'development_closure':identity(root/'stages/development/closed.json'),
        'score_seal_hash':content_hash(seal),'score_seal_identity':identity(root/'scores/development/closed.json')}
    publish(root/'development-score-attestation.json',seal);publish(root/'confirmation-decision.json',decision)
    if decision['decision']=='admit':
        publish(root/'confirmation-admission.json',{'kind':'reader-quality-confirmation-admission-v1',
            'plan_hash':plan['plan_hash'],'boot_id':plan['freeze']['boot_id'],'rule':ADMISSION,'decision':'admit',
            'decision_identity':identity(root/'confirmation-decision.json'),'development_closure':decision['development_closure'],
            'score_attestation':identity(root/'development-score-attestation.json')})
    return decision


def report(root):
    root=Path(root).resolve();plan=verify(root);result={'plan_hash':plan['plan_hash'],'planned_generations':608,'stages':{},
        'admission':read(root/'confirmation-decision.json') if (root/'confirmation-decision.json').exists() else None}
    def ledger(p): return list(read_jsonl(p)) if p.exists() else []
    def elapsed(rows): return sum((r['stop_ns']-r['start_ns'])/1e9 for r in rows)
    physical={'preparation_seconds':elapsed(ledger(root/'setup.jsonl')),'index_setup_seconds':sum(elapsed(ledger(root/'stages'/s/'index-setup.jsonl')) for s in STAGES),
        'scoring_seconds':elapsed(ledger(root/'scoring-attempts.jsonl')),'serving_exact_seconds':0.,'serving_lower_seconds':0.,'serving_upper_seconds':0.}
    for stage in STAGES:
        jobs=[j for j in read(root/'schedule.json') if j['scientific_stage']==stage];terminal=0;calls=0;warmups=0;unreceipted=0;sessions={};samples=[];status='reserved_unexecuted'
        for reader in READERS:
            leaf=leaf_root(root,stage,reader);lp=read(leaf/'plan.json');directory=leaf/'stages'/SLOT
            for job in [j for j in jobs if j['reader_id']==reader]:
                record=completion(leaf,lp,job)
                if record: terminal+=1
                job_dir=leaf/'jobs'/job['job_id']
                calls+=int((job_dir/'paid.json').exists())
                unreceipted+=int((job_dir/'started.json').exists() and record is None)
            if (directory/'aborted.json').exists(): status='aborted'
            warmups+=len(list(directory.glob('warmup-*/paid.json')))
            account=session_accounting(leaf,SLOT,lp);sessions[reader]=account
            for key,source in [('serving_exact_seconds','exact_seconds'),('serving_lower_seconds','lower_seconds'),('serving_upper_seconds','upper_seconds')]:
                physical[key]=physical[key]+account[source] if physical[key] is not None and account[source] is not None else None
            samples.extend(r for p in directory.glob('resources-*.jsonl') for r in ledger(p))
        summary=None
        if status!='aborted' and (terminal or any(v['sessions'] for v in sessions.values())): status='incomplete'
        if (root/'stages'/stage/'closed.json').exists():
            validate_closed_stage(root,stage);status='closed_unscored'
            if (root/'scores'/stage/'closed.json').exists():
                validate_score_seal(root,stage,plan);summary=read(root/'scores'/stage/'summary.json');status='scored'
        result['stages'][stage]={'status':status,'assigned_observations':len(jobs),'terminal_observations':terminal,
            'incomplete_observations':len(jobs)-terminal,'unreceipted_attempts':unreceipted,'assigned_calls':calls,'authored_warmup_calls':warmups,
            'session_accounting':sessions,'summary':summary,'resource_peaks':{k:max((r[k] for r in samples if r.get(k) is not None),default=None)
                for k in ('rss_parent_bytes','rss_children_bytes','peak_mlx_bytes','swap_used_bytes')}}
    base=sum(physical[k] for k in ('preparation_seconds','index_setup_seconds','scoring_seconds'))
    for name,source in [('total_exact_seconds','serving_exact_seconds'),('total_lower_seconds','serving_lower_seconds'),('total_upper_seconds','serving_upper_seconds')]:
        physical[name]=None if physical[source] is None else base+physical[source]
    physical['summing_rule']='Only disjoint preparation, index, serving sessions and scoring. Jobs, warmup, acquisition and lifecycle are nested diagnostics.'
    result['physical_costs']=physical
    result['interpretation']='One repetition; descriptive times. Both reader lineages differ. No allocation/provider/customer claim.'
    atomic_json(root/'aggregate-report.json',result);return result

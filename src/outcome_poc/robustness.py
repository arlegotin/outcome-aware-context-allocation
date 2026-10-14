"""Exploratory checks over immutable receipts; never trains or changes a score.

No benchmark input is read on import. Native transfer needs a separately reviewed,
prospective diagnostic; this module's required path is entirely offline.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import math
from pathlib import Path

from .schemas import ScoredTask, validate_record
from .storage import canonical_bytes, content_hash


def _unique(rows, key, label):
    result = {key(row):row for row in rows}
    if len(result) != len(rows):
        raise ValueError('duplicate '+label)
    return result


def _policy_id(method):
    family = method['family']
    if family == 'FIXED':
        return f'FIXED-{method["k"]}'
    if family.startswith('ADAPTIVE-k'):
        return f'ADAPTIVE-k-{"published" if family.endswith("published") else "tuned"}-B{method["buffer"]}'
    return method.get('model_name', family)


def _assignments(protocol, scores):
    from .protocol import FAMILIES
    jobs = protocol['schedule']['jobs']
    byjob = _unique(jobs, lambda j:j['job_id'], 'scheduled job')
    ids = protocol['sample']['task_ids']
    if not ids or len(ids) != len(set(ids)) or protocol['sample']['n'] != len(ids):
        raise ValueError('invalid assigned task denominator')
    if [s.job_id for s in scores] != list(byjob):
        raise ValueError('full ordered assigned schedule required')
    representatives = protocol['methods']['representatives']
    if {r['family'] for r in representatives} != FAMILIES or len(representatives) != len(FAMILIES):
        raise ValueError('incomplete frozen family roster')
    groups = {}
    for job, score in zip(jobs, scores):
        validate_record(score)
        if (score.run_id,score.task_id,score.policy_id,score.repetition_id) != (
                'confirmation',job['task_id'],_policy_id(job['method']),job['repetition_id']):
            raise ValueError('score identity differs from assigned job')
        if job['scope'] != 'primary':
            key = (job['scope'],job['method']['config_id'])
            groups.setdefault(key, []).append(job)
    expected = {('representative',m['config_id']) for m in representatives}
    expected |= {('anchor',protocol['methods']['anchor']['config_id']),
                 ('random',protocol['methods']['random']['config_id']),
                 ('oracle-source',protocol['methods']['oracle_source']['config_id'])}
    if set(groups) != expected:
        raise ValueError('assigned family scopes differ from frozen roster')
    descriptors={('representative',m['config_id']):m for m in representatives}
    for scope,key in (('anchor','anchor'),('random','random'),('oracle-source','oracle_source')):
        method=protocol['methods'][key];descriptors[scope,method['config_id']]=method
    for group,rows in groups.items():
        if len(rows) != len(ids) or {j['task_id'] for j in rows} != set(ids):
            raise ValueError('family assigned denominator incomplete')
        for j in rows:
            frozen=deepcopy(descriptors[group])
            if group[0]=='random':
                frozen['k']=10 if int(content_hash([271828,j['task_id'],'random-mixture']),16)/2**256<frozen['probability'] else 2
            if j['method']!=frozen:
                raise ValueError('assigned descriptor differs from frozen method')
    primary = [j for j in jobs if j['scope']=='primary']
    expected_primary = {(t,a,r) for t in ids for a in ('A','B')
                        for r in range(1,protocol['methods']['repetitions']+1)}
    if len(primary) != len(expected_primary) or {(j['task_id'],j['arm'],j['repetition_id']) for j in primary} != expected_primary:
        raise ValueError('primary repetition denominator incomplete')
    for j in primary:
        if j['method'] != protocol['methods']['selected'][j['arm']]:
            raise ValueError('primary method differs from frozen selection')
    return byjob, {s.job_id:s for s in scores}, groups


def _events(events):
    indexed = _unique(events, lambda e:e.event_id, 'cost event')
    for event in events:
        validate_record(event)
        if event.elapsed_seconds != (event.stop_ns-event.start_ns)/1e9:
            raise ValueError('event duration does not bind timestamps')
    return indexed


def _cells(candidate, comparator):
    names = {(0,0):'both_fail',(1,0):'candidate_only',(0,1):'comparator_only',(1,1):'both_success'}
    counts = dict.fromkeys(names.values(), 0)
    for a,b in zip(candidate, comparator):
        counts[names[a,b]] += 1
    return counts


def ablate(protocol: dict, scored_rows: list[ScoredTask], events: list) -> dict:
    """Compare only frozen representatives on their common assigned population."""
    _, scores, groups = _assignments(protocol, scored_rows)
    _events(events)
    candidate = protocol['methods']['selected']['A']
    source = groups[('representative',candidate['config_id'])]
    a = {j['task_id']:scores[j['job_id']] for j in source}
    ids = protocol['sample']['task_ids']; comparisons = []
    for (scope,config), jobs in groups.items():
        if scope=='representative' and config==candidate['config_id']:
            continue
        b = {j['task_id']:scores[j['job_id']] for j in jobs}
        comparisons.append({'scope':scope,'config_id':config,'family':jobs[0]['method']['family'],
            'assigned_tasks':len(ids),
            'joint_cells':_cells([a[t].joint_em for t in ids],[b[t].joint_em for t in ids]),
            'answer_cells':_cells([a[t].answer_em for t in ids],[b[t].answer_em for t in ids]),
            'joint_difference':sum(a[t].joint_em-b[t].joint_em for t in ids)/len(ids),
            'answer_difference':sum(a[t].answer_em-b[t].answer_em for t in ids)/len(ids),
            'candidate_mean_support_f1':sum(a[t].support_f1 for t in ids)/len(ids),
            'comparator_mean_support_f1':sum(b[t].support_f1 for t in ids)/len(ids),
            'mean_serving_difference_seconds':sum(a[t].total_serving_seconds-b[t].total_serving_seconds for t in ids)/len(ids),
            'diagnostic_only':scope in ('random','oracle-source') or jobs[0]['method']['family']=='SHUFFLED-LABEL-GBM'})
    return {'protocol_hash':protocol['protocol_hash'],'assigned_tasks':len(ids),
        'selected':deepcopy(protocol['methods']['selected']),'comparisons':comparisons,
        'selection_performed':False,'scope':'exploratory frozen attribution; no simultaneous superiority claim',
        'all_family_superiority':'not prespecified'}


def _union_seconds(intervals):
    total = 0; end = None
    for start,stop in sorted(intervals):
        total += max(0,stop-max(start,end if end is not None else start))
        end = max(stop,end if end is not None else stop)
    return total/1e9


def _close(a,b):
    if not math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8):
        raise ValueError('accounted serving/experiment cost mismatch')


def _compatible(p, q, paid_p, paid_q):
    # The whole output_parity_hash includes different policy decisions.
    fields = ('task_id','evidence_ids','raw_output','answer','citations','status',
              'model_revision','prompt_hash','decoding_hash','prompt_tokens','generated_tokens')
    if any(getattr(p,k) != getattr(q,k) for k in fields):
        return False
    if not paid_p or not paid_q:
        return False
    for key in ('request','result'):
        fields = (('model_revision','model_hash','prompt_hash','decoding_hash','role','max_context_tokens',
                   'max_new_tokens','timeout_seconds','cache_mode') if key=='request' else
                  ('raw_output','answer','citations','status','prompt_token_ids','generated_token_ids','stop_reason'))
        if any(k not in paid_p[-1][key] or k not in paid_q[-1][key] or
               canonical_bytes(paid_p[-1][key][k]) != canonical_bytes(paid_q[-1][key][k]) for k in fields):
            return False
    return True


def audit_accounting(protocol, scored_rows, events, predictions, evidence, receipts):
    """Audit exact job ownership, paid roles and source-based cost reconstruction.

    Component intervals explain enclosures. Overlap and residual overhead are
    explicit, while complete-ledger score totals remain the cost authority.
    """
    jobs, scores, groups = _assignments(protocol, scored_rows)
    indexed = _events(events)
    pred = _unique(predictions,lambda p:p.job_id,'prediction')
    info = _unique(evidence['jobs'],lambda j:j['job_id'],'job evidence')
    if evidence['protocol_hash'] != protocol['protocol_hash'] or set(pred)!=set(jobs) or set(info)!=set(jobs) or set(receipts)!=set(jobs):
        raise ValueError('exact job/prediction/evidence/receipt mapping required')
    indexed_ids = set(indexed)
    owned = []; results = []; by_events = {}; removed_prefill = 0.; post_seconds = 0.;prefill_measured=True
    for jid,job in jobs.items():
        p,s,row = pred[jid],scores[jid],info[jid]
        validate_record(p)
        if row['prediction_hash']!=content_hash(p) or row['score_hash']!=content_hash(s):
            raise ValueError('job prediction/score hash mismatch')
        if (p.task_id,p.policy_id,p.repetition_id,p.protocol_hash) != (job['task_id'],s.policy_id,job['repetition_id'],protocol['protocol_hash']):
            raise ValueError('prediction identity mismatch')
        if any(row[k]!=job[k] for k in ('task_id','scope','arm','repetition_id')) or row['config_id']!=job['method']['config_id']:
            raise ValueError('job evidence identity mismatch')
        if row['action_k']!=(receipts[jid]['decision'] or {}).get('action_k') or row['status']!=p.status:
            raise ValueError('decision action/status differs from job evidence')
        ids = row['event_ids']; owned.extend(ids)
        if set(ids) - indexed_ids:
            raise ValueError('missing accounted event')
        attempt_ids = [i for attempt in row['attempts'] for i in attempt['event_ids']]
        if Counter(attempt_ids)!=Counter(ids) or len(attempt_ids)!=len(set(attempt_ids)):
            raise ValueError('attempt event ownership mismatch')
        jobevents = [indexed[i] for i in ids];by_events[jid] = jobevents
        roles = Counter(); enclosing = union = serving = experiment = overlap = 0.
        for attempt in row['attempts']:
            current = [indexed[i] for i in attempt['event_ids']]
            if any((e.run_id,e.task_id,e.policy_id,e.attempt)!=(p.run_id,p.task_id,p.policy_id,attempt['attempt']) for e in current):
                raise ValueError('event ownership identity mismatch')
            boundary = [e for e in current if e.role=='serving']
            if len(boundary)!=1:
                raise ValueError('one serving enclosure per accounted attempt required')
            boundary = boundary[0];enclosing += boundary.elapsed_seconds
            transfer = sum(e.elapsed_seconds for e in current if e.role=='worker_reload_transfer')
            reload = sum(e.elapsed_seconds for e in current if e.role=='worker_reload')
            serving += boundary.elapsed_seconds-transfer+reload
            experiment += boundary.elapsed_seconds-transfer+sum(e.elapsed_seconds for e in current
                if e.role in ('telemetry','setup','warmup','offline','worker_reload'))
            components = [e for e in current if e.role not in (
                'serving','telemetry','setup','warmup','offline','worker_reload','worker_reload_transfer',
                'setup_in_serving','worker_reload_in_serving')]
            if any(e.start_ns<boundary.start_ns or e.stop_ns>boundary.stop_ns for e in components):
                raise ValueError('component lies outside serving enclosure')
            covered = _union_seconds([(e.start_ns,e.stop_ns) for e in components])
            union += covered;overlap += sum(e.elapsed_seconds for e in components)-covered
            for e in current: roles[e.role] += e.elapsed_seconds
            if attempt['attempt']==p.attempt:
                required = {'retrieval','payload'}
                if receipts[jid]['decision'] is not None: required.add('routing')
                paid = receipts[jid]['paid']
                generation = [e for e in current if e.role.startswith('generation:')]
                if len(paid)!=p.generation_calls or {e.event_id for e in generation}!=set(p.event_ids):
                    raise ValueError('missing paid generation component')
                if {r['event']['event_id'] for r in paid}!=set(p.event_ids):
                    raise ValueError('paid receipt/event component mismatch')
                for r in paid:
                    ev = indexed.get(r['event']['event_id'])
                    if ev is None or content_hash(r['event'])!=content_hash(ev):
                        raise ValueError('paid event content mismatch')
                    role = ev.role.split(':',1)[1]
                    required.update({f'evidence:{role}',f'prompt:{role}',f'generation:{role}',f'parse:{role}'})
                present = {e.role for e in current}
                if 'failure_payload' in present: required.discard('payload')
                if not required <= present:
                    raise ValueError('missing required cost role/component: '+str(sorted(required-present)))
                if job['method']['family']=='POST-OUTCOME' and p.generation_calls and 'generation:draft' not in present:
                    raise ValueError('missing paid POST draft role')
        allocations = row['shared_allocations']
        if len({a['event_id'] for a in allocations})!=len(allocations) or any(
                not math.isfinite(a['allocated_seconds']) or a['allocated_seconds']<0 for a in allocations):
            raise ValueError('invalid shared cost allocation')
        experiment += sum(a['allocated_seconds'] for a in allocations)
        _close(serving,s.total_serving_seconds);_close(experiment,s.total_experiment_seconds)
        if job['method']['family']=='POST-OUTCOME':
            clean = sum(e.clean_prefill_seconds for e in jobevents if e.role=='generation:answer')
            if any(e.clean_prefill_seconds>e.elapsed_seconds for e in jobevents):
                raise ValueError('clean prefill exceeds measured generation')
            measured={r['event']['event_id']:r['result'].get('telemetry',{})
                      for r in receipts[jid].get('all_paid',receipts[jid]['paid'])}
            for e in jobevents:
                if e.role=='generation:answer' and measured.get(e.event_id,{}).get('clean_prefill_seconds')!=e.clean_prefill_seconds:
                    prefill_measured=False
            removed_prefill += clean;post_seconds += serving
        results.append({'job_id':jid,'serving_seconds':serving,'experiment_seconds':experiment,
            'enclosing_seconds':enclosing,'instrumented_union_seconds':union,
            'residual_overhead_seconds':enclosing-union,'overlapping_component_seconds':overlap,
            'cost_roles':dict(roles),'shared_allocated_seconds':sum(a['allocated_seconds'] for a in allocations),
            'action_k':row['action_k'],'attempts':len(row['attempts'])})
    if Counter(owned)!=Counter(indexed.keys()):
        raise ValueError('complete unique event ownership required')
    lookup = {(j['task_id'],scope,config):j['job_id'] for (scope,config),rows in groups.items() for j in rows}
    reconstruction = []
    for jid,j in jobs.items():
        if j['scope']!='primary': continue
        representative = lookup[(j['task_id'],'representative',j['method']['config_id'])]
        action = info[representative]['action_k']
        source = (lookup[(j['task_id'],'oracle-source',protocol['methods']['oracle_source']['config_id'])] if action==2 else
                  lookup[(j['task_id'],'anchor',protocol['methods']['anchor']['config_id'])] if action==10 else None)
        compatible = source is not None and info[jid]['action_k']==action and all(
            _compatible(pred[source],pred[target],receipts[source]['paid'],receipts[target]['paid'])
            for target in (representative,jid))
        own = [e for e in by_events[representative] if e.attempt==pred[representative].attempt and e.role in ('routing','payload')]
        replaced = [e for e in by_events.get(source,[]) if source and e.attempt==pred[source].attempt and e.role in ('routing','payload')]
        seconds = scores[source].total_serving_seconds-sum(e.elapsed_seconds for e in replaced)+sum(e.elapsed_seconds for e in own) if compatible else None
        reconstruction.append({'job_id':jid,'task_id':j['task_id'],'arm':j['arm'],'repetition_id':j['repetition_id'],
            'source_job_id':source,'routing_source_job_id':representative,'action_k':action,
            'status':'compatible' if compatible else 'incompatible',
            'reason':None if compatible else 'action/request/evidence/output/token identity not established',
            'reconstructed_seconds':seconds,'direct_seconds':scores[jid].total_serving_seconds,
            'direct_minus_reconstructed':scores[jid].total_serving_seconds-seconds if compatible else None,
            'direct_over_reconstructed':scores[jid].total_serving_seconds/seconds if compatible and seconds>0 else None,
            'prompt_tokens':pred[jid].prompt_tokens})
    strata={}
    for row in reconstruction:
        key=(row['arm'],row['action_k'],row['prompt_tokens']);strata.setdefault(key,[]).append(row)
    strata_rows=[]
    for (arm,action,length),rows in strata.items():
        compatible=[r for r in rows if r['status']=='compatible']
        strata_rows.append({'arm':arm,'action_k':action,'prompt_tokens':length,'assigned_jobs':len(rows),
            'compatible_jobs':len(compatible),'unavailable_jobs':len(rows)-len(compatible),
            'mean_direct_minus_reconstructed':sum(r['direct_minus_reconstructed'] for r in compatible)/len(compatible) if compatible else None})
    return {'jobs':results,'assigned_direct_jobs':len(reconstruction),'reconstruction':reconstruction,
        'action_length_strata':strata_rows,
        'primary_cost_authority':'actual fresh direct complete pipeline',
        'comparison':'descriptive paired source reconstruction; no wall-time equivalence tolerance inferred',
        'post_optimistic_bound':{'executed':False,'selection_pool':False,'actual_serving_seconds':post_seconds,
            'removed_full_prefill_seconds':removed_prefill if prefill_measured else None,
            'optimistic_serving_seconds':post_seconds-removed_prefill if prefill_measured else None,
            'reason':None if prefill_measured else 'clean_prefill_not_fully_measured',
            'limitation':'all measured full-call clean prefill removed; paid drafts, decoding and other costs retained; numerical cache gate failed'}}


def diagnostics(protocol, scored_rows, predictions, evidence):
    jobs,scores,groups = _assignments(protocol,scored_rows)
    info = _unique(evidence['jobs'],lambda j:j['job_id'],'job evidence')
    pred = _unique(predictions,lambda p:p.job_id,'prediction')
    ids = protocol['sample']['task_ids'];cells = dict.fromkeys(('both_fail','rescue','harm','both_success'),0)
    small = {j['task_id']:scores[j['job_id']] for j in groups[('oracle-source',protocol['methods']['oracle_source']['config_id'])]}
    full = {j['task_id']:scores[j['job_id']] for j in groups[('anchor',protocol['methods']['anchor']['config_id'])]}
    seconds = 0.;successes = 0;switches = []
    for tid in ids:
        a,b = small[tid],full[tid]
        cells[{(0,0):'both_fail',(0,1):'rescue',(1,0):'harm',(1,1):'both_success'}[a.joint_em,b.joint_em]] += 1
        cheap,expensive = sorted((a,b),key=lambda s:s.total_serving_seconds)
        seconds += cheap.total_serving_seconds;successes += cheap.joint_em
        if expensive.joint_em>cheap.joint_em:
            switches.append((expensive.total_serving_seconds-cheap.total_serving_seconds,tid))
    frontier = [{'successes':successes,'total_seconds':seconds}]
    for extra,tid in sorted(switches):
        seconds += extra;successes += 1
        frontier.append({'successes':successes,'total_seconds':seconds,'switched_task_id':tid})
    aa = {}
    for arm in ('A','B'):
        pairs=[]
        for tid in ids:
            rows=sorted([j for j in jobs.values() if j['scope']=='primary' and j['arm']==arm and j['task_id']==tid],key=lambda j:j['repetition_id'])
            pairs.append({'task_id':tid,'job_ids':[j['job_id'] for j in rows],
                'seconds':[scores[j['job_id']].total_serving_seconds for j in rows],
                'output_agreement':len({info[j['job_id']]['output_parity_hash'] for j in rows})==1,
                'statuses':[pred[j['job_id']].status for j in rows]})
        aa[arm]={'assigned_tasks':len(ids),'pairs':pairs,'scope':'fresh same-arm repetitions; repetitions are not tasks'}
    return {'oracle':{'assigned_tasks':len(ids),'cells':cells,
        'oracle_quality':sum(max(small[t].joint_em,full[t].joint_em) for t in ids)/len(ids),
        'frontier':frontier,'deployable':False,'scope':'clairvoyant two/ten diagnostic with zero gate overhead'},
        'AA':aa,'always_abstain':{'assigned_tasks':len(ids),'success_count':0,'ratio':None,
            'reason':'zero_successes','scope':'analytical quality diagnostic; zero reader calls, no measured serving pipeline'},
        'no_context':{'status':'not_scored_in_primary','protected_calls':0,
            'development':'four actual Task13 calibration calls retained/paid; separate full-closure projection required for scoring'}}


def failure_analysis(scored_rows, predictions):
    pred = _unique(predictions,lambda p:p.job_id,'prediction')
    if set(pred)!={s.job_id for s in scored_rows} or len(pred)!=len(scored_rows):
        raise ValueError('failure review requires exact assigned predictions/scores')
    output=[]
    for score in scored_rows:
        p=pred[score.job_id];validate_record(score);validate_record(p)
        if (score.run_id,score.task_id,score.policy_id,score.repetition_id)!=(p.run_id,p.task_id,p.policy_id,p.repetition_id):
            raise ValueError('failure review identity mismatch')
        if score.joint_em: continue
        tags=[];evidence=[]
        if p.status in ('parse_error','invalid_citation'):
            tags.append('parse/ID error');evidence.append({'status':p.status})
        if p.status in ('context_overflow','timeout','budget_exhausted'):
            tags.append('budget/context exhaustion');evidence.append({'status':p.status})
        if p.status=='infra_error':
            tags.append('infrastructure');evidence.append({'status':p.status})
        if score.answer_em==1:
            tags.append('answer correct/citations wrong');evidence.append({'answer_em':1,'joint_em':0,'support_em':score.support_em})
        if not tags:
            tags=['unknown'];evidence=[{'joint_em':score.joint_em,'answer_em':score.answer_em,'status':p.status}]
        output.append({'job_id':p.job_id,'task_id':p.task_id,'tags':tags,'evidence':evidence,
                       'causal_attribution':'unknown','score_overridden':False})
    return output


def pooled_corpus_manifest(development_tasks, protected_population):
    """Pure full-population document union; no query selection or gold association."""
    if not protected_population or any(t.split not in ('pilot','fit','tune') for t in development_tasks) or any(
            t.split!='protected' for t in protected_population):
        raise ValueError('selected development and complete protected population required')
    development = _unique(development_tasks,lambda t:t.task_id,'development task')
    protected = _unique(protected_population,lambda t:t.task_id,'protected population task')
    if set(development)&set(protected): raise ValueError('development/protected overlap')
    for t in [*development_tasks,*protected_population]: validate_record(t)
    documents = sorted({d for t in [*development_tasks,*protected_population] for d in t.candidate_ids})
    return {'document_ids':documents,'document_ids_hash':content_hash(documents),
        'development_task_count':len(development),'protected_population_count':len(protected),
        'development_tasks_hash':content_hash(sorted(development)),
        'protected_population_hash':content_hash(sorted(protected)),
        'query_restrictions':False,'gold_associations':False,'index_constructed':False}


def transfer(protocol: dict, corpus: dict, query_ids: list[str], runtime: object) -> dict:
    """No native side effect before separate prospective review and budget pilot."""
    return {'protocol_hash':protocol['protocol_hash'],'executed':False,'feasibility':'not_assessed',
        'status':'requires_separate_prospective_diagnostic',
        'missing':['actual remaining capacity assessment','prospective full-population corpus/query manifest',
                   'authentic unchanged-core diagnostic execution path','measured index/retrieval/generation budget'],
        'scope':'packet-only until pooled transfer actually executes'}


def _document(documents, doc_id):
    return documents[doc_id] if isinstance(documents,dict) else documents.get(doc_id)


def stress_cases(tasks, documents, spec):
    """Labeled diagnostic copies only; no natural primary input mutation."""
    if spec.get('kind') not in ('prompt_injection','contradiction') or not isinstance(spec.get('text'),str) or not spec['text'].strip():
        raise ValueError('explicit labeled diagnostic text/kind required')
    output=[]
    for task in tasks:
        copies=[asdict(_document(documents,d)) for d in task.candidate_ids]
        if not copies: raise ValueError('stress requires nonempty evidence')
        copies[0]['sentences'].append(spec['text'])
        copies[0]['character_count']=sum(map(len,copies[0]['sentences']))
        copies[0]['doc_id']=content_hash([copies[0]['title'],copies[0]['sentences']])
        output.append({'natural_task_id':task.task_id,'question':task.question,'documents':copies,
            'kind':spec['kind'],'synthetic':True,'executed':False,'primary_scores_changed':False})
    return output


def blind_review_packet(cases, documents, *, count):
    """Return separate reviewer packet/key; preparing it does not perform review.

    Callers must keep the key, original cases, scores and gold inaccessible to the
    reviewer until tentative notes are durably sealed. This helper alone cannot
    certify that a reviewer has not already seen outcomes.
    """
    bytask=_unique(cases,lambda c:c['task_id'],'review task')
    if type(count) is not int or not 1<=count<=len(bytask): raise ValueError('invalid review count')
    selected=sorted(cases,key=lambda c:content_hash([271828,c['task_id'],'annotation-review']))[:count]
    packet=[];key=[]
    for position,case in enumerate(selected):
        alias=f'case-{position+1}'
        packet.append({'blind_id':alias,'question':case['question'],
            'evidence':[{'title':_document(documents,d).title,'sentences':list(_document(documents,d).sentences)} for d in case['evidence_ids']],
            'response':case['raw_output']})
        key.append({'blind_id':alias,'task_id':case['task_id'],'job_id':case['job_id']})
    return {'packet':{'cases':packet},'private_key':key,'status':'packet_prepared_review_unexecuted',
        'selection_rule':'SHA256 canonical [271828,task_id,"annotation-review"] ascending; unique tasks, outcome-independent'}


def seal_review_notes(packet, notes):
    ids=[c['blind_id'] for c in packet['cases']]
    if len(notes)!=len(ids) or {n['blind_id'] for n in notes}!=set(ids) or any(
            not isinstance(n.get('notes'),str) or not n['notes'].strip() for n in notes):
        raise ValueError('one complete tentative note per blind case required')
    return {'packet_hash':content_hash(packet),'notes_hash':content_hash(notes),
        'scope':'write this receipt and notes durably before reveal; does not itself certify reviewer blindness'}


def pooled_top_ten(vectors, paragraphs, query, *, batch_rows=4096):
    """Exhaustive float32 CPU memmap search, max per paragraph, stable ID ties.

    Only a bounded matrix slice is materialized. Metadata/maximum-score arrays
    are linear in corpus size; there is no packet-candidate argument or gold.
    Query embedding and index/setup costs belong to the enclosing caller.
    """
    import heapq
    import time
    import numpy as np
    from .schemas import RankedDocument
    from .retrieval import validate_vectors
    started=time.perf_counter()
    if (not isinstance(vectors,np.ndarray) or vectors.ndim!=2 or vectors.shape[1]!=384 or
            vectors.dtype!=np.float32 or not len(vectors) or type(batch_rows) is not int or batch_rows<1):
        raise ValueError('nonempty float32 384-vector matrix and positive batch size required')
    if not isinstance(query,np.ndarray) or query.shape!=(384,) or query.dtype!=np.float32:
        raise ValueError('normalized float32 384-dimensional query required')
    validate_vectors(query.reshape(1,384),1)
    _unique(paragraphs,lambda p:p['doc_id'],'pooled paragraph')
    owners=np.full(len(vectors),-1,dtype=np.int64)
    for index,p in enumerate(paragraphs):
        start,count=p['vector_start'],p['window_count']
        if (type(start) is not int or type(count) is not int or start<0 or count<1 or
                start+count>len(vectors) or np.any(owners[start:start+count]!=-1)):
            raise ValueError('invalid/overlapping pooled window metadata')
        owners[start:start+count]=index
    if np.any(owners<0): raise ValueError('uncovered pooled vectors')
    maxima=np.full(len(paragraphs),-np.inf,dtype=np.float32)
    dots_seconds=aggregation_seconds=lookup_seconds=0.;batches=maximum=0
    for start in range(0,len(vectors),batch_rows):
        tick=time.perf_counter();block=vectors[start:start+batch_rows]
        validate_vectors(block,len(block));lookup_seconds+=time.perf_counter()-tick
        tick=time.perf_counter();scores=block @ query;dots_seconds+=time.perf_counter()-tick
        tick=time.perf_counter();np.maximum.at(maxima,owners[start:start+len(block)],scores)
        aggregation_seconds+=time.perf_counter()-tick
        batches+=1;maximum=max(maximum,len(block))
    tick=time.perf_counter()
    order=heapq.nsmallest(10,range(len(paragraphs)),key=lambda i:(-float(maxima[i]),paragraphs[i]['doc_id']))
    ranking=[RankedDocument(paragraphs[i]['doc_id'],float(maxima[i]),rank,
        paragraphs[i]['character_count'],paragraphs[i]['sentence_count'],paragraphs[i]['title']) for rank,i in enumerate(order)]
    for r in ranking:validate_record(r)
    return {'ranking':ranking,'window_count':len(vectors),'document_count':len(paragraphs),
        'batches':batches,'maximum_batch_rows':maximum,'packet_restrictions_used':False,
        'dots_seconds':dots_seconds,'aggregation_seconds':aggregation_seconds,'vector_lookup_validation_seconds':lookup_seconds,
        'sort_seconds':time.perf_counter()-tick,'full_seconds':time.perf_counter()-started,
        'precision':'CPU float32 batched matrix product; exhaustive, not bitwise packet-reduction parity'}


def _validate_analysis(protocol, analysis, scores):
    """Validate consumed family metrics without rerunning protected inference."""
    _,byjob,groups=_assignments(protocol,scores)
    if (analysis['protocol_hash']!=protocol['protocol_hash'] or
            analysis['assigned_unique_tasks']!=len(protocol['sample']['task_ids']) or
            analysis['population']!=protocol['sample']['N']):
        raise ValueError('analysis identity/denominator mismatch')
    if set(analysis['families'])!={scope+':'+config for scope,config in groups}:
        raise ValueError('analysis family roster mismatch')
    for (scope,config),jobs in groups.items():
        row=analysis['families'][scope+':'+config];values=[byjob[j['job_id']] for j in jobs]
        success=sum(s.joint_em for s in values);total=sum(s.total_serving_seconds for s in values);n=len(values)
        expected={'n':n,'repetitions':1,'success_count':success,'quality':success/n,'total_time':total,
            'mean_time':total/n,'ratio':total/success if success else None,
            'reason':None if success else 'zero_successes','answer_em':sum(s.answer_em for s in values)/n,
            'scope':scope,'config_id':config,'job_ids':[j['job_id'] for j in jobs]}
        for key,value in expected.items():
            if isinstance(value,float):_close(row[key],value)
            elif row[key]!=value:raise ValueError('analysis family values differ from closed scores')


def analyze_closed(protocol: dict) -> dict:
    """Read an already complete scored run; never opens gold records or rescores.

    Caller must obtain execution-phase release before using real observations.
    The existing full-run validator remains mandatory for all real data.
    """
    import time
    from .protocol import verify_protocol, file_hash, _read
    from .protected import validate_run
    from .runner import load_events
    from .storage import read_jsonl
    started=time.perf_counter();root=Path(protocol['run_dir'])
    if verify_protocol(Path(protocol.get('output_dir',root))/'protocol.json')!=protocol:
        raise ValueError('robustness protocol mismatch')
    predictions,context=validate_run(protocol,root)
    marker=_read(root/'scores.jsonl.closed.json')
    if marker['protocol_hash']!=protocol['protocol_hash'] or marker['paid_receipt_coverage']!='forward_v2':
        raise ValueError('complete protected score closure required')
    for name,digest in marker['hashes'].items():
        if not (root/name).resolve().is_relative_to(root.resolve()) or file_hash(root/name)!=digest:
            raise ValueError('score closure checksum mismatch')
    names=('scores.jsonl.closed.json','scores.jsonl','job-evidence.json','analysis.json',
           'predictions.closed.json','protected-run.closed.json')
    bindings={name:file_hash(root/name) for name in names}
    scores=[ScoredTask(**r) for r in read_jsonl(root/'scores.jsonl')]
    if marker['record_count']!=len(scores) or marker['assigned_unique_tasks']!=len(protocol['sample']['task_ids']):
        raise ValueError('score closure denominator mismatch')
    evidence=_read(root/'job-evidence.json');analysis=_read(root/'analysis.json')
    _validate_analysis(protocol,analysis,scores)
    receipt_map={};by_pred={p.job_id:p for p in predictions}
    for row in evidence['jobs']:
        jid=row['job_id'];p=by_pred[jid]
        for attempt in row['attempts']:
            prefix=(root/'jobs'/jid/f'attempt-{attempt["attempt"]}').resolve()
            for name,digest in attempt['files'].items():
                path=root/name
                if not path.resolve().is_relative_to(prefix) or file_hash(path)!=digest:
                    raise ValueError('attempt evidence checksum/path mismatch')
        directory=root/'jobs'/jid/f'attempt-{p.attempt}'
        paid=[]
        for number in range(1,p.generation_calls+1):
            record=_read(directory/f'paid-{number}.finished.json')
            record['request']=_read(directory/f'paid-{number}.started.json')['request']
            paid.append(record)
        decision=_read(directory/'decision.json')
        all_paid=[_read(path) for attempt in row['attempts']
                  for path in sorted((root/'jobs'/jid/f'attempt-{attempt["attempt"]}').glob('paid-*.finished.json'))]
        receipt_map[jid]={'decision':decision.get('decision'),'paid':paid,'all_paid':all_paid}
    events=load_events(root)
    result={'protocol_hash':protocol['protocol_hash'],'input_hashes':bindings,
        'attribution':ablate(protocol,scores,events),'families':deepcopy(analysis['families']),
        'accounting':audit_accounting(protocol,scores,events,predictions,evidence,receipt_map),
        'diagnostics':diagnostics(protocol,scores,predictions,evidence),
        'failures':failure_analysis(scores,predictions),
        'primary_analysis_reference':{'sha256':bindings['analysis.json'],'primary_status':analysis['primary']['status'],
            'quality_claim_valid':analysis['quality_claim_valid'],'outcome':analysis['outcome'],
            'limitation':'primary/quality/statistical assessment remains owned by frozen Task14 analysis'},
        'blinded_review':{'status':'unexecuted','pilot_review':'unblinded/score-contaminated; never relabeled'},
        'transfer':transfer(protocol,{},[],None),
        'scientific_data_access':'closed receipts only; no gold records opened',
        'outcome':analysis['outcome']}
    context.verify_unchanged()
    if any(file_hash(root/name)!=digest for name,digest in bindings.items()):
        raise ValueError('robustness inputs changed during analysis')
    result['analysis_seconds']=time.perf_counter()-started
    return result


def main(args) -> int:
    import json
    import time
    from .protocol import _read, file_hash
    from .protected import immutable_json
    from .storage import append_jsonl
    if not getattr(args,'protocol',None) or getattr(args,'config',None):
        raise ValueError('required offline checks use --protocol only; diagnostic execution needs separate prospective review')
    protocol=_read(Path(args.protocol))
    # Never append analysis artifacts into the frozen original run ledger.
    output=Path(args.output) if getattr(args,'output',None) else Path(protocol['run_dir']).parent/'task15-robustness'/f'{args.command}.json'
    if output.resolve().is_relative_to(Path(protocol['run_dir']).resolve()):
        raise ValueError('robustness output must be outside the primary run')
    started=time.perf_counter();status='failed';report_hash=None
    source_hash=file_hash(Path(__file__))
    try:
        if args.command=='transfer':result=transfer(protocol,{},[],None)
        elif args.command=='ablate':result=analyze_closed(protocol)
        else:raise ValueError('unknown robustness command')
        result.pop('analysis_seconds',None)
        result['robustness_source_sha256']=source_hash
        immutable_json(output,result);report_hash=file_hash(output);status='ok'
    finally:
        append_jsonl(output.with_suffix('.attempts.jsonl'),{'protocol_hash':protocol['protocol_hash'],
            'source_sha256':source_hash,'status':status,'report_sha256':report_hash,
            'elapsed_seconds':time.perf_counter()-started,
            'cost_boundary':'analysis and immutable report publication; excludes attempt-receipt persistence/console'})
    print(json.dumps({'status':args.command,'output':str(output),'executed':args.command=='ablate'}))
    return 0

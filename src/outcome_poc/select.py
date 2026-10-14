"""Common development-only quality and serving-cost selection."""
import math

from .schemas import validate_record

COMPARATORS={'FIXED','ADAPTIVE-k-tuned','ADAPTIVE-k-published','PRE-LINEAR','PRE-RF',
             'POST-OUTCOME','LLM-SUFFICIENCY','QUERY-ONLY','PROXY-LABEL'}


def configuration_metrics(predictions, scores, events):
    if not predictions or len({p.task_id for p in predictions}) != len(predictions):
        raise ValueError('one assigned prediction per unique tuning task required')
    keys=lambda r:(r.run_id,r.task_id,r.policy_id,r.job_id,r.repetition_id)
    if len(scores)!=len(predictions) or {keys(s) for s in scores}!={keys(p) for p in predictions}:
        raise ValueError('scores must match every assigned prediction')
    for record in [*predictions,*scores,*events]: validate_record(record)
    success=sum(s.joint_em for s in scores)
    seconds=sum(s.total_serving_seconds for s in scores)
    return {'assigned_tasks':len(predictions),'joint_successes':success,
            'answer_successes':sum(s.answer_em for s in scores),'Q':success/len(predictions),
            'answer_em':sum(s.answer_em for s in scores)/len(predictions),
            'mean_time':seconds/len(predictions),'total_serving_seconds':seconds,
            'total_experiment_seconds':sum(s.total_experiment_seconds for s in scores),
            'R':seconds/success if success else None,'reason':None if success else 'zero_successes',
            'source_event_ids':sorted({e.source_event_id or e.event_id for e in events})}


def configuration_sort_key(row):
    ratio=row['R']
    return (math.inf if ratio is None else ratio,-row['Q'],row['mean_time'],row['config_id'])


def select_configuration(config_rows, anchor):
    if not config_rows or len({r['config_id'] for r in config_rows})!=len(config_rows):
        raise ValueError('unique nonempty configuration IDs required')
    population=anchor['task_ids']
    if not population or len(set(population)) != len(population) or anchor['split']!='tune':
        raise ValueError('development tuning population required')
    rows=[]
    for row in config_rows:
        if row['split']!='tune' or row['task_ids']!=population:
            raise ValueError('no protected or mismatched tuning IDs accepted')
        for key in ('Q','answer_em','mean_time'):
            if not math.isfinite(row[key]) or row[key]<0: raise ValueError('invalid tuning metric')
        if row['Q']>1 or row['answer_em']>1 or (row['R'] is not None and (not math.isfinite(row['R']) or row['R']<0)):
            raise ValueError('invalid tuning ratio/quality')
        eligible=row['Q']>=anchor['Q'] and row['answer_em']>=anchor['answer_em']
        rows.append({**row,'eligible':eligible,'selection_pool':row['family']=='PRE-OUTCOME-GBM' or row['family'] in COMPARATORS,
                     'ineligible_reason':None if eligible else 'below_fixed_ten_joint_or_answer_em'})
    allowed=[r for r in rows if r['eligible'] and r['selection_pool']]
    candidates=[r for r in allowed if r['family']=='PRE-OUTCOME-GBM']
    comparators=[r for r in allowed if r['family']!='PRE-OUTCOME-GBM']
    if not candidates or not comparators: raise ValueError('eligible candidate and comparator required')
    families={}
    for family in sorted({r['family'] for r in rows}):
        members=[r for r in rows if r['family']==family]
        eligible=[r for r in members if r['eligible']]
        families[family]={'representative':min(eligible or members,key=configuration_sort_key),
                          'representative_eligible':bool(eligible),'config_count':len(members),'eligible_count':len(eligible)}
    return {'A*':min(candidates,key=configuration_sort_key),'B*':min(comparators,key=configuration_sort_key),
            'fixed_ten_anchor':anchor,'configurations':rows,'families':families}


def reconstructed_seconds(family, mode, source_seconds, source_events, routing_seconds, payload_seconds=None):
    """Keep paid work; replace source policy work with per-request measured work."""
    if family!='POST-OUTCOME' and mode in {'always_ten','always_two'}:
        return source_seconds
    replaced=sum(e.elapsed_seconds for e in source_events if e.role=='routing')
    if payload_seconds is not None:
        replaced+=sum(e.elapsed_seconds for e in source_events if e.role=='payload')
    result=source_seconds-replaced+routing_seconds+(payload_seconds or 0.)
    if result<0 or not math.isfinite(result): raise ValueError('invalid reconstructed cost')
    return result


def _policy_definitions(models):
    from .policies import ThresholdPolicy, PostOutcomePolicy, AdaptiveKPolicy
    from .train import load_gate
    policies=[]
    for model_name,manifest in models.items():
        model=load_gate(manifest)
        family='PRE-LINEAR' if model_name.startswith('PRE-LINEAR-') else model_name
        for number,threshold in enumerate(manifest['thresholds']):
            identity=f'{model_name}:{number:02d}:{threshold["threshold_mode"]}'
            settings={**threshold,'policy_id':model_name,'feature_schema_hash':manifest['feature_schema_hash']}
            policy=(PostOutcomePolicy if family=='POST-OUTCOME' else ThresholdPolicy)(model,settings)
            policies.append({'config_id':identity,'family':family,'model_name':model_name,
                             'model_artifact_sha256':manifest['artifact_sha256'],
                             'fit_escalation_probability':(1. if threshold['threshold_mode']=='always_ten' else
                                  0. if threshold['threshold_mode']=='always_two' else
                                  sum(p>threshold['threshold'] for p in manifest['training_predictions'])/len(manifest['training_predictions'])),
                             **threshold,'policy':policy})
    for buffer in range(6):
        policy=AdaptiveKPolicy(buffer,variant='tuned')
        policies.append({'config_id':policy.policy_id,'family':'ADAPTIVE-k-tuned','buffer':buffer,'policy':policy})
    published=AdaptiveKPolicy(5,variant='published')
    policies.append({'config_id':published.policy_id,'family':'ADAPTIVE-k-published','buffer':5,'policy':published})
    return policies


def tune(config: dict, runtime: object) -> dict:
    """Annotation-free acquisition and request-level policy observations; no labels."""
    from dataclasses import asdict, replace
    from datetime import datetime, timezone
    from pathlib import Path
    import time
    from .collection import _ObservedRetrieval
    from .features import feature_schema
    from .policies import FixedPolicy, PostOutcomePolicy, SufficiencyPolicy
    from .runner import (execute_job, action_signature, job_id, close_run, record_shared_cost,
                         _result, _answer_payload)
    from .schemas import PaidDraft, ReaderResult
    from .storage import atomic_json, append_jsonl, content_hash
    from .timing import TimingLedger
    tasks=config['tasks']
    ids=[t.task_id for t in tasks]
    if not ids or ids!=config['assigned_ids'] or len(set(ids))!=len(ids) or any(t.split!='tune' for t in tasks):
        raise ValueError('exact assigned tune membership required; protected access forbidden')
    if any(k in config for k in ('gold','scores','supporting_facts','answer')):
        raise ValueError('gold-bearing tune acquisition configuration')
    root=Path(config['run_dir']);root.mkdir(parents=True,exist_ok=True)
    if (root/'schedule.json').exists(): raise ValueError('tune acquisition already scheduled')
    preparation_start=runtime.clock()
    definitions=_policy_definitions(config['models'])
    jobs=[];schedule=[]
    for task in tasks:
        actions=[(f'k={k}',FixedPolicy(k)) for k in range(1,11)]
        actions += [('post-full',PostOutcomePolicy(None,{'threshold_mode':'always_ten','threshold':None})),
                    ('judge',SufficiencyPolicy())]
        for arm,policy in actions:
            signature=action_signature(task,runtime.config,task.candidate_ids,arm,'none')
            job={'run_id':root.name,'task':task,'policy':policy,'protocol_hash':'development-task12',
                 'job_id':job_id(signature,'direct:tune:'+arm,0),'mode':'direct','cache_mode':'none',
                 'arm':arm,'repetition_id':0}
            jobs.append(job);schedule.append({'task_id':task.task_id,'arm':arm,'job_id':job['job_id']})
    checks=config.get('direct_check_ids',[])
    if not set(checks)<=set(ids): raise ValueError('direct check IDs must be assigned tune tasks')
    check_definitions=[]
    for name in ('PRE-OUTCOME-GBM','PRE-RF','POST-OUTCOME'):
        candidates=[d for d in definitions if d.get('model_name')==name and d.get('threshold_mode')=='numeric']
        if candidates: check_definitions.append(candidates[len(candidates)//2])
    check_definitions += [d for d in definitions if d['config_id']=='ADAPTIVE-k-published-B5']
    for task in tasks:
        if task.task_id not in checks: continue
        for definition in check_definitions:
            signature=action_signature(task,runtime.config,task.candidate_ids,definition['config_id'],'none')
            job={'run_id':root.name,'task':task,'policy':definition['policy'],'protocol_hash':'development-task12',
                 'job_id':job_id(signature,'direct:tune-check',0),'mode':'direct','cache_mode':'none',
                 'arm':'direct-check:'+definition['config_id'],'repetition_id':0}
            jobs.append(job);schedule.append({'task_id':task.task_id,'arm':job['arm'],'job_id':job['job_id']})
    declared=[{k:v for k,v in d.items() if k!='policy'} for d in definitions]
    atomic_json(root/'schedule.json',{'assigned_ids':ids,'jobs':schedule,'runtime_config':runtime.config,
                                    'configurations':declared,'feature_schema_hash':feature_schema()['hash']})
    assigned=[j['job_id'] for j in jobs]
    if config.get('setup_interval'):
        record_shared_cost(root,'cold_setup',*config['setup_interval'],assigned,source_id='task12-native-setup')
        runtime._lifecycle_seen=len(getattr(runtime.reader.backend,'lifecycle',[]))
    record_shared_cost(root,'offline',preparation_start,runtime.clock(),assigned,source_id='task12-policy-materialization-and-schedule')
    original=runtime.retrieval; recording=_ObservedRetrieval(original);runtime.retrieval=recording
    predictions=[];sources={};rankings={}
    try:
        for job,item in zip(jobs,schedule):
            if config.get('deadline_utc') and (datetime.fromisoformat(config['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()<=3600:
                raise TimeoutError('deadline reporting reserve exhausted')
            prediction=execute_job(job,runtime,root)
            predictions.append(prediction)
            if hasattr(runtime.reader.backend,'last_resources'):
                append_jsonl(root/'resources.jsonl',{'job_id':prediction.job_id,**runtime.reader.backend.last_resources})
            if prediction.status=='infra_error': raise ValueError('unresolved tune infrastructure; original attempts preserved')
            sources[(prediction.task_id,item['arm'])]=prediction
            rankings[prediction.task_id]=recording.ranking
            if item['arm']=='k=2':
                append_jsonl(root/'observables.jsonl',{'task_id':prediction.task_id,
                             'ranking':[asdict(r) for r in recording.ranking],
                             'source_prediction_id':prediction.job_id,'runtime_config_hash':content_hash(runtime.config)})
            if len(predictions)%12==0:
                print(__import__('json').dumps({'stage':'tune-acquisition','completed':len(predictions),'assigned':len(jobs)}),flush=True)
        # Policies receive the identical ranked packet and a real event-backed paid draft.
        # One choose per request/threshold measures feature construction, model.predict and routing.
        routing_phase_start=runtime.clock()
        for definition in definitions:
            policy=definition['policy']
            for task in tasks:
                ranking=rankings[task.task_id]
                small=sources[(task.task_id,'k=2')]
                draft=PaidDraft(small.event_ids[0],ReaderResult(small.raw_output,small.answer,small.citations,
                                small.status,small.prompt_tokens,small.generated_tokens,[],[],None))
                identity=content_hash([definition['config_id'],task.task_id,'request-routing'])
                routejob={'job_id':identity,'run_id':root.name,'task':task,'attempt':1}
                ledger=TimingLedger(routejob,policy.policy_id,runtime.clock)
                with ledger.component('routing'):
                    decision=policy.choose(task.question,ranking,draft if getattr(policy,'requires_draft',False) else None)
                    validate_record(decision)
                source=sources[(task.task_id,'post-full' if definition['family']=='POST-OUTCOME' and decision.action_k==10 else f'k={decision.action_k}')]
                payload_prediction=replace(source,policy_id=policy.policy_id,job_id=identity,elapsed_seconds=0.)
                from .runner import _read
                source_decision=_read(root/'jobs'/source.job_id/f'attempt-{source.attempt}'/'decision.json')
                with ledger.component('payload'):
                    runtime.serialize({'prediction':_answer_payload(payload_prediction),
                        'decision':{'decision':decision,'aliases':{f'D{i}':r.doc_id for i,r in enumerate(ranking)},
                                    'stop_reason':source_decision['stop_reason'],'action_signature':source_decision['action_signature']}})
                for event in ledger.events: append_jsonl(root/'routing-events.jsonl',event)
                append_jsonl(root/'routes.jsonl',{'config_id':definition['config_id'],'task_id':task.task_id,
                    'decision':decision,'source_prediction_id':source.job_id,
                    'routing_seconds':ledger.events[0].elapsed_seconds,'payload_seconds':ledger.events[1].elapsed_seconds,
                    'event_ids':[e.event_id for e in ledger.events]})
        record_shared_cost(root,'offline',routing_phase_start,runtime.clock(),assigned,source_id='task12-request-routing-measurements-and-receipts')
        closure=close_run(root,jobs)
        names=('schedule.json','observables.jsonl','routes.jsonl','routing-events.jsonl')
        from .runner import _digest
        atomic_json(root/'tuning-acquisition.closed.json',{'hashes':{n:_digest(root/n) for n in names if (root/n).exists()},
                    'prediction_closure_sha256':_digest(root/'predictions.closed.json'),'assigned_ids':ids})
        return {'assigned_jobs':len(jobs),'assigned_tasks':len(tasks),'all_k':list(range(1,11)),
                'generation_calls':sum(p.generation_calls for p in predictions),'closure':closure,
                'request_routing_observations':len(definitions)*len(tasks)}
    finally:
        runtime.retrieval=original


def analyze_tuning(run_dir, assigned_ids, *, require_roster=True):
    """Separate closed-score join; never called by native serving."""
    from dataclasses import replace
    from pathlib import Path
    import json
    import time
    from .runner import (_digest, _prediction, validate_closed_accounting, _read, _owned_reloads)
    from .schemas import CostEvent, ScoredTask
    from .storage import read_jsonl, content_hash
    started=time.perf_counter()
    root=Path(run_dir)
    acquisition=_read(root/'tuning-acquisition.closed.json')
    if acquisition['assigned_ids']!=assigned_ids:
        raise ValueError('exact tune assignment required')
    if any(_digest(root/n)!=digest for n,digest in acquisition['hashes'].items()):
        raise ValueError('tuning acquisition checksum mismatch')
    if acquisition['prediction_closure_sha256']!=_digest(root/'predictions.closed.json'):
        raise ValueError('tuning prediction closure mismatch')
    schedule=_read(root/'schedule.json')
    if schedule['assigned_ids']!=assigned_ids: raise ValueError('tune schedule assignment mismatch')
    predictions=[_prediction(r) for r in read_jsonl(root/'predictions.jsonl')]
    context=validate_closed_accounting(root,predictions)
    if context.receipt_coverage=='legacy_unsealed': raise ValueError('tuning selection requires paid receipt coverage')
    score_receipt=_read(root/'scores.jsonl.closed.json')
    if (score_receipt['scores_sha256']!=_digest(root/'scores.jsonl') or
            score_receipt['prediction_sha256']!=_digest(root/'predictions.jsonl') or
            score_receipt['prediction_closure_sha256']!=_digest(root/'predictions.closed.json') or
            score_receipt['timing_kind']!='complete_ledger'):
        raise ValueError('separate complete-ledger scorer receipt mismatch')
    scores=[ScoredTask(**r) for r in read_jsonl(root/'scores.jsonl')]
    byjob={p.job_id:p for p in predictions};scorebyjob={s.job_id:s for s in scores}
    if len(scores)!=len(predictions) or set(byjob)!=set(scorebyjob):
        raise ValueError('scorer assigned denominator mismatch')
    for p in predictions:
        s=scorebyjob[p.job_id]
        if (s.run_id,s.task_id,s.policy_id,s.repetition_id)!=(p.run_id,p.task_id,p.policy_id,p.repetition_id):
            raise ValueError('score source identity mismatch')
        if context.costs(p)!={'total_serving_seconds':s.total_serving_seconds,'total_experiment_seconds':s.total_experiment_seconds}:
            raise ValueError('score cost changed from validated ledger')
    eventbyjob={}
    for p in predictions:
        events=[]
        for attempt in sorted((root/'jobs'/p.job_id).glob('attempt-*')):
            if (attempt/'observed-failure.closed.json').exists():
                from .runner import _observed_failure
                _,observed=_observed_failure(attempt);events+=observed
            else:
                events += [CostEvent(**r) for r in read_jsonl(attempt/'events.jsonl')]
            events += _owned_reloads(attempt)
        eventbyjob[p.job_id]=events
    sources={(j['task_id'],j['arm']):j['job_id'] for j in schedule['jobs']}
    routes=list(read_jsonl(root/'routes.jsonl'))
    routebykey={(r['config_id'],r['task_id']):r for r in routes}
    if len(routebykey)!=len(routes): raise ValueError('duplicate tuning routing receipt')
    routing_rows=list(read_jsonl(root/'routing-events.jsonl'))
    routeevents={r['event_id']:CostEvent(**r) for r in routing_rows}
    if len(routeevents)!=len(routing_rows): raise ValueError('duplicate paid routing event')
    for event in routeevents.values():
        validate_record(event)
        if event.elapsed_seconds!=(event.stop_ns-event.start_ns)/1e9: raise ValueError('routing event duration mismatch')
    rows=[];bounds=[]
    def make_row(definition,route_mode):
        selected=[];scored=[];events=[];detail=[];bound_seconds=[]
        for task_id in assigned_ids:
            if route_mode=='fixed':
                source_id=sources[(task_id,f'k={definition["k"]}')];route=None
            elif route_mode=='judge':
                source_id=sources[(task_id,'judge')];route=None
            else:
                route=routebykey[(definition['config_id'],task_id)]
                source_id=route['source_prediction_id']
            p=byjob[source_id];s=scorebyjob[source_id]
            if p.task_id!=task_id: raise ValueError('routing source task identity mismatch')
            all_events=eventbyjob[source_id]
            final_events=[e for e in all_events if e.attempt==p.attempt]
            seconds=s.total_serving_seconds
            if route is not None:
                action=route['decision']['action_k']
                expected=sources[(task_id,'post-full' if definition['family']=='POST-OUTCOME' and action==10 else f'k={action}')]
                if source_id!=expected: raise ValueError('routing source action mismatch')
                paid_events=[routeevents[i] for i in route['event_ids']]
                if len(paid_events)!=2: raise ValueError('routing and payload paid events required')
                if paid_events:
                    if {e.role for e in paid_events}!={'routing','payload'} or any(e.task_id!=task_id for e in paid_events):
                        raise ValueError('routing event identity mismatch')
                    if sum(e.elapsed_seconds for e in paid_events if e.role=='routing')!=route['routing_seconds'] or sum(e.elapsed_seconds for e in paid_events if e.role=='payload')!=route['payload_seconds']:
                        raise ValueError('routing duration mismatch')
                seconds=reconstructed_seconds(definition['family'],definition.get('threshold_mode'),
                           seconds,final_events,route['routing_seconds'],route['payload_seconds'])
                events+=paid_events
            else:
                action=definition.get('k')
                if route_mode=='judge':
                    decision=_read(root/'jobs'/source_id/f'attempt-{p.attempt}'/'decision.json')['decision']
                    action=decision['action_k']
            identity=content_hash([definition['config_id'],task_id,'development-reconstruction'])
            selected.append(replace(p,policy_id=definition['config_id'],job_id=identity,elapsed_seconds=seconds))
            scored.append(replace(s,policy_id=definition['config_id'],job_id=identity,total_serving_seconds=seconds,
                                 total_experiment_seconds=s.total_experiment_seconds+seconds-s.total_serving_seconds))
            events+=all_events
            clean=sum(e.clean_prefill_seconds for e in final_events if e.role=='generation:answer') if definition['family']=='POST-OUTCOME' and action==10 else 0.
            if clean<0 or clean>sum(e.elapsed_seconds for e in final_events if e.role=='generation:answer'):
                raise ValueError('optimistic bound exceeds measured clean full-prefill work')
            bound_seconds.append(seconds-clean)
            detail.append({'task_id':task_id,'action_k':action,'source_prediction_id':source_id,
                           'source_event_ids':[e.event_id for e in all_events],
                           'serving_seconds':seconds,'joint_em':s.joint_em,'answer_em':s.answer_em,
                           'routing_seconds':route['routing_seconds'] if route else None,
                           'payload_seconds':route['payload_seconds'] if route else None,
                           'optimistic_clean_prefill_removed':clean})
        metrics=configuration_metrics(selected,scored,events)
        row={**definition,**metrics,'split':'tune','task_ids':assigned_ids,
             'action_rates':{str(k):sum(d['action_k']==k for d in detail)/len(detail) for k in range(1,11)},
             'per_task':detail,'cost_kind':'direct_source' if route_mode in {'fixed','judge'} else 'development_paid_action_reconstruction'}
        rows.append(row)
        if definition['family']=='POST-OUTCOME':
            bound={k:v for k,v in row.items() if k!='per_task'}
            bound.update(total_serving_seconds=sum(bound_seconds),mean_time=sum(bound_seconds)/len(assigned_ids),
                R=sum(bound_seconds)/row['joint_successes'] if row['joint_successes'] else None,
                executed=False,selection_pool=False,bound_kind='optimistic removal of all measured clean full-call prefill; no cache parity certificate')
            bounds.append(bound)
    for k in range(1,11): make_row({'config_id':f'FIXED-{k}','family':'FIXED','k':k},'fixed')
    make_row({'config_id':'LLM-SUFFICIENCY','family':'LLM-SUFFICIENCY'},'judge')
    for definition in schedule['configurations']: make_row(definition,'policy')
    mandatory={'FIXED','ADAPTIVE-k-tuned','ADAPTIVE-k-published','PRE-OUTCOME-GBM','PRE-LINEAR','PRE-RF','POST-OUTCOME','LLM-SUFFICIENCY','QUERY-ONLY','PROXY-LABEL','SHUFFLED-LABEL-GBM'}
    missing=mandatory-{r['family'] for r in rows}
    if require_roster and missing: raise ValueError('mandatory tuning families unfinished: '+','.join(sorted(missing)))
    anchor=next(r for r in rows if r['config_id']=='FIXED-10')
    result=select_configuration(rows,anchor)
    for bound in bounds: bound['eligible']=bound['Q']>=anchor['Q'] and bound['answer_em']>=anchor['answer_em']
    eligible_bounds=[b for b in bounds if b['eligible']]
    parity=[]
    def signature(p): return (p.raw_output,p.answer,p.citations,p.status,p.prompt_tokens,p.generated_tokens)
    for task_id in assigned_ids:
        small=byjob[sources[(task_id,'k=2')]];post=byjob[sources[(task_id,'post-full')]];full=byjob[sources[(task_id,'k=10')]]
        draft=_read(root/'jobs'/post.job_id/f'attempt-{post.attempt}'/'paid-1.finished.json')['result']
        # Raw paid backend draft has alias citations prior to parsing; raw bytes/token count is the deterministic check.
        parity.append({'task_id':task_id,'post_draft_matches_fixed_two':draft['raw_output']==small.raw_output,
                       'post_full_matches_fixed_ten':signature(post)==signature(full)})
    checks=[]
    rowbyid={r['config_id']:r for r in rows}
    for item in schedule['jobs']:
        if not item['arm'].startswith('direct-check:'): continue
        identity=item['arm'].split(':',1)[1]
        direct=byjob[item['job_id']]
        reconstructed=next(d for d in rowbyid[identity]['per_task'] if d['task_id']==item['task_id'])
        source=byjob[reconstructed['source_prediction_id']]
        checks.append({'task_id':item['task_id'],'config_id':identity,'output_status_parity':signature(direct)==signature(source),
                       'direct_serving_seconds':context.costs(direct)['total_serving_seconds'],
                       'reconstructed_serving_seconds':reconstructed['serving_seconds']})
    result.update(published_adaptive_k=next(r for r in rows if r['family']=='ADAPTIVE-k-published'),
                  post_optimistic_bounds=bounds,
                  best_eligible_post_optimistic_bound=min(eligible_bounds,key=configuration_sort_key) if eligible_bounds else None,
                  deterministic_paid_action_checks=parity,direct_reconstruction_checks=checks,
                  diagnostics_to_freeze={'random_mixture':{'status':'frozen_setting_unexecuted',
                    'escalation_probability':result['A*'].get('fit_escalation_probability'),
                    'probability_source':'selected candidate fit-only training predictions and chosen threshold',
                    'draw_rule':'unsigned256 SHA256 canonical [271828,task_id,random-mixture] / 2**256; choose ten when below p',
                    'selection_pool':False},'shuffled_labels':{'status':'tuned_diagnostic_only','selection_pool':False},
                    'AA_abstain_no_context_oracle':{'status':'future_diagnostic_execution; not selection competitors'}},
                  missing_families=sorted(missing),analysis_seconds=time.perf_counter()-started,
                  physical_run_serving_seconds=sum(context.costs(p)['total_serving_seconds'] for p in predictions),
                  physical_run_experiment_seconds=sum(context.costs(p)['total_experiment_seconds'] for p in predictions),
                  warnings=['Tuning eligibility is an empirical heuristic, not a quality certificate.',
                            'All candidate/comparator costs use measured per-request routing and original paid action costs.',
                            'The optimized POST numerical-parity gate failed; clean-prefill bounds are unexecuted sensitivities.',
                            'Reconstruction replaces source final routing/payload, preserves earlier attempts, and retains shared retrieval exactly once.',
                            'PRE endpoint development costs alias fixed actions; POST endpoints retain paid draft work.'])
    if not all(c['post_draft_matches_fixed_two'] and c['post_full_matches_fixed_ten'] for c in parity):
        raise ValueError('deterministic POST draft/full action parity failed; reconstructed POST thresholds cannot be selected')
    return result


def capture_launch(config_path, stage='tune'):
    """Capture committed execution bytes/settings before any native work."""
    from datetime import datetime, timezone
    from pathlib import Path
    import json
    import shutil
    import subprocess
    from .runner import _digest
    from .storage import atomic_json, content_hash
    if stage not in {'tune','index','analysis'}: raise ValueError('unknown native launch stage')
    config_path=Path(config_path)
    config=json.loads(config_path.read_text())
    relevant=['src','tests','tools','configs','requirements.lock']
    dirty=subprocess.run(['git','status','--porcelain','--',*relevant],check=True,capture_output=True,text=True).stdout
    if dirty: raise ValueError('commit implementation/tests/config before native launch: '+dirty)
    commit=subprocess.run(['git','rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
    window=json.loads(Path('artifacts/provenance/execution-window.json').read_text())
    if (datetime.fromisoformat(window['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()<=3600:
        raise TimeoutError('deadline reporting reserve exhausted')
    prelaunch=Path(config['tuning']['prelaunch_dir']+('' if stage=='tune' else '-'+stage))
    prelaunch.mkdir(parents=True,exist_ok=False)
    snapshot=prelaunch/'source';snapshot.mkdir()
    copied=[*Path('src/outcome_poc').glob('*.py'),Path('tools/task12_native.py'),config_path,
            Path('requirements.lock'),Path(config['inputs']['asset_manifest'])]
    snapshot_hashes={}
    for source in copied:
        destination=snapshot/source;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,destination);snapshot_hashes[str(source)]=_digest(destination)
    paths=list(copied)
    paths += [Path('.venv/lib/python3.12/site-packages/mlx_lm')/p for p in ('generate.py','models/cache.py','models/qwen3.py','tokenizer_utils.py')]
    for origin in (Path(config['training']['output_dir'])/'fit-origin.json',Path(config['tuning']['post_training_dir'])/'fit-origin.json'):
        paths.append(origin)
        data=json.loads(origin.read_text())
        paths += [Path(m['artifact_root'])/m['artifact_file'] for m in data['models'].values()]
    paths += [Path(config['inputs']['prepared_dir'])/'manifest.json']
    for index in (config['tuning']['index_dir'],*config['retrieval']['reuse_indexes_by_split']['tune']):
        root=Path(index)
        if root.exists(): paths += [p for p in root.rglob('*') if p.is_file()]
    binding={'commit':commit,'captured_utc':datetime.now(timezone.utc).isoformat(),'stage':stage,
             'deadline_utc':window['deadline_utc'],'source_snapshot':str(snapshot),
             'sha256':{str(p):_digest(p) for p in paths},'snapshot_sha256':snapshot_hashes,
             'reader_settings':config['reader'],'encoder_settings':config['encoder'],
             'execution_environment':{'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'},
             'candidate_actions':[2,10],'all_fixed_budgets':list(range(1,11)),
             'post_cache_mode':'none','optimized_post_status':'numerical_parity_unresolved_bound_sensitivity_only'}
    if stage=='analysis':
        root=Path(config['tuning']['run_dir'])
        binding['native_source_binding_hash']=json.loads((root/'native-summary.json').read_text())['source_binding_hash']
        binding['closed_native_inputs']={name:_digest(root/name) for name in ('predictions.closed.json','tuning-acquisition.closed.json','schedule.json')}
    atomic_json(prelaunch/'binding.json',binding)
    prepared=Path(config['inputs']['prepared_dir'])
    ids=json.loads((prepared/'manifest.json').read_text())['reservations']['tune']
    checks=sorted(ids,key=lambda i:content_hash([271828,'task12-direct-reconstruction',i]))[:config['tuning']['direct_check_count']]
    plan={'config':str(snapshot/config_path),'run_dir':config['tuning']['run_dir'],'deadline_utc':window['deadline_utc'],
          'binding_path':str(prelaunch/'binding.json'),'source_binding_hash':content_hash(binding),
          'task_ids':ids,'direct_check_ids':checks,'stage':stage,
          'planned_common_jobs':128*12,'planned_common_generation_calls':128*14,
          'direct_checks_are_diagnostics':True}
    atomic_json(prelaunch/'plan.json',plan)
    profile=native_sandbox_profile(Path.cwd(),prepared)
    (prelaunch/'native.sb').write_text(profile)
    atomic_json(Path('artifacts/provenance')/f'task12-{stage}-prelaunch.json',
                {'binding':binding,'source_binding_hash':plan['source_binding_hash'],
                 'plan_sha256':_digest(prelaunch/'plan.json'),'sandbox_sha256':_digest(prelaunch/'native.sb'),
                 'tune_ids_hash':content_hash(ids),'direct_check_ids_hash':content_hash(checks)})
    return {'prelaunch':str(prelaunch),'snapshot':str(snapshot),'plan':plan}


def main(args):
    from pathlib import Path
    import cProfile
    import io
    import json
    import os
    import pstats
    import subprocess
    import sys
    import time
    from .runner import _prediction, validate_closed_accounting
    from .storage import atomic_json, read_jsonl
    config=json.loads(Path(args.config).read_text())
    root=Path(config['tuning']['run_dir'])
    if getattr(args,'analyze_closed',False): return finish_closed_tuning(config,args.config)
    if root.exists(): raise ValueError('tune run already exists; preserve original acquisition')
    if not (Path(config['tuning']['index_dir'])/'manifest.json').exists():
        raise ValueError('completed tune index prerequisite; run index --split tune first')
    launch=capture_launch(args.config)
    prelaunch=Path(launch['prelaunch']);snapshot=Path(launch['snapshot'])
    environment={**os.environ,'PYTHONPATH':str((snapshot/'src').resolve()),
                 'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}
    interpreter=str(Path('.venv/bin/python3.12').absolute())
    command=['/usr/bin/sandbox-exec','-f',str(prelaunch/'native.sb'),interpreter,
             str(snapshot/'tools/task12_native.py'),str(prelaunch/'plan.json')]
    print(json.dumps({'stage':'native-tune-launch','command':command,'source_binding_hash':launch['plan']['source_binding_hash']}),flush=True)
    before=time.perf_counter()
    with (prelaunch/'native.log').open('w') as log:
        process=subprocess.run(command,env=environment,stdout=log,stderr=subprocess.STDOUT)
    native_seconds=time.perf_counter()-before
    if process.returncode: raise RuntimeError('native tune failed; original work retained in '+str(prelaunch/'native.log'))
    print(json.dumps({'stage':'native-tune-closed','seconds':native_seconds}),flush=True)
    return finish_closed_tuning(config,args.config,native_seconds=native_seconds)


def native_sandbox_profile(cwd, prepared):
    from pathlib import Path
    import json
    profile='(version 1)\n(allow default)\n(deny network*)\n'
    for blocked in (prepared/'gold',Path('data/gold'),Path('models/pinned/data')):
        profile+='(deny file-read* (subpath '+json.dumps(str((cwd/blocked).resolve()))+'))\n'
    profile+='(deny file-read* (regex #".*[.]gold[.]jsonl$"))\n'
    return profile


def compact_selection_summary(result):
    """Keep every configuration/metric; store duplicated task/event rows privately."""
    def compact(value):
        if isinstance(value,dict):
            return {k:compact(v) for k,v in value.items()
                    if k not in {'per_task','source_event_ids','deterministic_paid_action_checks'}}
        if isinstance(value,list): return [compact(v) for v in value]
        return value
    public=compact(result)
    public['private_selection_path']='artifacts/runs/task12-tune128-retry/selection.json'
    public['interpretation']='development selection only; no protected sample/generation/freeze'
    return public


def finish_closed_tuning(config, config_path, *, native_seconds=None):
    """Bind current analysis source, validate/seal receipts, then separately score."""
    from pathlib import Path
    import cProfile
    import io
    import json
    import os
    import pstats
    import subprocess
    import time
    from .data_runtime import DocumentStore
    from .runner import _prediction, validate_closed_accounting, seal_legacy_paid_receipts, _read
    from .storage import atomic_json, read_jsonl
    root=Path(config['tuning']['run_dir'])
    if not all((root/n).is_file() for n in ('native-summary.json','predictions.closed.json','tuning-acquisition.closed.json')):
        raise ValueError('analyze-closed requires complete native closure')
    if (root/'scores.jsonl').exists() or (root/'selection.json').exists():
        raise ValueError('closed tuning already scored; preserve original outputs')
    native_summary=_read(root/'native-summary.json')
    marker=_read(root/'predictions.closed.json')
    reservations=_read(Path(config['inputs']['prepared_dir'])/'manifest.json')['reservations']['tune']
    if len(reservations)!=128 or native_summary['assigned_tasks']!=128 or native_summary['assigned_jobs']!=marker['record_count']:
        raise ValueError('complete tune128 assigned native denominator required')
    launch=capture_launch(config_path,'analysis')
    if launch['plan']['task_ids']!=reservations: raise ValueError('tune128 reservation changed')
    prelaunch=Path(launch['prelaunch']);snapshot=Path(launch['snapshot'])
    environment={**os.environ,'PYTHONPATH':str((snapshot/'src').resolve()),
                 'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}
    interpreter=str(Path('.venv/bin/python3.12').absolute())
    predictions=[_prediction(r) for r in read_jsonl(root/'predictions.jsonl')]
    context=validate_closed_accounting(root,predictions)
    seal_seconds=0.
    if context.receipt_coverage=='legacy_unsealed':
        before=time.perf_counter()
        documents=DocumentStore(Path(config['inputs']['prepared_dir'])/'documents.jsonl')
        seal=seal_legacy_paid_receipts(root,predictions,documents=documents,
                                      source_binding_hash=launch['plan']['source_binding_hash'])
        seal_seconds=time.perf_counter()-before
        atomic_json(root/'paid-receipt-seal-cost.json',{'seconds':seal_seconds,'timing_kind':'complete legacy core/content validation and retrospective paid-receipt seal including document-store setup'})
        print(json.dumps({'stage':'legacy-receipts-sealed-before-gold','finished_receipts':seal['finished_receipts_checked'],
                          'crosschecks':len(seal['development_crosschecks']),'seconds':seal_seconds}),flush=True)
    atomic_json(prelaunch/'analysis-started.json',{'native_source_binding_hash':native_summary['source_binding_hash'],
                'analysis_source_binding_hash':launch['plan']['source_binding_hash'],'gold_opened':False})
    # The scoring process has gold permission only after the native run has exited and closed.
    scoring_command=[interpreter,'-m','outcome_poc','score','--run-dir',str(root),
        '--predictions',str(root/'predictions.jsonl'),'--gold',str(Path(config['inputs']['prepared_dir'])/'gold/gold.jsonl'),
        '--documents',str(Path(config['inputs']['prepared_dir'])/'documents.jsonl'),'--output',str(root/'scores.jsonl')]
    with (prelaunch/'scoring.log').open('w') as log:
        subprocess.run(scoring_command,env=environment,stdout=log,stderr=subprocess.STDOUT,check=True)
    # Focused deterministic profile: one whole closed-ledger validation, then O(1) cost lookups.
    predictions=[_prediction(r) for r in read_jsonl(root/'predictions.jsonl')]
    profile=cProfile.Profile();profile.enable()
    context=validate_closed_accounting(root,predictions)
    for prediction in predictions: context.costs(prediction)
    profile.disable()
    stream=io.StringIO();pstats.Stats(profile,stream=stream).sort_stats('cumulative').print_stats(25)
    (root/'accounting-profile.txt').write_text(stream.getvalue())
    result=analyze_tuning(root,launch['plan']['task_ids'],require_roster=config['tuning']['complete_roster_required'])
    result['native_launch_wall_seconds']=native_seconds
    result['unknown_outer_native_wall_reason']=None if native_seconds is not None else 'outer orchestrator intentionally paused/terminated after native exit; native self envelope separately measured'
    result['legacy_receipt_seal_seconds']=seal_seconds
    result['source_binding_hash']=native_summary['source_binding_hash']
    result['analysis_source_binding_hash']=launch['plan']['source_binding_hash']
    result['paid_receipt_coverage']=context.receipt_coverage
    if (root/'paid-receipts.sealed.json').exists():
        result['legacy_receipt_seal']=json.loads((root/'paid-receipts.sealed.json').read_text())
    result['scorer_receipt']=json.loads((root/'scores.jsonl.closed.json').read_text())
    result['native_summary']=json.loads((root/'native-summary.json').read_text())
    atomic_json(root/'selection.json',result)
    # Provenance/table contains IDs, metrics and hashes, never question/document/answer text.
    public=compact_selection_summary(result)
    atomic_json(Path(config['output_dir'])/'task12-selection.json',public)
    print(json.dumps({'A*':result['A*']['config_id'],'B*':result['B*']['config_id'],
                      'configurations':len(result['configurations']),'assigned_tune_tasks':len(launch['plan']['task_ids'])}),flush=True)
    return 0

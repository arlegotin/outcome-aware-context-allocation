"""Independently verify aggregate sums; publish no benchmark text or predictions."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path


def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with Path(p).open() as stream:return [json.loads(v) for v in stream]
def identity(p):
    b=Path(p).read_bytes()
    return {'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
def inventory(p):return {str(f.relative_to(p)):identity(f) for f in sorted(p.rglob('*')) if f.is_file() and '__pycache__' not in f.parts}
def canonical_hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def seconds(v):return (v['stop_ns']-v['start_ns'])/1e9
def percentile(v,p):
    v=sorted(v);x=(len(v)-1)*p;a,b=math.floor(x),math.ceil(x)
    return v[a]+(v[b]-v[a])*(x-a)


def build(root,audit):
    plan,summary=read(root/'plan.json'),read(root/'scores/summary.json')
    closure=read(root/'scores/closed.json')
    for n,i in closure['files'].items():
        if identity(root/'scores'/n)!=i:raise ValueError('score closure changed')
    scored,schedule=rows(root/'scores/scores.jsonl'),read(root/'schedule.json')
    if len(scored)!=128 or {r['job_id'] for r in scored}!={j['job_id'] for j in schedule} or len({r['task_id'] for r in scored})!=64:
        raise ValueError('entire exact128-call/64-question assignment required')
    arms={}
    for arm in ('baseline','evidence-first'):
        values=[r for r in scored if r['arm']==arm]
        S,E=sum(r['joint_em'] for r in values),sum(r['answer_em'] for r in values)
        total=sum(r['seconds'] for r in values)
        actual={'n':len(values),'strict_successes':S,'answer_successes':E,'Q':S/64,'mean_T':total/64,
                'total_T':total,'R':total/S if S else None,'R_reason':None if S else 'zero_successes',
                'statuses':dict(sorted(Counter(r['status'] for r in values).items()))}
        if actual!=summary['arms'][arm]:raise ValueError('independent aggregate/ratio verification failed')
        arms[arm]={**actual,**{k:sum(r[k] for r in values)/64 for k in ('answer_f1','support_f1','support_precision','support_recall')},
            'support_em_count':sum(r['support_em'] for r in values),
            'missing_reference_supports_total':sum(r['missing_reference_supports'] for r in values),
            'excess_reference_citations_total':sum(r['excess_reference_citations'] for r in values),
            'correct_answer_without_strict_success':sum(bool(r['answer_em'] and not r['joint_em']) for r in values),
            'p95_seconds':percentile([r['seconds'] for r in values],.95),'p99_seconds':percentile([r['seconds'] for r in values],.99),
            'max_seconds':max(r['seconds'] for r in values),'input_tokens':sum(r['prompt_tokens'] for r in values),
            'output_tokens':sum(r['generated_tokens'] for r in values)}
    by_cell={(r['task_id'],r['arm']):r for r in scored}
    ids={r['task_id'] for r in scored}
    for g in summary['reader_validation']['quality_guards']:
        endpoint=g['metric'];a=[by_cell[i,'evidence-first'][endpoint] for i in ids];b=[by_cell[i,'baseline'][endpoint] for i in ids]
        if sum(x and not y for x,y in zip(a,b))!=g['rescue_count'] or sum(y and not x for x,y in zip(a,b))!=g['harm_count']:
            raise ValueError('question-level discordance verification failed')
    envelopes={k:rows(root/p) for k,p in [('preparation','preparation-attempts.jsonl'),('index','setup-attempts.jsonl'),
               ('launch','launches.jsonl'),('scoring','scoring-attempts.jsonl')]}
    envelopes['preflight']=[read(p) for p in sorted(audit.glob('preflight*.json'))]
    intervals=sorted((v['start_ns'],v['stop_ns']) for values in envelopes.values() for v in values)
    if any(a>b for a,b in intervals) or any(b>c for (_,b),(c,_) in zip(intervals,intervals[1:])):
        raise ValueError('invalid/overlapping envelopes; no double addition')
    costs={k+'_seconds':sum(seconds(v) for v in values) for k,values in envelopes.items()}
    costs.update(observed_disjoint_seconds=sum(costs.values()),nested_resident_seconds=summary['costs']['resident_session_seconds'],
        nested_service_seconds=sum(v['seconds'] for v in scored),project_engineering_tests_and_historical_seconds=None,
        attributable_incremental_adaptation_seconds=None,break_even_queries=None,
        scope='Preparation/index/launch/scoring/preflight envelopes only; resident, service, warmup, forecasts and paid admissions are nested. Unknown project costs are not zero.')
    stage=root/'stages/natural';forecast=read(stage/'render-forecast.json')
    monitor=rows(stage/'resources.jsonl');gates=rows(stage/'memory-gates.jsonl')+rows(stage/'paid-memory-gates.jsonl')
    swap=[v['swap_used_bytes'] for v in monitor if v['swap_used_bytes'] is not None]
    resources={'all_memory_gates_pass':all(v['passed'] for v in gates),'memory_gate_count':len(gates),
        'resource_samples':len(monitor),'unavailable_resource_samples':sum('unavailable' in v for v in monitor),
        'maximum_conservative_overlapping_working_set_bytes':max(v['working_set_bytes'] for v in gates),
        'reserve_bytes':gates[0]['reserve_bytes'],'limit_bytes':gates[0]['limit_bytes'],
        'system_swap_range_bytes':[min(swap),max(swap)] if swap else None,
        'scope':'Observed sampled maxima only; missing background samples stay unavailable, never zero; admission gates recorded separately.'}
    warmup=read(stage/'warmup/result.json')['result']
    if warmup['status']!='ok' or warmup['answer']!='violet light' or warmup['citations']!=[['D0',0]]:
        raise ValueError('actual authored warmup did not answer/cite correctly')
    result={'protocol_id':plan['config']['protocol_id'],'assigned_questions':64,'assigned_calls':128,
        'population':summary['population'],'arms':arms,'reader_validation':summary['reader_validation'],
        'registered_endpoint_results':{g['metric']:{'difference':g['difference'],'ci':g['ci'],
            'positive_lower_bound':g['ci'][0]>0,'rescues':g['rescue_count'],'harms':g['harm_count']}
            for g in summary['reader_validation']['quality_guards'] if g['comparator']=='selected'},
        'claims':summary['claims'],'costs':costs,'resources':resources,'prompt_forecast':{k:v for k,v in forecast.items() if k!='jobs'},
        'operational_requirements':None,'semantic_validity':'Unresolved; no Gold repair or replacement semantic endpoint'}
    result['qualitative_review']=read(audit/'blind-review-summary.json')
    source_inventory=inventory(root/'source')
    if canonical_hash(source_inventory)!=summary['source_snapshot_hash']:raise ValueError('measured source inventory differs')
    names=['plan.json','cohorts.json','selection-frozen.json','schedule.json','config.json','prompt-conditions.json','precision.json',
        'source.diff','preparation-attempts.jsonl','setup-attempts.jsonl','launches.jsonl','scoring-attempts.jsonl',
        'index-setup/index-seal.json','index-setup/index/manifest.json','index-setup/index-attempts.jsonl',
        'stages/natural/closed.json','scores/closed.json','scores/scores.jsonl','scores/summary.json']
    manifest={'generated_utc':datetime.now(timezone.utc).isoformat(),'base_commit':plan['source_commit'],
        'plan_hash':plan['plan_hash'],'source_snapshot_hash':summary['source_snapshot_hash'],'source_files':source_inventory,
        'files':{n:identity(root/n) for n in names},'audit_files':inventory(audit),
        'data_and_reservation_identities':read(root/'selection-frozen.json'),'gold_identity':plan['gold_input']['identity'],
        'assets':read(root/'assets.json'),'clock':plan['freeze'],'environment':plan['environment'],
        'reserved_final_questions':128,'authored_prompt_examples':read(root/'prompt-conditions.json'),
        'native_denials':read(stage/'denials.json'),'native_controlled_suspend':'not performed',
        'known_answer_native_warmup':'passed single authored baseline question; not reader quality validation',
        'aggregate_verification':'Independent all128 row sums/ratios, assignment and paired rescue/harm counts; no cached scorer return',
        'publication_scope':'Aggregates/hashes/authored examples only; raw text, Gold, predictions, reserved IDs and model files private',
        'script_identity':identity(Path(__file__)),
        'post_run_delivery_source_files':inventory(Path(__file__).resolve().parents[2]/'src/outcome_poc'),
        'post_run_delivery_test_files':inventory(Path(__file__).resolve().parents[2]/'tests'),
        'reservation_catalog_identity':identity(Path(__file__).resolve().parents[2]/'experiments/reservation-manifests.json'),
        'post_run_note':'Delivered preparation-only reservation guard was added after validation; measured frozen source and gate stay unchanged.',
        'private_human_adjudication_packet':identity(root/'human-adjudication-packet.json')}
    return result,manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--audit-dir',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True,help='new aggregate-only directory; never overwrite')
    a=p.parse_args();results,manifest=build(a.root,a.audit_dir)
    a.output_dir.mkdir(parents=True,exist_ok=False)
    for n,v in [('results.json',results),('evidence-manifest.json',manifest)]:
        (a.output_dir/n).write_text(json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+'\n')
    (a.output_dir/'closed.json').write_text(json.dumps({n:identity(a.output_dir/n) for n in ('results.json','evidence-manifest.json')},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'assigned_calls':128,'admitted':results['reader_validation']['admitted'],'claims':results['claims']}))


if __name__=='__main__':main()

"""NEW read-only complete v4 diagnostics. Load the run's frozen source via PYTHONPATH.

Fresh actual-Scorer rescore is a separate command. This tool recomputes the
prospective action screen and aggregates without mutating retained run evidence.
Its output directory must remain PRIVATE: frontier witnesses include choices
aligned to private cohort order. Strip choices recursively for public aggregates.
"""
import argparse
from collections import Counter
import json,math,sys
from pathlib import Path
sys.dont_write_bytecode=True
import numpy as np


def analyze(root,output):
    from outcome_poc.reader_recovery.scoring import closed_records
    from outcome_poc.reader_recovery.study import read,identity,publish,verify_files
    from outcome_poc.reader_recovery.action_analysis_v4 import action_value_screen
    from outcome_poc.reader_probe.study import inventory
    from outcome_poc.schemas import PairedActionRow
    from outcome_poc.storage import content_hash,read_jsonl
    from outcome_poc.statistics import paired_quality_bounds
    root=Path(root).resolve(strict=True);output=Path(output).resolve()
    metadata=read(root/'plan.json')
    retained={root,Path(__file__).resolve().parents[1],Path(metadata['config']['historical_checkout']).resolve(),
              *(Path(p).resolve() for p in metadata['denied_paths'])}
    if any(p.is_relative_to(output) or output.is_relative_to(p) for p in retained):raise ValueError('fresh diagnostics output overlaps retained roots')
    if output.exists():raise ValueError('fresh diagnostics output required')
    before=inventory(root);plan,records=closed_records(root)
    if plan['config']['purpose']!='action-headroom':raise ValueError('explicit completed action-headroom study required')
    closure=read(root/'scores/closed.json');summary=read(root/'scores/summary.json')
    if closure['plan_hash']!=plan['plan_hash'] or closure['assigned_jobs']!=len(records):raise ValueError('score closure assignment drift')
    verify_files({str(root/'scores'/n):v for n,v in closure['files'].items()})
    rows=list(read_jsonl(root/'scores/scores.jsonl'))
    if len(rows)!=len(records) or {r['job_id'] for r in rows}!={j['job_id'] for j,_,_ in records}:raise ValueError('incomplete score roster')
    cells={(r['task_id'],r['arm']):r for r in rows};ids=read(root/'cohorts.json')['development'];N=read(root/'cohorts.json')['eligibility_count']
    tasks={t['task_id']:t for t in read_jsonl(root/'tasks.jsonl')}
    paired=[PairedActionRow(task_id=i,question=tasks[i]['question'],ranked_documents=[],features={},
        small_prediction_id=cells[i,'2']['job_id'],full_prediction_id=cells[i,'10']['job_id'],
        small_joint_em=cells[i,'2']['joint_em'],full_joint_em=cells[i,'10']['joint_em'],
        small_answer_em=cells[i,'2']['answer_em'],full_answer_em=cells[i,'10']['answer_em'],
        small_event_ids=[],full_event_ids=[],small_cost_seconds=cells[i,'2']['seconds'],full_cost_seconds=cells[i,'10']['seconds'],
        small_status=cells[i,'2']['status'],full_status=cells[i,'10']['status']) for i in ids]
    screen=action_value_screen(paired,summary['arms'],plan['config']['research_screen'])
    if screen!=summary['action_value_screen']:raise ValueError('fresh prospective screen recomputation differs')
    roster=read(root/'schedule.json');report={'plan_hash':plan['plan_hash'],'source_snapshot_hash':plan['source_snapshot_hash'],
        'assigned_questions':len(ids),'assigned_jobs':len(rows),'N':N,'action_value_screen':screen,'arms':{},'paired':{}}
    for arm in ('2','5','10'):
        values=[cells[j['task_id'],arm] for j in roster if j['arm']==arm];times=np.array([r['seconds'] for r in values]);n=len(values)
        S=sum(r['joint_em'] for r in values);E=sum(r['answer_em'] for r in values);total=math.fsum(times);old=summary['arms'][arm]
        if S!=old['strict_successes'] or E!=old['answer_successes'] or not math.isclose(total,old['total_T'],rel_tol=1e-12):raise ValueError('independent sums differ')
        report['arms'][arm]={'n':n,'E':E,'S':S,'Q':S/n,'total_T':total,'mean_T':total/n,'R_descriptive':total/S if S else None,
            'statuses':dict(Counter(r['status'] for r in values)),
            'p50_T':float(np.quantile(times,.5)),'p95_T':float(np.quantile(times,.95)),'p99_T':float(np.quantile(times,.99)),
            'maximum_T':float(times.max()),'first_half_mean_T':float(times[:n//2].mean()),'second_half_mean_T':float(times[n//2:].mean()),
            'max_absolute_continuous_active_drift':max(abs(r['drift_seconds']) for r in values)}
    for a,b in (('10','2'),('5','10')):
        report['paired'][a+'-minus-'+b]={}
        for endpoint in ('joint_em','answer_em'):
            x=np.array([cells[i,a][endpoint] for i in ids]);y=np.array([cells[i,b][endpoint] for i in ids]);table=Counter(zip(x,y))
            report['paired'][a+'-minus-'+b][endpoint]={'both_success':table[1,1],'rescues':table[1,0],'harms':table[0,1],'both_fail':table[0,0],
                'diagnostic_bounds_alpha_tail_0125':paired_quality_bounds(x,y,N,.0125)}
    resource=list(read_jsonl(root/'stages/natural/resources.jsonl'))
    gates=list(read_jsonl(root/'stages/natural/memory-gates.jsonl'))+list(read_jsonl(root/'stages/natural/paid-memory-gates.jsonl'))
    report['resources']={k:{'min':min(r[k] for r in resource if r.get(k) is not None),'max':max(r[k] for r in resource if r.get(k) is not None)}
        for k in ('rss_parent_bytes','rss_children_bytes','swap_used_bytes') if any(r.get(k) is not None for r in resource)}
    report['resources'].update(all_registered_gates_passed=bool(gates) and all(r['passed'] for r in gates),samples=len(resource))
    report['costs']={**summary['costs'],'complete_index_invocation_seconds':read(root/'index-supervision/complete.json')['seconds']}
    report['limits']={'allocation_efficiency_claim':False,'operational_claim':False,'semantic_human_review':'unavailable',
        'timing_repetitions':1,'controlled_suspension_test':'unperformed','service_requirements':None,
        'interpretation':'finite development oracle screen; no held-out learned policy or eligible efficiency interval',
        'adaptation_total':'engineering/human-review/historical costs unknown; no operational break-even'}
    report['identities']={n:identity(root/n) for n in ('plan.json','cohorts.json','schedule.json','selection-frozen.json','assets.json','scores/scores.jsonl','scores/closed.json','stages/natural/closed.json','native-parent-closure.json','index-supervision/complete.json')}
    if inventory(root)!=before:raise ValueError('read-only diagnostics changed retained run')
    report.update(input_inventory_hash=content_hash(before),retained_inputs_unchanged=True,tool_identity=identity(Path(__file__)))
    output.mkdir(parents=True,exist_ok=False);publish(output/'analysis.json',report)
    return {k:report[k] for k in ('assigned_questions','arms','paired')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(analyze(args.root,args.output),allow_nan=False))

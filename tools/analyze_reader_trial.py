"""NEW read-only diagnostics after a complete, sealed paired reader trial.

Use PYTHONPATH=<run>/source/src and the pinned interpreter. No partial scoring,
Gold correction, inference, threshold selection or allocation acceptance occurs.
Output includes only allowed aggregate metrics and byte identities.
"""
import argparse
from collections import Counter
import json,math,sys
sys.dont_write_bytecode=True
from pathlib import Path
import numpy as np


def analyze(root,output):
    from outcome_poc.reader_recovery.scoring import closed_records
    from outcome_poc.reader_recovery.study import read,identity,publish,verify_files
    from outcome_poc.reader_recovery.analysis import validation_admission
    from outcome_poc.reader_probe.study import inventory
    from outcome_poc.storage import read_jsonl,content_hash
    from outcome_poc.statistics import paired_quality_bounds
    root=Path(root).resolve(strict=True);output=Path(output).resolve()
    metadata=read(root/'plan.json')
    retained={root,Path(__file__).resolve().parents[1],Path(metadata['config']['historical_checkout']).resolve(),
              *(Path(p).resolve() for p in metadata['denied_paths'])}
    for parent in retained:
        if parent.is_relative_to(output) or output.is_relative_to(parent):raise ValueError('analysis must not overlap retained source/evidence')
    if output.exists():raise ValueError('fresh analysis output required')
    before=inventory(root);plan,records=closed_records(root)
    closure=read(root/'scores/closed.json')
    if closure['plan_hash']!=plan['plan_hash'] or closure['assigned_jobs']!=len(records):raise ValueError('score assignment closure mismatch')
    verify_files({str(root/'scores'/n):v for n,v in closure['files'].items()})
    rows=list(read_jsonl(root/'scores/scores.jsonl'));summary=read(root/'scores/summary.json')
    if {r['job_id'] for r in rows}!={j['job_id'] for j,_,_ in records} or len(rows)!=len(records):raise ValueError('complete score roster mismatch')
    cells={(r['task_id'],r['arm']):r for r in rows};ids=sorted({r['task_id'] for r in rows});N=read(root/'cohorts.json')['eligibility_count']
    admission=validation_admission(rows,N)
    if admission!=summary['reader_validation']:raise ValueError('independent admission recomputation differs')
    roster=read(root/'schedule.json');ordered={a:[cells[j['task_id'],a] for j in roster if j['arm']==a] for a in summary['arms']}
    report={'plan_hash':plan['plan_hash'],'source_snapshot_hash':plan['source_snapshot_hash'],
            'assigned_questions':len(ids),'assigned_jobs':len(rows),'N':N,'reader_admission':admission,'arms':{},'paired':{}}
    for arm,values in ordered.items():
        times=np.array([r['seconds'] for r in values]);S=sum(r['joint_em'] for r in values);E=sum(r['answer_em'] for r in values)
        total=math.fsum(times);n=len(values);expected=summary['arms'][arm]
        if S!=expected['strict_successes'] or E!=expected['answer_successes'] or not math.isclose(total,expected['total_T'],rel_tol=1e-12):raise ValueError('independent aggregate mismatch')
        report['arms'][arm]={'n':n,'E':E,'S':S,'Q':S/n,'total_T':total,'mean_T':total/n,'R_descriptive':total/S if S else None,
            'statuses':dict(Counter(r['status'] for r in values)),
            'support_set_EM':sum(r['support_em'] for r in values)/n,
            'mean_answer_F1':math.fsum(r['answer_f1'] for r in values)/n,
            'mean_support_precision':math.fsum(r['support_precision'] for r in values)/n,
            'mean_support_recall':math.fsum(r['support_recall'] for r in values)/n,
            'mean_support_F1':math.fsum(r['support_f1'] for r in values)/n,
            'p50_T':float(np.quantile(times,.5)),'p95_T':float(np.quantile(times,.95)),'p99_T':float(np.quantile(times,.99)),
            'maximum_T':float(times.max()),'first_half_mean_T':float(times[:n//2].mean()),'second_half_mean_T':float(times[n//2:].mean()),
            'max_absolute_continuous_active_drift':max(abs(r['drift_seconds']) for r in values)}
    for endpoint in ('joint_em','answer_em'):
        a=[cells[i,'evidence-first'][endpoint] for i in ids];b=[cells[i,'baseline'][endpoint] for i in ids]
        table=Counter((x,y) for x,y in zip(a,b))
        report['paired'][endpoint]={'both_success':table[1,1],'rescues':table[1,0],'harms':table[0,1],'both_fail':table[0,0],
            'exact_existing_bounds':paired_quality_bounds(np.array(a),np.array(b),N,.003125)}
    resources=list(read_jsonl(root/'stages/natural/resources.jsonl'))
    report['resources']={key:{'min':min(r[key] for r in resources if r.get(key) is not None),'max':max(r[key] for r in resources if r.get(key) is not None)}
        for key in ('rss_parent_bytes','rss_children_bytes','swap_used_bytes') if any(r.get(key) is not None for r in resources)}
    gates=list(read_jsonl(root/'stages/natural/memory-gates.jsonl'))+list(read_jsonl(root/'stages/natural/paid-memory-gates.jsonl'))
    report['resources']['all_registered_gates_passed']=bool(gates) and all(r['passed'] for r in gates)
    report['resources']['memory_samples']=len(resources)
    first={arm:[] for arm in ordered};second={arm:[] for arm in ordered}
    for offset in range(0,len(roster),2):
        for index,target in ((offset,first),(offset+1,second)):
            j=roster[index];target[j['arm']].append(cells[j['task_id'],j['arm']]['seconds'])
    report['order_diagnostics']={arm:{'first_in_pair_mean_T':math.fsum(first[arm])/len(first[arm]),
        'second_in_pair_mean_T':math.fsum(second[arm])/len(second[arm])} for arm in ordered}
    report['costs']=summary['costs']
    report['limits']={'allocation_efficiency_claim':False,'operational_claim':False,'semantic_adjudication':'unavailable',
        'timing_repetitions':1,'deterministic_repeat_assumption':'not independently tested; no efficiency inference',
        'controlled_suspend_test':'unperformed','service_requirements':None,
        'stationarity_and_order':'descriptive diagnostics only; no preplanned trend test or causal attribution',
        'forecast':'shared prospective safety forecasting outside warm requests is included in the resident envelope',
        'adaptation_total':'engineering, human review and historical adaptation cost unknown; no break-even claim'}
    report['identities']={n:identity(root/n) for n in ('plan.json','cohorts.json','schedule.json','selection-frozen.json','assets.json','scores/scores.jsonl','scores/closed.json','stages/natural/closed.json','native-parent-closure.json')}
    if inventory(root)!=before:raise ValueError('read-only diagnostics changed retained inputs')
    report['input_inventory_hash']=content_hash(before);report['retained_inputs_unchanged']=True
    output.mkdir(parents=True,exist_ok=False);publish(output/'analysis.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(analyze(args.root,args.output),allow_nan=False))

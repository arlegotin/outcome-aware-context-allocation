"""Predeclared paired finite-population efficacy and descriptive cost analysis."""
from collections import Counter
import numpy as np
from ..statistics import paired_quality_bounds


def summarize(rows,stage,population_N):
    arms=('2','10','support-documents') if stage=='diagnosis' else ('2','10')
    if stage not in {'diagnosis','comparison'} or not rows:raise ValueError('empty/unknown stage')
    by={}
    for row in rows:
        key=(row['task_id'],row['prompt_condition'],row['arm'],row['repetition'])
        if key in by or row['repetition']!=0:raise ValueError('duplicate/unplanned observation')
        by[key]=row
    ids=sorted({r['task_id'] for r in rows})
    expected={(i,c,a,0) for i in ids for c in ('baseline','chain') for a in arms}
    if set(by)!=expected:raise ValueError('incomplete assigned factorial observations')
    cells={};paired={}
    for c in ('baseline','chain'):
        for a in arms:
            group=[by[i,c,a,0] for i in ids];seconds=[r['seconds'] for r in group]
            successes=sum(r['joint_em'] for r in group);total=sum(seconds)
            cell={'n':len(group),'counts':{k:sum(r[k] for r in group) for k in ('joint_em','answer_em','support_em')},
                'means':{k:float(np.mean([r[k] for r in group])) for k in ('joint_em','answer_em','support_em','joint_f1','answer_f1','support_f1','support_precision','support_recall')},
                'total_seconds':total,'mean_seconds':float(np.mean(seconds)),
                'p50_seconds':float(np.quantile(seconds,.5)),'p95_seconds':float(np.quantile(seconds,.95)),
                'seconds_per_strict_success':total/successes if successes else None,
                'ratio_reason':None if successes else 'zero strict successes; all assigned work retained',
                'ratio_display':str(total/successes) if successes else '∞',
                'calls':sum(r['calls'] for r in group),'prompt_tokens':sum(r['prompt_tokens'] for r in group),
                'generated_tokens':sum(r['generated_tokens'] for r in group),
                'statuses':dict(sorted(Counter(r['status'] for r in group).items())),
                'failures':sum(r['status']!='ok' for r in group),'abstentions':sum(r['status']=='abstain' for r in group),
                'empty':sum(r['empty'] for r in group),'truncated':sum(r['truncated'] for r in group)}
            cells[c+'/'+a]=cell
    for arm in arms:
        b=[by[i,'baseline',arm,0] for i in ids];c=[by[i,'chain',arm,0] for i in ids]
        pair={}
        for metric in ('joint_em','answer_em','support_em'):
            x=np.array([r[metric] for r in c]);y=np.array([r[metric] for r in b])
            bounds=paired_quality_bounds(x,y,population_N,.00625 if metric=='answer_em' and arm!='support-documents' else .0125)
            bounds.pop('preserved',None)
            bounds.update(both_success=int(((x==1)&(y==1)).sum()),neither_success=int(((x==0)&(y==0)).sum()),
                          difference_percentage_points=100*bounds['difference'],
                          ci_percentage_points=[100*v for v in bounds['ci']],
                          interpretation='conservative finite-population union-bound interval; no preservation inference')
            pair[metric]=bounds
        deltas=[x['seconds']-y['seconds'] for x,y in zip(c,b)]
        pair['time_change']={'mean_seconds':float(np.mean(deltas)),'p50_seconds':float(np.quantile(deltas,.5)),
            'interpretation':'paired descriptive service difference; shared session overhead not attributed'}
        paired[arm]=pair
    drift=[r['drift_seconds'] for r in rows]
    ordered=sorted(rows,key=lambda r:r['ordinal']);half=len(rows)//2
    timing={'max_absolute_drift_seconds':max(abs(v) for v in drift),'total_drift_seconds':sum(drift),
        'unstable':any(abs(r['drift_seconds'])>max(.1,.01*r['seconds']) for r in rows),
        'first_half_mean_seconds':float(np.mean([r['seconds'] for r in ordered[:half]])),
        'last_half_mean_seconds':float(np.mean([r['seconds'] for r in ordered[half:]])),
        'condition_order_counts':dict(Counter('chain_first' if by[i,'chain',a,0]['ordinal']<by[i,'baseline',a,0]['ordinal'] else 'baseline_first' for i in ids for a in arms)),
        'interpretation':'one timing repetition; drift threshold is a descriptive flag, no stationarity or efficiency claim'}
    return {'stage':stage,'population_N':population_N,'assigned_observations':len(rows),'assigned_unique_questions':len(ids),
        'cells':cells,'paired':paired,'primary':'natural10 joint_em chain minus baseline' if stage=='comparison' else None,
        'secondary':'natural2 and all diagnosis/control endpoints','timing_health':timing,
        'interpretation':'Costs descriptive. No quality preservation, routing, business or efficiency inference.'}

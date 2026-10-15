"""Aggregate-only analysis; no annotations or serving imports."""
from collections import defaultdict
import math


def percentile(values, fraction):
    values=sorted(values)
    return values[min(len(values)-1,math.ceil(fraction*len(values))-1)] if values else None


def frontier(rows, metric):
    """Clairvoyant empirical binary-success frontier across measured 2/5/10."""
    grouped=defaultdict(list)
    for row in rows:
        if row['arm'] in {'2','5','10'}:
            grouped[row['task_id']].append(row)
    if any({r['arm'] for r in group}!={'2','5','10'} or len(group)!=3 for group in grouped.values()):
        raise ValueError('frontier requires all three actions once per question')
    cost=0.; successes=0; increments=[]
    for task_id,group in grouped.items():
        cheapest=min(group,key=lambda r:(r['seconds'],-r[metric],r['arm']))
        cost+=cheapest['seconds']; successes+=cheapest[metric]
        if not cheapest[metric]:
            successful=[r for r in group if r[metric]]
            if successful:
                increments.append((min(r['seconds'] for r in successful)-cheapest['seconds'],task_id))
    def point():
        return {'successes':successes,'questions':len(grouped),'seconds':cost,
                'cost_per_success':cost/successes if successes else None}
    points=[point()]
    for increment,_ in sorted(increments):
        cost+=increment;successes+=1;points.append(point())
    return points


def summarize(rows, *, repeated=False):
    arms=defaultdict(list)
    for row in rows: arms[row['arm']].append(row)
    result={}
    for arm,group in sorted(arms.items()):
        n=len(group); times=[r['seconds'] for r in group]; seconds=sum(times)
        joint=sum(r['joint_em'] for r in group); answer=sum(r['answer_em'] for r in group)
        result[arm]={'observations':n,'unique_questions':len({r['task_id'] for r in group}),
          **{key:sum(r[key] for r in group)/n for key in ('answer_em','support_em','support_f1','joint_em')},
          'joint_successes':joint,'answer_successes':answer,'seconds':seconds,
          'mean_seconds':seconds/n,'p50_seconds':percentile(times,.5),'p95_seconds':percentile(times,.95),
          'cost_per_joint_success':seconds/joint if joint else None,
          'cost_per_answer_success':seconds/answer if answer else None,
          'zero_success_reason':None if joint else 'zero supported successes across all assigned observations',
          'correct_answer_wrong_support':sum(r['status']=='ok' and r['answer_em'] and not r['support_em'] for r in group),
          'correct_answer_invalid_output':sum(r['status']!='ok' and r['answer_em'] for r in group),
          'reference_support_documents_present':sum(r.get('reference_support_documents_present',False) for r in group),
          'invalid':sum(r['status'] in {'parse_error','invalid_citation'} for r in group),
          'empty':sum(r['empty'] for r in group),'truncated':sum(r['truncated'] for r in group),
          'statuses':{s:sum(r['status']==s for r in group) for s in sorted({r['status'] for r in group})},
          'prompt_tokens':sum(r['prompt_tokens'] for r in group),'generated_tokens':sum(r['generated_tokens'] for r in group),
          'calls':sum(r['calls'] for r in group)}
    paired={}
    if not repeated:
        by_id=defaultdict(dict)
        for r in rows: by_id[r['task_id']][r['arm']]=r
        for left in sorted(arms):
            for right in sorted(arms):
                if left>=right:continue
                paired[f'{left}->{right}']={f'{a}{b}':sum(r[left]['joint_em']==a and r[right]['joint_em']==b for r in by_id.values())
                                           for a,b in ((0,0),(0,1),(1,0),(1,1))}
    drift=[r.get('drift_seconds',0.) for r in rows]
    # A prospective conservative health flag; never adjust elapsed values after collection.
    repeat_ratios=[]
    if repeated:
        repeated_groups=defaultdict(list)
        for r in rows:repeated_groups[(r['task_id'],r['arm'])].append(r['seconds'])
        repeat_ratios=[max(values)/min(values) for values in repeated_groups.values() if len(values)==2 and min(values)>0]
    unstable=any(abs(d)>.25 for d in drift) or any(r>2. for r in repeat_ratios)
    return {'arms':result,'joint_harm_rescue_cells':paired,
       'joint_frontier':None if repeated else frontier(rows,'joint_em'),
       'answer_only_diagnostic_frontier':None if repeated else frontier(rows,'answer_em'),
       'timing_health':{'continuous_minus_active_seconds':sum(drift),'max_drift_seconds':max(drift,default=0.),
          'sleep_or_drift_flag':any(abs(d)>.25 for d in drift),
          'calibration_repeat_ratio_max':max(repeat_ratios,default=None),
          'calibration_repeat_ratio_median':percentile(repeat_ratios,.5),
          'health_rule':'absolute continuous-active drift >0.25s or calibration repeat max/min >2; raw times unchanged',
          'unstable':unstable,'cost_comparisons':'unresolved' if unstable else 'development descriptive only'},
       'claims':'development diagnosis; no quality preservation, production uncertainty or superiority claim'}

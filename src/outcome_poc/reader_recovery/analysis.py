"""Descriptive diagnostic summaries cannot confer an allocation/efficiency claim."""
from collections import Counter
import math


def validation_admission(rows,N):
    from ..statistics import quality_guards
    ids = sorted({r['task_id'] for r in rows})
    cells = {(r['task_id'],r['arm']):r for r in rows}
    if len(cells)!=len(rows) or set(cells)!={(i,a) for i in ids for a in ('baseline','evidence-first')}:
        raise ValueError('complete paired validation required')
    guards = quality_guards([{f'{role}_{endpoint}':cells[i,arm][endpoint]
        for role,arm in (('candidate','evidence-first'),('comparator','baseline'),('fixed_ten','baseline'))
        for endpoint in ('joint_em','answer_em')} for i in ids],N)
    strict_lower = guards[0]['ci'][0]
    failures = {a:sum(cells[i,a]['status'] not in {'ok','abstain'} for i in ids) for a in ('baseline','evidence-first')}
    admitted = strict_lower>0 and all(g['preserved'] for g in guards) and failures['evidence-first']<=failures['baseline']
    return {'admitted':bool(admitted),'strict_lower_bound':strict_lower,'quality_guards':guards,
            'strict_benchmark_quality_improvement':bool(admitted),'cost_acceptability':None,'reader_improvement_claim':False,
            'invalid_or_runtime_failures':failures,'comparator':'unchanged natural-ten; selected and fixed-ten alias',
            'semantic_validity':'unresolved; strict benchmark admission is not semantic/operational certification',
            'efficiency_claim':False}


def summarize(rows):
    if not rows:
        raise ValueError('empty assigned diagnosis')
    arms = {}
    for arm in sorted({r['arm'] for r in rows}):
        values = [r for r in rows if r['arm'] == arm]
        if len({r['task_id'] for r in values}) != len(values):
            raise ValueError('repetitions cannot be treated as extra questions')
        if any(type(r['seconds']) not in (int,float) or not math.isfinite(r['seconds']) or r['seconds'] < 0 or
               type(r['joint_em']) is not int or r['joint_em'] not in (0,1) or
               type(r['answer_em']) is not int or r['answer_em'] not in (0,1) for r in values):
            raise ValueError('invalid diagnostic observation')
        successes = sum(r['joint_em'] for r in values)
        total = sum(r['seconds'] for r in values)
        arms[arm] = {'n':len(values),'strict_successes':successes,'answer_successes':sum(r['answer_em'] for r in values),
                     'Q':successes/len(values),'mean_T':total/len(values),'total_T':total,
                     'R':total/successes if successes else None,'R_reason':None if successes else 'zero_successes',
                     'statuses':dict(sorted(Counter(r['status'] for r in values).items()))}
    if len({tuple(sorted(r['task_id'] for r in rows if r['arm']==a)) for a in arms}) != 1:
        raise ValueError('diagnostic arms have different assigned populations')
    return {'arms':arms,'timing_scope':'descriptive warm request through durable payload; all assigned failures included',
            'claims':{'reader_improvement':False,'allocation_improvement':False,'operational_usefulness':False}}

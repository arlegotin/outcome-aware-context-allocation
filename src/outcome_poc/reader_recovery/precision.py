"""Prospective joint admission forecasts under explicit finite-frame assumptions.

Each cell couples E, S and invalid/runtime failure in both arms. Simulated draws
are not benchmark questions. Every draw uses the existing exact interval rule;
Monte Carlo uncertainty is disclosed separately from uncertainty about scenarios.
"""
import math
import numpy as np
from ..statistics import finite_population_lower,finite_population_upper


def forecast(cells,n,N,draws,seed):
    for value,minimum in ((n,1),(N,1),(draws,1),(seed,0)):
        if type(value) is not int or value<minimum:raise ValueError('positive integer planning design required')
    if n>N or not cells:raise ValueError('invalid planning population')
    probabilities=[]
    for cell in cells:
        for arm in ('baseline','candidate'):
            state=cell[arm]
            if (type(state) is not list or len(state)!=3 or any(type(x) is not int or x not in (0,1) for x in state)
                    or state[1]>state[0] or (state[1] and state[2])):
                raise ValueError('impossible E/S/failure state')
        probability=cell['probability']
        if type(probability) not in (int,float) or not math.isfinite(probability) or probability<0:
            raise ValueError('invalid planning probability')
        probabilities.append(probability)
    if not math.isclose(sum(probabilities),1.,rel_tol=0,abs_tol=1e-12):raise ValueError('planning probabilities must sum to one')
    probabilities=np.array(probabilities)
    raw=probabilities*N;counts=np.floor(raw).astype(np.int64)
    for j in sorted(range(len(cells)),key=lambda j:(-(raw[j]-counts[j]),j))[:N-int(counts.sum())]:counts[j]+=1
    sample=np.random.Generator(np.random.PCG64(seed)).multivariate_hypergeometric(counts,n,size=draws)
    baseline=np.array([c['baseline'] for c in cells]);candidate=np.array([c['candidate'] for c in cells])
    endpoint_pass=[];widths=[]
    for endpoint in (1,0):
        rescues=sample@((candidate[:,endpoint]==1)&(baseline[:,endpoint]==0)).astype(int)
        harms=sample@((candidate[:,endpoint]==0)&(baseline[:,endpoint]==1)).astype(int)
        lower={int(x):finite_population_lower(int(x),n,N,.003125) for x in np.unique(rescues)}
        upper={int(x):finite_population_upper(int(x),n,N,.003125) for x in np.unique(harms)}
        bound=np.array([lower[int(r)]-upper[int(h)] for r,h in zip(rescues,harms)])
        endpoint_pass.append(bound>0 if endpoint==1 else bound>=0)
        widths.append({'minimum_lower_bound':float(bound.min()),'median_lower_bound':float(np.median(bound)),
                       'p10_lower_bound':float(np.quantile(bound,.1))})
    failure_pass=sample@candidate[:,2]<=sample@baseline[:,2]
    passed=endpoint_pass[0]&endpoint_pass[1]&failure_pass
    probability=float(passed.mean());z=1.959963984540054
    denominator=1+z*z/draws
    centre=(probability+z*z/(2*draws))/denominator
    radius=z*math.sqrt(probability*(1-probability)/draws+z*z/(4*draws*draws))/denominator
    return {'n':n,'N':N,'draws':draws,'seed':seed,'joint_admission_probability':probability,
            'monte_carlo_95_interval':[centre-radius,centre+radius],
            'strict_guard_probability':float(endpoint_pass[0].mean()),'answer_guard_probability':float(endpoint_pass[1].mean()),
            'failure_guard_probability':float(failure_pass.mean()),'lower_bound_diagnostics':{'strict':widths[0],'answer':widths[1]},
            'finite_frame_cells':counts.tolist(),'cells':cells,'tail_alpha':.003125,
            'comparator':'baseline-ten is both selected and fixed-ten; duplicate guards remain unchanged',
            'assumptions':'Explicit hypothetical paired E/S/failure finite frame; not estimated power guaranteed by observed development rates'}

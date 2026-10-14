from collections import Counter

from test_protocol import api, inputs
from outcome_poc.storage import content_hash


def test_complete_roster_direct_repeats_and_paid_expansion(tmp_path):
    p=api();c=inputs(tmp_path);m=p.freeze_methods(c['development'],c['selection'],c['capacity'])
    jobs=p.plan_jobs(m,c['tasks'][:2])
    assert len(jobs)==36
    assert len({j['job_id'] for j in jobs})==36
    for task in c['tasks'][:2]:
        group=[j for j in jobs if j['task_id']==task.task_id]
        assert Counter(j['scope'] for j in group)=={'representative':11,'anchor':1,'random':1,'oracle-source':1,'primary':4}
        assert all(j['cache_mode']=='none' and j['mode']=='direct' for j in group)
        assert sum(j['generation_calls']['min'] for j in group)==19
        assert sum(j['generation_calls']['max'] for j in group)==20
        primary=[j for j in group if j['scope']=='primary']
        assert Counter((j['arm'],j['repetition_id']) for j in primary)=={('A',1):1,('B',1):1,('A',2):1,('B',2):1}
        for repetition in (1,2):
            positions=[i for i,j in enumerate(group) if j['scope']=='primary' and j['repetition_id']==repetition]
            assert positions[1]==positions[0]+1
        assert {j['method']['config_id'] for j in group if j['scope']!='primary'} >= {'FIXED-2','FIXED-10','RANDOM-MIXTURE'}
    assert jobs==p.plan_jobs(m,list(reversed(c['tasks'][:2])))
    # Identity must keep paid draft/judge roles, not deduplicate identical answer budgets.
    post=next(j for j in jobs if j['method']['family']=='POST-OUTCOME')
    judge=next(j for j in jobs if j['method']['family']=='LLM-SUFFICIENCY')
    assert post['paid_roles']==['draft','answer_if_escalated']
    assert judge['paid_roles']==['judge','answer']


def test_random_mixture_exact_hash_and_representative_order_is_not_fixed(tmp_path):
    p=api();c=inputs(tmp_path);m=p.freeze_methods(c['development'],c['selection'],c['capacity'])
    jobs=p.plan_jobs(m,c['tasks'])
    orders=[]
    for task in c['tasks']:
        group=[j for j in jobs if j['task_id']==task.task_id]
        orders.append(tuple(j['method']['config_id'] for j in group if j['scope']!='primary'))
        random=next(j for j in group if j['scope']=='random')
        expected=10 if int(content_hash([271828,task.task_id,'random-mixture']),16)/2**256<.2 else 2
        assert random['method']['k']==expected
    assert len(set(orders))>1


def test_bound_job_rejects_policy_task_and_runtime_changes(tmp_path):
    import pytest
    from outcome_poc.schemas import Task
    p=api();c=inputs(tmp_path);frozen=p.freeze(c);row=frozen['schedule']['jobs'][0]
    task=next(t for t in c['tasks'] if t.task_id==row['task_id'])
    assert p.verify_job(frozen,row,task,frozen['methods']['reader'])==row
    with pytest.raises(ValueError): p.verify_job(frozen,{**row,'mode':'replay'},task,frozen['methods']['reader'])
    with pytest.raises(ValueError): p.verify_job(frozen,row,Task(task.task_id,task.split,'mutated',task.candidate_ids),frozen['methods']['reader'])
    with pytest.raises(ValueError): p.verify_job(frozen,row,task,{**frozen['methods']['reader'],'max_new_tokens':1})


def test_diagnostic_policy_uses_frozen_budget_and_cannot_enter_candidate(tmp_path):
    from serving_helpers import fixture_runtime
    from outcome_poc.runner import execute_job
    p=api();runtime,job,_=fixture_runtime(tmp_path)
    policy=p.materialize_policy({'config_id':'RANDOM-MIXTURE','family':'RANDOM-MIXTURE','k':10},{})
    result=execute_job({**job,'policy':policy},runtime,tmp_path/'random')
    assert result.policy_id=='RANDOM-MIXTURE' and len(result.evidence_ids)==10
    no_context=p.materialize_policy({'config_id':'NO-CONTEXT-DIAGNOSTIC','family':'NO-CONTEXT-DIAGNOSTIC'},{})
    result=execute_job({**job,'policy':no_context,'allow_no_context_diagnostic':True},runtime,tmp_path/'no-context')
    assert result.policy_id=='NO-CONTEXT-DIAGNOSTIC' and result.evidence_ids==[] and result.generation_calls==1

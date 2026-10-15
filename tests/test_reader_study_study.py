"""Authored cohorts and protocol behavior; no benchmark assets."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from outcome_poc.storage import canonical_bytes, content_hash


def authored(n=220):
    tasks = [dict(task_id=f't-{i:04}', split='fit_extension', question=f'Invented item {i}?',
                  candidate_ids=[f'd-{j}' for j in range(10)]) for i in range(n)]
    membership = [dict(source='train', group_key_hash=content_hash(t['question'].casefold()),
                       representative_id=t['task_id'], member_ids=[t['task_id']], disposition='retained')
                  for t in tasks]
    citation = dict(diagnosis=[t['task_id'] for t in tasks[:64]],
                    comparison=[t['task_id'] for t in tasks[64:80]])
    return tasks, membership, citation


def test_cohorts_use_named_development_and_independent_full_fresh_population():
    from outcome_poc.reader_study.study import plan_cohorts
    tasks, membership, citation = authored()
    result = plan_cohorts(tasks, {'t-0080'}, membership, citation)
    ids = [f't-{i:04}' for i in range(81,220)]
    expected = sorted(citation['diagnosis'], key=lambda i:(hashlib.sha256(
        ('reader-quality-v1:development:'+i).encode()).digest(),i))[:16]
    permutation = np.random.Generator(np.random.PCG64(271829)).permutation(139)
    assert result['development'] == expected
    assert result['confirmation'] == [ids[i] for i in permutation[:128]]
    assert result['confirmation_population'] == 139
    assert result['eligibility']['sorted_ids_hash'] == content_hash(ids)
    assert result == plan_cohorts(list(reversed(tasks)), {'t-0080'}, list(reversed(membership)), citation)


def test_historical_aliases_and_dev_normalized_groups_close_before_sampling():
    from outcome_poc.reader_study.study import plan_cohorts
    tasks, membership, citation = authored(90)
    membership[80]['member_ids'].append('unexecuted')
    membership.append(dict(source='dev', member_ids=['unexecuted','z-bridge'],
                           group_key_hash='dev', disposition='excluded', representative_id='dev'))
    membership[81]['member_ids'].append('z-bridge')
    # A separate dev group shares the normalization of another retained train row.
    membership.append(dict(source='dev', member_ids=['official-dev'],
        group_key_hash=membership[82]['group_key_hash'], disposition='excluded',representative_id='official-dev'))
    cohorts = plan_cohorts(tasks, {'unexecuted'}, membership, citation,development_n=2,confirmation_n=2)
    assert cohorts['eligibility']['sorted_ids'] == [f't-{i:04}' for i in range(83,90)]
    assert set(citation['comparison']) <= set(cohorts['eligibility']['excluded_ids'])


@pytest.mark.parametrize('mutation', ['representative','hash','duplicate','citation','size'])
def test_invalid_metadata_cannot_relabel_a_representative(mutation):
    from outcome_poc.reader_study.study import plan_cohorts
    tasks, membership, citation = authored()
    kwargs = {}
    if mutation=='representative':membership[100]['member_ids'].append('a-earlier')
    elif mutation=='hash':membership[100]['group_key_hash']='wrong'
    elif mutation=='duplicate':membership.append(copy.deepcopy(membership[100]))
    elif mutation=='citation':citation['diagnosis'].append('absent')
    else:kwargs['development_n']=True
    with pytest.raises(ValueError):plan_cohorts(tasks,set(),membership,citation,**kwargs)


def test_factorial_schedule_has_exact_cells_stable_reader_blocks_and_bound_job_ids():
    from outcome_poc.reader_study.study import plan_cohorts,make_schedule
    tasks,membership,citation=authored()
    cohorts=plan_cohorts(tasks,set(),membership,citation)
    jobs=make_schedule(cohorts,'outer-source-cohort-and-registry')
    assert [sum(j['scientific_stage']==s for j in jobs) for s in ('development','confirmation')]==[96,512]
    assert len({j['job_id'] for j in jobs})==608
    assert all(j['stage']=='diagnosis' and j['prompt_condition']=='baseline' and j['repetition']==0 for j in jobs)
    for stage in ('development','confirmation'):
        selected=[j for j in jobs if j['scientific_stage']==stage]
        readers=sorted(['qwen4b-instruct','qwen14b-nonthinking'],key=lambda r:(
            content_hash([271829,'reader-quality-v1',stage,r]),r))
        assert list(dict.fromkeys(j['reader_id'] for j in selected))==readers
        first=[j for j in selected if j['reader_id']==readers[0]]
        assert [(j['task_id'],j['arm']) for j in first]==sorted(
            [(j['task_id'],j['arm']) for j in first],key=lambda c:(
                content_hash([271829,'reader-quality-v1',stage,readers[0],*c]),*c))
    reordered=copy.deepcopy(cohorts)
    for s in ('development','confirmation'):reordered[s].reverse()
    assert make_schedule(reordered,'outer-source-cohort-and-registry')==jobs
    changed=make_schedule(cohorts,'other-reader-or-source')
    assert not {j['job_id'] for j in jobs}&{j['job_id'] for j in changed}
    for job in jobs:
        swapped={k:v for k,v in job.items() if k not in {'job_id','ordinal'}}
        swapped['reader_id']='qwen4b-instruct' if job['reader_id']=='qwen14b-nonthinking' else 'qwen14b-nonthinking'
        assert job['job_id']!=content_hash(['reader-quality-v1',swapped])

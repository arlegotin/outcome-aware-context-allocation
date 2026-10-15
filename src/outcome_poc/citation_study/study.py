"""Annotation-free selection and immutable serving verification.

Serving verification deliberately never opens original inputs or comparison stores.
Call verify_stage only after comparison admission, when selecting comparison jobs.
"""
from pathlib import Path

import numpy as np

from ..storage import content_hash, read_jsonl
from ..data_runtime import load_tasks, DocumentStore
from ..followup.study import read, identity, verify_files, publish, normalized, validate_projection
from .prompts import registry

SEED = 20261015
NAMESPACE = 'citation-chain-v1'
STAGES = ('diagnosis', 'comparison')
EXECUTION_MODE = 'continuous-resident-v1'


def decoding_settings(config):
    """Shared declaration for the actual backend and GenerationRequest adapter."""
    return {**config['reader'],'cache_mode':'none','execution_mode':EXECUTION_MODE}


def plan_cohorts(tasks, old_ids, membership, *, diagnosis_n=64, comparison_n=256):
    if any(type(n) is not int or n <= 0 for n in (diagnosis_n, comparison_n)):
        raise ValueError('positive integer cohort sizes required')
    by_id = {row['task_id']: row for row in tasks}
    if len(by_id) != len(tasks):
        raise ValueError('duplicate task ID')
    old_ids = set(old_ids) | {r['task_id'] for r in tasks
                            if r['split'] in {'pilot','pilot_reservation','fit','tune'}}
    protected = {r['task_id'] for r in tasks if r['split'] == 'protected'}
    excluded = old_ids | protected | {i for g in membership if g['source'] == 'dev' for i in g['member_ids']}
    hashes = {content_hash(normalized(by_id[i]['question'])) for i in excluded if i in by_id}
    while True:
        new_groups = [g for g in membership if excluded.intersection(g['member_ids']) or g['group_key_hash'] in hashes]
        expanded = excluded | {i for g in new_groups for i in g['member_ids']}
        new_hashes = hashes | {g['group_key_hash'] for g in new_groups}
        new_hashes |= {content_hash(normalized(by_id[i]['question'])) for i in expanded if i in by_id}
        if expanded == excluded and new_hashes == hashes:
            break
        excluded, hashes = expanded, new_hashes
    groups = {}
    for group in membership:
        if group['disposition'] == 'retained':
            task_id = group['representative_id']
            if task_id in groups:
                raise ValueError('duplicate retained representative membership')
            groups[task_id] = group
    eligible = []
    for row in tasks:
        group = groups.get(row['task_id'])
        if (group is None or group['source'] != ('dev' if row['split'] == 'protected' else 'train') or
                group['group_key_hash'] != content_hash(normalized(row['question'])) or
                row['task_id'] != min(group['member_ids'])):
            raise ValueError('prepared representative membership mismatch')
        if row['split'] == 'fit_extension' and row['task_id'] not in excluded and group['group_key_hash'] not in hashes:
            eligible.append(row['task_id'])
    if len({groups[i]['group_key_hash'] for i in eligible}) != len(eligible):
        raise ValueError('eligible duplicate normalized groups')
    ids = sorted(eligible)
    if len(ids) < diagnosis_n + comparison_n:
        raise ValueError('insufficient fresh eligible questions')
    order = np.random.Generator(np.random.PCG64(SEED)).permutation(len(ids))
    diagnosis = [ids[int(i)] for i in order[:diagnosis_n]]
    comparison = [ids[int(i)] for i in order[diagnosis_n:diagnosis_n+comparison_n]]
    return {'diagnosis':diagnosis, 'comparison':comparison,
            'sample_hashes':{'diagnosis':content_hash(diagnosis),'comparison':content_hash(comparison)},
            'comparison_population':len(ids)-diagnosis_n,
            'generator':{'seed':SEED,'algorithm':'numpy.random.Generator(PCG64)','numpy_version':np.__version__},
            'eligibility':{'count':len(ids),'sorted_ids':ids,'sorted_ids_hash':content_hash(ids),
                           'excluded_ids':sorted(excluded),'old_ids':sorted(old_ids),
                           'protected_ids':sorted(protected),'excluded_group_hashes':sorted(hashes)}}


def make_schedule(cohorts, bindings_hash):
    jobs = []
    if set(cohorts['diagnosis']) & set(cohorts['comparison']):
        raise ValueError('cohorts overlap')
    for stage in STAGES:
        if len(set(cohorts[stage])) != len(cohorts[stage]):
            raise ValueError('duplicate cohort reservation')
        for task_id in cohorts[stage]:
            cells = [(c, a) for c in ('baseline','chain')
                     for a in (('2','10','support-documents') if stage == 'diagnosis' else ('2','10'))]
            cells.sort(key=lambda cell:(content_hash([SEED,NAMESPACE,stage,task_id,*cell]),*cell))
            for condition, arm in cells:
                factors = {'stage':stage,'task_id':task_id,'prompt_condition':condition,'evidence_arm':arm,
                           'arm':arm,'repetition':0,'execution_mode':EXECUTION_MODE,
                           'bindings_hash':bindings_hash,'system_hash':registry()[condition]['system_hash']}
                jobs.append({**factors,'job_id':content_hash([NAMESPACE,factors]),'ordinal':len(jobs)})
    return jobs


def verify_stage(root, stage, plan=None):
    if stage not in STAGES:
        raise ValueError('unknown citation stage')
    root = Path(root).resolve()
    plan = plan or verify(root)
    expected = plan['stage_files'][stage]
    prefix = f'inputs/{stage}/'
    names = {prefix+'tasks.jsonl',prefix+'documents.jsonl'}
    if stage == 'diagnosis': names.add(prefix+'support-doc-ids.jsonl')
    if set(expected) != names:
        raise ValueError('invalid stage input inventory')
    verify_files({str(root/n):v for n,v in expected.items()})
    tasks = load_tasks(root/prefix/'tasks.jsonl','fit_extension')
    cohorts = read(root/'cohorts.json')
    if [t.task_id for t in tasks] != cohorts[stage]:
        raise ValueError('stage task order differs from frozen cohort')
    documents = DocumentStore(root/prefix/'documents.jsonl')
    if set(documents.offsets) != {d for t in tasks for d in t.candidate_ids}:
        raise ValueError('stage document inventory mismatch')
    if stage == 'diagnosis':
        from dataclasses import asdict
        validate_projection(list(read_jsonl(root/prefix/'support-doc-ids.jsonl')), [asdict(t) for t in tasks])
    return plan


def verify(root, *, privileged=False):
    root = Path(root).resolve()
    plan = read(root/'plan.json')
    if plan['plan_hash'] != content_hash({k:v for k,v in plan.items() if k != 'plan_hash'}):
        raise ValueError('plan checksum mismatch')
    verify_files({str(root/n):v for n,v in plan['files'].items()})
    verify_files(plan['asset_files'])
    freeze = plan['freeze']
    if content_hash(freeze['bindings']) != freeze['bindings_hash']:
        raise ValueError('execution bindings mismatch')
    if freeze['bindings']['settings'] != freeze['settings']:
        raise ValueError('settings binding mismatch')
    if (freeze['bindings']['decoding'] != decoding_settings(freeze['settings']) or
            freeze['decoding_hash'] != content_hash(freeze['bindings']['decoding'])):
        raise ValueError('decoding declaration differs from bound reader settings')
    if read(root/'selection-frozen.json') != freeze:
        raise ValueError('selection freeze mismatch')
    cohorts, schedule = read(root/'cohorts.json'), read(root/'schedule.json')
    if (content_hash(cohorts) != freeze['cohorts_hash'] or content_hash(schedule) != freeze['schedule_hash']
            or schedule != make_schedule(cohorts,freeze['bindings_hash'])):
        raise ValueError('schedule/cohort binding mismatch')
    if read(root/'prompts.json') != registry() or freeze['bindings']['prompts'] != registry():
        raise ValueError('prompt registry mismatch')
    input_bindings = {stage:{n:v for n,v in files.items() if not n.endswith('/support-doc-ids.jsonl')}
                      for stage,files in plan['stage_files'].items()}
    if freeze['bindings']['stage_files'] != input_bindings:
        raise ValueError('stage input binding mismatch')
    verify_stage(root,'diagnosis',plan)
    if privileged:
        verify_files(freeze['source_files'])
        verify_files(freeze['privileged_inputs'])
        verify_files({plan['gold_input']['path']:plan['gold_input']['identity']})
        verify_stage(root,'comparison',plan)
    return plan


def selected_jobs(root, stage):
    plan = verify(root)
    verify_stage(root,stage,plan)
    return [job for job in read(Path(root)/'schedule.json') if job['stage'] == stage]

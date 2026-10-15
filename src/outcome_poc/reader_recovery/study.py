"""Shared immutable contracts, safe for the serving import closure."""
from pathlib import Path
from ..followup.study import read, identity, publish, verify_files
from ..storage import content_hash, read_jsonl

GROUP_ARMS = {'natural':('2','5','10'), 'oracle':('support-documents','support-sentences')}
READER = {'repo_id':'mlx-community/Qwen3-4B-Instruct-2507-4bit',
    'revision':'50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b','max_context_tokens':8192,
    'max_new_tokens':256,'timeout_seconds':120,'prefill_step_size':512,'temperature':0}


def group_arms(config):
    if config['protocol_id']=='reader-evidence-first-v1':
        return {'natural':('baseline','evidence-first')}
    if config['protocol_id']=='reader-recovery-v1':
        return GROUP_ARMS
    raise ValueError('unknown recovery protocol')


def make_schedule(config,cohorts):
    roster = []
    if config['protocol_id']=='reader-evidence-first-v1':
        ordered = sorted(cohorts['validation'],key=lambda i:content_hash([config['protocol_id'],config['seed'],i]))
        for number,i in enumerate(ordered):
            arms = ('baseline','evidence-first') if number%2==0 else ('evidence-first','baseline')
            for arm in arms:
                job = {'group':'natural','stage':'natural','task_id':i,'arm':arm,'reader_condition':arm,
                       'budget':10,'repetition':0,'block':number//8}
                roster.append({**job,'job_id':content_hash([config['protocol_id'],job]),'ordinal':len(roster)})
        return roster
    for group,arms in GROUP_ARMS.items():
        cells = [(i,arm) for i in cohorts['diagnosis'] for arm in arms]
        cells.sort(key=lambda cell:content_hash([config['protocol_id'],config['seed'],group,*cell]))
        for i,arm in cells:
            job = {'group':group,'stage':group,'task_id':i,'arm':arm,'repetition':0}
            roster.append({**job,'job_id':content_hash([config['protocol_id'],job]),'ordinal':len(roster)})
    return roster


def verify(root, *, group=None):
    root = Path(root).resolve()
    plan = read(root/'plan.json')
    if plan['plan_hash'] != content_hash({k:v for k,v in plan.items() if k!='plan_hash'}):
        raise ValueError('recovery plan identity mismatch')
    if plan['root'] != str(root):
        raise ValueError('recovery root/protocol mismatch')
    config = plan['config']
    groups = group_arms(config)
    if content_hash(config['reader']) != content_hash(READER):
        raise ValueError('recovery reader recipe drift')
    cohorts = read(root/'cohorts.json')
    all_ids = []
    validation = config['protocol_id']=='reader-evidence-first-v1'
    keys = (('validation','validation_n'),('prior_diagnosis','prior_diagnosis_n'),('evaluation_reserved','evaluation_reserved_n')) if validation else (
        ('diagnosis','diagnosis_n'),('validation_reserved','validation_reserved_n'),('evaluation_reserved','evaluation_reserved_n'))
    for cohort,key in keys:
        ids = cohorts[cohort]
        if type(config[key]) is not int or config[key]<=0 or len(ids)!=config[key] or any(type(i) is not str or not i for i in ids):
            raise ValueError('recovery assigned/reserved cohort mismatch')
        all_ids.extend(ids)
    if len(set(all_ids)) != len(all_ids):
        raise ValueError('recovery diagnosis/reservations overlap')
    tasks = list(read_jsonl(root/'tasks.jsonl'))
    active = cohorts['validation' if validation else 'diagnosis']
    if len(tasks)!=len(active) or {t['task_id'] for t in tasks}!=set(active):
        raise ValueError('recovery task assignment mismatch')
    if read(root/'schedule.json') != make_schedule(config,cohorts):
        raise ValueError('recovery exact diagnosis schedule mismatch')
    if any(Path(n).is_absolute() or '..' in Path(n).parts for n in plan['files']):
        raise ValueError('recovery frozen input escapes root')
    if validation:
        from .prompts import registry
        if plan['prompt_conditions']!=registry():
            raise ValueError('reader condition identity drift')
    if group is not None and group not in groups:
        raise ValueError('unknown recovery serving group')
    verify_files({str(root/name):value for name,value in plan['files'].items()
                  if not (group=='natural' and name=='support-view.json')})
    return plan


def jobs(root,group):
    if group not in GROUP_ARMS:
        raise ValueError('unknown diagnosis group')
    return [j for j in read(Path(root)/'schedule.json') if j['group']==group]

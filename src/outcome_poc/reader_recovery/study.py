"""Shared immutable contracts, safe for the serving import closure."""
from pathlib import Path
from ..followup.study import read, identity, publish, verify_files
from ..storage import content_hash, read_jsonl

GROUP_ARMS = {'natural':('2','5','10'), 'oracle':('support-documents','support-sentences')}
READER = {'repo_id':'mlx-community/Qwen3-4B-Instruct-2507-4bit',
    'revision':'50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b','max_context_tokens':8192,
    'max_new_tokens':256,'timeout_seconds':120,'prefill_step_size':512,'temperature':0}


FRESH_KIND = 'independent-reader-validation-v2'
LEGACY_IDS = {'reader-recovery-v1','reader-evidence-first-v1'}


def is_fresh_validation(config):
    from .study_v3 import is_scientific
    from .action_study_v4 import is_action
    from .learning_study_v5 import is_learning
    if is_scientific(config) or is_action(config) or is_learning(config):return False
    if 'study_kind' not in config and 'schema_version' not in config:
        return False
    import re
    if (type(config.get('schema_version')) is not int or config.get('schema_version')!=2 or config.get('study_kind')!=FRESH_KIND or
            config.get('protocol_id') in LEGACY_IDS or
            type(config.get('protocol_id')) is not str or
            re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}',config['protocol_id']) is None or
            type(config.get('seed')) is not int or config['seed']<0 or
            type(config.get('validation_n')) is not int or config['validation_n']<2 or config['validation_n']%2 or
            config.get('arms')!=['baseline','evidence-first'] or
            type(config.get('repetitions')) is not int or config['repetitions']!=1):
        raise ValueError('unsupported fresh recovery protocol/schema/schedule')
    return True


def is_validation(config):
    from .study_v3 import is_scientific
    return is_scientific(config) or is_fresh_validation(config) or config['protocol_id']=='reader-evidence-first-v1'


def group_arms(config):
    from .learning_study_v5 import is_learning
    if is_learning(config):return {'natural':('2','10')}
    from .action_study_v4 import is_action
    if is_action(config):return {'natural':('2','5','10')}
    if is_validation(config):
        return {'natural':('baseline','evidence-first')}
    if config['protocol_id']=='reader-recovery-v1':
        return GROUP_ARMS
    raise ValueError('unknown recovery protocol')


def make_schedule(config,cohorts):
    from .learning_study_v5 import is_learning,schedule as learning_schedule
    if is_learning(config):return learning_schedule(config,cohorts)
    from .action_study_v4 import is_action,schedule
    if is_action(config):return schedule(config,cohorts)
    group_arms(config)  # Unknown IDs must never inherit a completed-v1 schedule.
    roster = []
    if is_validation(config):
        ids=cohorts['validation']
        if (type(ids) is not list or any(type(i) is not str or not i for i in ids) or len(ids)!=len(set(ids)) or
                (config.get('schema_version') in (2,3) and len(ids)!=config['validation_n'])):
            raise ValueError('validation assignment mismatch')
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
    from .study_v3 import is_scientific
    from .action_study_v4 import is_action
    from .learning_study_v5 import is_learning
    learning=is_learning(config)
    action=is_action(config)
    if is_scientific(config) or action or learning:
        if group is None:verify_files(plan.get('input_identities',{}))
        from ..reader_probe.study import inventory
        if plan['source_snapshot_hash']!=content_hash(inventory(root/'source')):
            raise ValueError('scientific frozen source inventory drift')
    if is_fresh_validation(config):
        if config.get('execution_mode')!='preparation-only' or plan['scientific_execution']['enabled'] is not False:
            raise ValueError('fresh v2 scientific execution is unsupported')
        verify_files(plan['input_identities'])
    if content_hash(config['reader']) != content_hash(READER):
        raise ValueError('recovery reader recipe drift')
    cohorts = read(root/'cohorts.json')
    all_ids = []
    validation = is_validation(config)
    keys = (('validation','validation_n'),('prior_diagnosis','prior_diagnosis_n'),('evaluation_reserved','evaluation_reserved_n')) if validation else (
        ('diagnosis','diagnosis_n'),('validation_reserved','validation_reserved_n'),('evaluation_reserved','evaluation_reserved_n'))
    if config.get('schema_version') in (2,3):
        keys=(('validation','validation_n'),)
    if action:keys=(('development','development_n'),)
    if learning:keys=(('fit','fit_n'),('learning_holdout','holdout_n'))
    for cohort,key in keys:
        ids = cohorts[cohort]
        if type(config[key]) is not int or (config[key]<=0 and not (learning and key=='holdout_n' and config[key]==0)) or len(ids)!=config[key] or any(type(i) is not str or not i for i in ids):
            raise ValueError('recovery assigned/reserved cohort mismatch')
        all_ids.extend(ids)
    if len(set(all_ids)) != len(all_ids):
        raise ValueError('recovery diagnosis/reservations overlap')
    tasks = list(read_jsonl(root/'tasks.jsonl'))
    active = cohorts['fit']+cohorts['learning_holdout'] if learning else cohorts['development' if action else 'validation' if validation else 'diagnosis']
    if len(tasks)!=len(active) or {t['task_id'] for t in tasks}!=set(active):
        raise ValueError('recovery task assignment mismatch')
    if read(root/'schedule.json') != make_schedule(config,cohorts):
        raise ValueError('recovery exact diagnosis schedule mismatch')
    if any(Path(n).is_absolute() or '..' in Path(n).parts for n in plan['files']):
        raise ValueError('recovery frozen input escapes root')
    if validation or action or learning:
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

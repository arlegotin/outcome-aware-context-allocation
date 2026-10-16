"""NEW annotation-free v4 action schedules, distinct from reader admission."""
from itertools import permutations
import math,re
from ..storage import content_hash
from .study import READER,LEGACY_IDS

KIND='allocation-action-value-v4'
SCREEN={'minimum_R_fraction_saving':.20,'minimum_mean_T_saving_seconds':.25,
        'planning_routing_seconds':.02,'minimum_strict_discordances':16,'operational_requirements':None}


def is_action(config):
    if config.get('schema_version')!=4:return False
    n=config.get('development_n');purpose=config.get('purpose')
    if (type(config.get('schema_version')) is not int or config.get('study_kind')!=KIND or
            type(config.get('protocol_id')) is not str or config['protocol_id'] in LEGACY_IDS or
            re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}',config['protocol_id']) is None or
            purpose not in {'action-headroom','authored-action-smoke'} or config.get('execution_mode')!='frozen-native' or
            config.get('reader')!=READER or config.get('reader_recipe')!='evidence-first-v1' or
            'validation_n' in config or type(n) is not int or n!=(2 if purpose=='authored-action-smoke' else 128) or
            type(config.get('seed')) is not int or config['seed']<0 or config.get('arms')!=['2','5','10'] or
            type(config.get('repetitions')) is not int or config['repetitions']!=1 or
            config.get('cache_mode')!='none' or type(config.get('semantic_retries')) is not int or config['semantic_retries']!=0 or
            config.get('reuse_indexes')!=[] or config.get('request_timing')!='complete-continuous-v3' or
            type(config.get('native_generation_budget_calls')) is not int or config['native_generation_budget_calls']!=3*n+1 or
            type(config.get('native_budget_seconds')) not in (int,float) or not math.isfinite(config['native_budget_seconds']) or config['native_budget_seconds']<=0 or
            config.get('index_budget_seconds')!=600 or config.get('research_screen')!=SCREEN):
        raise ValueError('unsupported v4 action study definition')
    return True


def schedule(config,cohorts):
    if not is_action(config):raise ValueError('explicit v4 action kind required')
    ids=cohorts['development']
    if type(ids) is not list or len(ids)!=config['development_n'] or len(set(ids))!=len(ids) or any(type(i) is not str or not i for i in ids):
        raise ValueError('v4 exact development assignment mismatch')
    ordered=sorted(ids,key=lambda i:content_hash([config['protocol_id'],config['seed'],i]))
    orders=sorted(permutations((2,5,10)),key=lambda p:content_hash([config['protocol_id'],config['seed'],p]))
    roster=[]
    for number,i in enumerate(ordered):
        for budget in orders[number%len(orders)]:
            job={'group':'natural','stage':'headroom','task_id':i,'arm':str(budget),'reader_condition':'evidence-first',
                 'budget':budget,'repetition':0,'block':number//8}
            roster.append({**job,'job_id':content_hash([config['protocol_id'],job]),'ordinal':len(roster)})
    return roster

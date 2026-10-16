"""NEW annotation-free v5 fit/untouched-learning-holdout contracts."""
import math,re
from ..storage import content_hash
from .study import READER,LEGACY_IDS

KIND='allocation-routing-signal-v5'
SCREEN={'minimum_R_fraction_saving':.20,'minimum_mean_T_saving_seconds':.25,
        'planning_routing_seconds':.02,'control_match_R_fraction':.05,'operational_requirements':None}


def is_learning(config):
    if config.get('schema_version')!=5:return False
    smoke=config.get('purpose')=='authored-routing-smoke';nf=config.get('fit_n');nh=config.get('holdout_n')
    if (type(config.get('schema_version')) is not int or config.get('study_kind')!=KIND or
            type(config.get('protocol_id')) is not str or config['protocol_id'] in LEGACY_IDS or
            re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}',config['protocol_id']) is None or
            config.get('purpose') not in {'authored-routing-smoke','routing-signal'} or config.get('execution_mode')!='frozen-native' or
            config.get('reader')!=READER or config.get('reader_recipe')!='evidence-first-v1' or
            any(k in config for k in ('validation_n','development_n','gold','answer','answers','supporting_facts','scores')) or
            type(nf) is not int or type(nh) is not int or (nf,nh)!=((2,0) if smoke else (512,256)) or
            type(config.get('seed')) is not int or config['seed']!=20261018 or config.get('arms')!=['2','10'] or
            type(config.get('repetitions')) is not int or config['repetitions']!=1 or config.get('cache_mode')!='none' or
            type(config.get('semantic_retries')) is not int or config['semantic_retries']!=0 or config.get('reuse_indexes')!=[] or
            config.get('request_timing')!='complete-continuous-v3' or config.get('index_budget_seconds')!=600 or
            type(config.get('native_generation_budget_calls')) is not int or config['native_generation_budget_calls']!=2*(nf+nh)+1 or
            type(config.get('native_budget_seconds')) not in (int,float) or not math.isfinite(config['native_budget_seconds']) or config['native_budget_seconds']<=0 or
            config.get('learning_screen')!=SCREEN):raise ValueError('unsupported v5 routing-signal definition')
    return True


def schedule(config,cohorts):
    if not is_learning(config):raise ValueError('explicit v5 routing-signal kind required')
    fit,holdout=cohorts['fit'],cohorts['learning_holdout'];ids=fit+holdout
    if (type(fit) is not list or type(holdout) is not list or len(fit)!=config['fit_n'] or len(holdout)!=config['holdout_n'] or
            len(ids)!=len(set(ids)) or any(type(i) is not str or not i for i in ids)):
        raise ValueError('v5 exact fit/learning-holdout assignment mismatch')
    held=set(holdout);roster=[]
    for number,i in enumerate(sorted(ids,key=lambda i:content_hash([config['protocol_id'],config['seed'],i]))):
        for budget in ((2,10) if number%2==0 else (10,2)):
            job={'group':'natural','stage':'headroom' if i in held else 'fit','task_id':i,'arm':str(budget),
                 'reader_condition':'evidence-first','budget':budget,'repetition':0,'block':number//8}
            roster.append({**job,'job_id':content_hash([config['protocol_id'],job]),'ordinal':len(roster)})
    return roster

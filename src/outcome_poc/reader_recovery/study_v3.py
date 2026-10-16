"""NEW scientific study definition over the actual allocation serving runner."""
import re
from .study import READER,LEGACY_IDS

KIND='allocation-reader-admission-v3'


def is_scientific(config):
    if config.get('schema_version')!=3:return False
    if (type(config.get('schema_version')) is not int or config.get('study_kind')!=KIND or
            type(config.get('protocol_id')) is not str or config['protocol_id'] in LEGACY_IDS or
            re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}',config['protocol_id']) is None or
            config.get('purpose') not in {'reader-admission','authored-native-smoke'} or
            config.get('execution_mode')!='frozen-native' or config.get('reader')!=READER or
            type(config.get('validation_n')) is not int or config['validation_n']<2 or config['validation_n']%2 or
            type(config.get('seed')) is not int or config['seed']<0 or
            config.get('arms')!=['baseline','evidence-first'] or type(config.get('repetitions')) is not int or config['repetitions']!=1 or
            config.get('cache_mode')!='none' or type(config.get('semantic_retries')) is not int or config['semantic_retries']!=0 or
            config.get('reuse_indexes')!=[] or config.get('request_timing')!='complete-continuous-v3' or
            type(config.get('native_generation_budget_calls')) is not int or config['native_generation_budget_calls']!=2*config['validation_n']+1 or
            type(config.get('native_budget_seconds')) not in (int,float) or config['native_budget_seconds']<=0):
        raise ValueError('unsupported scientific v3 study definition')
    return True

"""Immutable scientific methods, sample and schedule; replaceable pre-attempt source seal.

No model or scorer is imported for planning. A source update changes execution
bytes only; it cannot change the three scientific manifests. Runtime verifies
large files once at initialization, then checks bound job identities per attempt.
"""
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np

from .storage import atomic_json, canonical_bytes, content_hash

FAMILIES = frozenset(('ADAPTIVE-k-published','ADAPTIVE-k-tuned','FIXED','LLM-SUFFICIENCY',
    'POST-OUTCOME','PRE-LINEAR','PRE-OUTCOME-GBM','PRE-RF','PROXY-LABEL','QUERY-ONLY','SHUFFLED-LABEL-GBM'))
POLICY_FIELDS = ('config_id','family','k','buffer','model_name','model_artifact_sha256','threshold_mode','threshold')
EXECUTION_MODULES = ('__init__','__main__','schemas','storage','data_runtime','retrieval','generation',
    'assets','environment','features','policies','train','timing','runner','protocol','scoring','statistics')


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def _read(path):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ValueError('duplicate protocol key')
            result[key]=value
        return result
    result=json.loads(Path(path).read_text(),object_pairs_hook=unique)
    canonical_bytes(result)
    return result


def _positive(value,name,integer=False):
    if type(value) not in ((int,) if integer else (int,float)) or not math.isfinite(value) or value<=0:
        raise ValueError('invalid '+name)
    return value


def _policy(row):
    value={key:row[key] for key in POLICY_FIELDS if key in row}
    family=value['family']
    if not value.get('config_id'): raise ValueError('unresolved policy identity')
    if family=='FIXED':
        if type(value.get('k')) is not int or not 1<=value['k']<=10: raise ValueError('invalid fixed action')
    elif family.startswith('ADAPTIVE-k'):
        if type(value.get('buffer')) is not int or not 0<=value['buffer']<=5: raise ValueError('invalid adaptive buffer')
    elif family!='LLM-SUFFICIENCY':
        if not value.get('model_name') or not value.get('model_artifact_sha256'): raise ValueError('unbound learned model')
        mode=value.get('threshold_mode');threshold=value.get('threshold')
        if mode=='numeric':
            if type(threshold) not in (int,float) or not math.isfinite(threshold): raise ValueError('nonfinite threshold')
        elif mode not in ('always_two','always_ten') or threshold is not None: raise ValueError('unresolved threshold')
    return value


def freeze_methods(development: dict, selection: dict, capacity: dict) -> dict:
    canonical_bytes([development,selection,capacity])
    if set(selection['families'])!=FAMILIES or selection.get('missing_families'): raise ValueError('incomplete family roster')
    a,b=_policy(selection['A*']),_policy(selection['B*'])
    if a['family']!='PRE-OUTCOME-GBM' or b['family'] in ('PRE-OUTCOME-GBM','SHUFFLED-LABEL-GBM'):
        raise ValueError('invalid selected pair')
    if selection['fixed_ten_anchor'].get('k')!=10 or selection['fixed_ten_anchor'].get('family')!='FIXED': raise ValueError('fixed-ten anchor required')
    reps=[_policy(selection['families'][f]['representative']) for f in sorted(FAMILIES)]
    if any(row['family']!=f for row,f in zip(reps,sorted(FAMILIES))): raise ValueError('mismatched representative')
    if a not in reps or b not in reps: raise ValueError('selected pair differs from family representatives')
    for row in reps:
        if 'model_name' in row:
            manifest=development['models'].get(row['model_name'])
            if (not isinstance(manifest,dict) or manifest.get('family')!=row['model_name'] or
                    manifest.get('origin')!='locally_created_fit_only' or manifest.get('artifact_sha256')!=row['model_artifact_sha256']):
                raise ValueError('unresolved or mismatched local gate model manifest')
    reader=copy.deepcopy(development['reader'])
    if (reader['max_context_tokens'],reader['max_new_tokens'])!=(8192,256): raise ValueError('unamended token caps')
    if (capacity.get('passed') is not True or capacity.get('max_prompt_tokens')!=7936 or
            capacity.get('forced_output_tokens')!=256): raise ValueError('unresolved maximum capacity calibration')
    largest=_positive(capacity['max_request_seconds'],'measured request seconds')
    if reader['timeout_seconds']!=2*largest: raise ValueError('timeout must equal twice measured maximum')
    repetitions=_positive(development['repetitions'],'repetitions',True)
    if repetitions<2: raise ValueError('two paired repetitions required; no one-repeat fallback declared')
    probability=selection['A*']['fit_escalation_probability']
    if type(probability) not in (int,float) or not 0<=probability<=1: raise ValueError('invalid fit routing probability')
    forecast=copy.deepcopy(development['forecast'])
    for name in ('conservative_seconds_per_question','fixed_remaining_seconds','report_reserve_seconds','available_seconds','bytes_per_question'):
        _positive(forecast[name],name)
    if forecast['report_reserve_seconds']<7200: raise ValueError('report reserve below two hours')
    if not development.get('calibration') or not development.get('identities'): raise ValueError('unresolved calibration/identities')
    return {'version':1,'selected':{'A':a,'B':b},'representatives':reps,
        'anchor':_policy(selection['fixed_ten_anchor']),'oracle_source':{'config_id':'FIXED-2','family':'FIXED','k':2},
        'random':{'config_id':'RANDOM-MIXTURE','family':'RANDOM-MIXTURE','probability':probability,
                  'rule':'unsigned SHA256 canonical [271828,task_id,"random-mixture"] / 2**256 < p chooses ten'},
        'reader':reader,'encoder':copy.deepcopy(development['encoder']),'retrieval':copy.deepcopy(development['retrieval']),'models':copy.deepcopy(development['models']),
        'identities':copy.deepcopy(development['identities']),'calibration':copy.deepcopy(development['calibration']),
        'capacity':copy.deepcopy(capacity),'forecast':forecast,'repetitions':repetitions,'post_cache_mode':'none',
        'seeds':{'split':20261014,'estimator':1729,'sampling':271828},
        'schedule_rule':{'question':'sort SHA256 canonical [271828,"question-order",task_id]',
            'representative':'sort SHA256 canonical [271828,"representative-order",task_id,scope,config_id]',
            'pair':'sort SHA256 canonical [271828,"pair-order",task_id,repetition,arm]; adjacent A/B after representatives',
            'deduplication':'none; fresh complete retrieval/routing/generation per pipeline'},
        'diagnostics':{'AA':{'scope':'full sample repeated fresh same-arm primary executions','timing_repetitions_not_tasks':True},
            'always_abstain':{'scope':'full assigned sample analytical policy','reader_calls':0},
            'oracle':{'scope':'full sample scorer-only clairvoyant two/ten','actions':[2,10]},
            'no_context':copy.deepcopy(development['diagnostics']['no_context']),
            'stress':{'status':'unexecuted'},'transfer':{'status':'unexecuted'}},
        'statistics':{'primary_alpha':.05,'quality_guards':['joint_vs_B','joint_vs_fixed10','answer_vs_B','answer_vs_fixed10'],
            'quality_tail_alpha':.05/16,'minimum_successes':30,'loo_minimum_successes':30,
            'stationarity_required':True,'deterministic_outputs_required':True,'single_dominance_review_required':True,
            'actual_run_assessment':{'timing':'retain raw paired times and covariance; inspect question-centered A-B differences by order/repetition/run block/length and recorded resource state; document evidence, never infer True merely from no rejected test; unresolved=None',
                'determinism':'compare raw output/status and paid token IDs across fresh same-arm repetitions; any difference invalidates fixed-outcome primary inference',
                'influence':'retain all leave-one-out effects/intervals/sign conclusions; documented dominance review, no invented universal cutoff; unresolved=None'},
            'all_family_superiority':'not prespecified','zero_successes':'null with reason zero_successes'},
        'cost_boundary':'complete warm pipeline; every paid attempt/draft/judge; direct repetitions averaged within question'}


def sample_protected(population_ids: list[str], n: int, seed: int = 271828) -> list[str]:
    if (not population_ids or any(type(i) is not str or not i for i in population_ids) or
            len(set(population_ids))!=len(population_ids) or type(n) is not int or not 1<=n<=len(population_ids)):
        raise ValueError('invalid population/sample size')
    if seed!=271828: raise ValueError('unamended sample seed')
    return np.random.Generator(np.random.PCG64(seed)).choice(sorted(population_ids),n,replace=False).tolist()


def plan_jobs(methods: dict, sampled_tasks: list) -> list[dict]:
    def identity(task): return task['task_id'] if isinstance(task,dict) else task.task_id
    if not sampled_tasks or len({identity(t) for t in sampled_tasks})!=len(sampled_tasks): raise ValueError('duplicate/empty sampled tasks')
    rows=[]
    for task in sorted(sampled_tasks,key=lambda t:content_hash([271828,'question-order',identity(t)])):
        tid=identity(task);task_hash=content_hash(task)
        def add(method,scope,repetition=0,arm=None):
            method=copy.deepcopy(method)
            if scope=='random': method['k']=10 if int(content_hash([271828,tid,'random-mixture']),16)/2**256<method['probability'] else 2
            family=method['family']
            roles=(['draft','answer_if_escalated'] if family=='POST-OUTCOME' else
                   ['judge','answer'] if family=='LLM-SUFFICIENCY' else ['answer'])
            row={'task_id':tid,'task_hash':task_hash,'method':method,'scope':scope,'arm':arm,
                 'mode':'direct','cache_mode':'none','repetition_id':repetition,'paid_roles':roles,
                 'generation_calls':{'min':2 if family=='LLM-SUFFICIENCY' else 1,
                                     'max':2 if family in ('POST-OUTCOME','LLM-SUFFICIENCY') else 1}}
            row['job_id']=content_hash(row);rows.append(row)
        regular=[(m,'representative') for m in methods['representatives']]+[(methods['anchor'],'anchor'),
                  (methods['random'],'random'),(methods['oracle_source'],'oracle-source')]
        for method,scope in sorted(regular,key=lambda pair:content_hash([271828,'representative-order',tid,pair[1],pair[0]['config_id']])):
            add(method,scope)
        for repetition in range(1,methods['repetitions']+1):
            for arm in sorted(('A','B'),key=lambda a:content_hash([271828,'pair-order',tid,repetition,a])):
                add(methods['selected'][arm],'primary',repetition,arm)
    return rows


def _source_files(config):
    names=sorted(set(map(str,config['source_files'])))
    return names if config.get('fixture',False) else execution_source_files(names)


def _capture_source(commit, source_files, fixture=False):
    if not isinstance(commit,str) or len(commit)!=40 or any(c not in '0123456789abcdef' for c in commit): raise ValueError('invalid source commit')
    if not fixture:
        head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        if commit!=head: raise ValueError('source commit must be current HEAD')
        for name in source_files:
            original=subprocess.check_output(['git','show',f'{commit}:{name}'])
            if hashlib.sha256(original).hexdigest()!=file_hash(name): raise ValueError('uncommitted execution source '+name)
    return {'commit':commit,'sha256':{name:file_hash(name) for name in source_files}}


def _hash_protocol(protocol):
    return content_hash({k:v for k,v in protocol.items() if k!='protocol_hash'})


def _attempted(protocol):
    root=Path(protocol['run_dir'])
    return (root/'protected-attempt.started.json').exists() or any(root.glob('jobs/*/attempt-*'))


def freeze(config: dict) -> dict:
    canonical_bytes(config)
    root=Path(config['output_dir'])
    if any((root/name).exists() for name in ('methods.json','sample.json','schedule.json','protocol.json')):
        raise ValueError('protocol already frozen or partially exists; never resample')
    methods=freeze_methods(config['development'],config['selection'],config['capacity'])
    n=_positive(config['n'],'sample size',True);forecast=methods['forecast']
    feasible=math.floor((forecast['available_seconds']-forecast['report_reserve_seconds']-forecast['fixed_remaining_seconds'])/forecast['conservative_seconds_per_question'])
    if n>feasible or n>len(config['population_ids']): raise ValueError('unfeasible sample size')
    source=_capture_source(config['source_commit'],_source_files(config),config.get('fixture',False))
    artifacts={str(p):file_hash(p) for p in config['artifact_files']}
    if config.get('artifact_manifest_path'):
        manifest=Path(config['artifact_manifest_path'])
        expected=_read(manifest)
        for name,digest in expected.items():
            if file_hash(name)!=digest:raise ValueError('artifact/dependency changed: '+name)
        artifacts.update(expected)
        artifacts[str(manifest)]=file_hash(manifest)
    methods['n']=n;methods['N']=len(config['population_ids'])
    methods['deadline_utc']=config['deadline_utc']
    # The write precedes selection and survives an interruption without resampling.
    atomic_json(root/'methods.json',methods)
    ids=sample_protected(config['population_ids'],n)
    byid={(t['task_id'] if isinstance(t,dict) else t.task_id):t for t in config['tasks']}
    if not set(ids)<=set(byid): raise ValueError('sample tasks missing')
    selected=[byid[i] for i in ids]
    sample={'population_hash':content_hash(sorted(config['population_ids'])),'N':len(config['population_ids']),
            'n':n,'seed':271828,'algorithm':'NumPy Generator PCG64 choice sorted IDs without replacement',
            'task_ids':ids,'tasks':json.loads(canonical_bytes(selected)),
            'document_ids_hash':content_hash(sorted({d for t in selected for d in (t['candidate_ids'] if isinstance(t,dict) else t.candidate_ids)}))}
    schedule={'jobs':plan_jobs(methods,selected),'assigned_task_ids':ids}
    atomic_json(root/'sample.json',sample);atomic_json(root/'schedule.json',schedule)
    protocol={'version':1,'methods':methods,'sample':sample,'schedule':schedule,
        'digests':{name:content_hash(value) for name,value in [('methods',methods),('sample',sample),('schedule',schedule)]},
        'source':source,'artifact_sha256':artifacts,'output_dir':str(root.resolve()),
        'run_dir':str(Path(config['run_dir']).resolve()),'fixture':config.get('fixture',False),'source_history':[],
        'created_utc':datetime.now(timezone.utc).isoformat()}
    protocol['protocol_hash']=_hash_protocol(protocol)
    atomic_json(root/'protocol.json',protocol)
    return verify_protocol(root/'protocol.json')


def _verify_science(protocol):
    canonical_bytes(protocol)
    if protocol.get('protocol_hash')!=_hash_protocol(protocol): raise ValueError('protocol checksum changed')
    root=Path(protocol['output_dir'])
    for key in ('methods','sample','schedule'):
        if (content_hash(protocol[key])!=protocol['digests'][key] or _read(root/(key+'.json'))!=protocol[key]):
            raise ValueError(key+' manifest digest changed')
    m,s=protocol['methods'],protocol['sample']
    if len(s['task_ids'])!=s['n'] or len(set(s['task_ids']))!=s['n'] or m['n']!=s['n'] or m['N']!=s['N']:
        raise ValueError('sample denominator changed')
    if [t['task_id'] for t in s['tasks']]!=s['task_ids']: raise ValueError('sample task identity changed')
    if protocol['schedule']!={'jobs':plan_jobs(m,s['tasks']),'assigned_task_ids':s['task_ids']}: raise ValueError('schedule changed')


def verify_protocol(protocol_path: Path) -> dict:
    protocol=_read(protocol_path);_verify_science(protocol)
    for name,digest in {**protocol['source']['sha256'],**protocol['artifact_sha256']}.items():
        if not Path(name).is_file() or file_hash(name)!=digest: raise ValueError('bound file checksum changed: '+name)
    return protocol


def bind_source(protocol: dict, commit: str) -> dict:
    _verify_science(protocol)
    if _attempted(protocol): raise ValueError('source binding forbidden after any protected attempt')
    for name,digest in protocol['artifact_sha256'].items():
        if file_hash(name)!=digest: raise ValueError('scientific artifact changed: '+name)
    updated=copy.deepcopy(protocol)
    source_files=list(protocol['source']['sha256'])
    if not protocol['fixture']: source_files=execution_source_files(source_files)
    updated['source']=_capture_source(commit,source_files,protocol['fixture'])
    updated['source_history'].append({'previous_source':protocol['source'],'previous_protocol_hash':protocol['protocol_hash'],
                                    'bound_utc':datetime.now(timezone.utc).isoformat(),'preserved_digests':protocol['digests']})
    updated['protocol_hash']=_hash_protocol(updated)
    atomic_json(Path(protocol['output_dir'])/'protocol.json',updated)
    return updated


def plan(protocol: dict, dry_run: bool = True) -> dict:
    if dry_run is not True: raise ValueError('plan is dry-run only; execution is a separate reviewed stage')
    _verify_science(protocol)
    jobs=protocol['schedule']['jobs'];m=protocol['methods'];n=m['n'];f=m['forecast']
    return {'protocol_hash':protocol['protocol_hash'],'assigned_unique_tasks':n,'population':m['N'],
        'jobs':len(jobs),'direct_primary_jobs':sum(j['scope']=='primary' for j in jobs),
        'generation_calls_if_complete_paths':{key:sum(j['generation_calls'][key] for j in jobs) for key in ('min','max')},
        'failure_qualification':'early terminal failures may prevent later calls; assigned denominator never shrinks',
        'estimated_job_bytes':math.ceil(n*f['bytes_per_question']),
        'conservative_confirmation_seconds':n*f['conservative_seconds_per_question'],
        'fixed_remaining_seconds':f['fixed_remaining_seconds'],'report_reserve_seconds':f['report_reserve_seconds'],
        'feasible':n*f['conservative_seconds_per_question']+f['fixed_remaining_seconds']+f['report_reserve_seconds']<=f['available_seconds']}


def main(args):
    if args.command=='plan':
        result=plan(verify_protocol(Path(args.protocol)),dry_run=True)
    else:
        config=_read(args.config)
        if getattr(args,'bind_source_only',False):
            protocol=_read(Path(config['output_dir'])/'protocol.json')
            result=bind_source(protocol,subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip())
        else:
            # Read only annotation-free prepared records. Gold is neither accepted nor imported.
            from .data_runtime import load_tasks
            config['selection']=_read(config.pop('selection_path'))
            config['capacity']=_read(config.pop('capacity_path'))
            config['development']=_read(config.pop('development_path'))
            manifest=_read(Path(config['prepared_dir'])/'manifest.json')
            config['population_ids']=manifest['reservations']['protected']
            config['tasks']=load_tasks(Path(config['prepared_dir'])/'tasks.jsonl','protected')
            config['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
            result=freeze(config)
        result=plan(result)
    print(json.dumps(result,allow_nan=False))
    return 0


def execution_source_files(extra=()):
    """Explicit runtime list; later execution tools are added before the final seal."""
    names=[f'src/outcome_poc/{name}.py' for name in EXECUTION_MODULES]
    names += ['requirements.lock','configs/frozen.json','tools/task13_calibrate.py','tools/task14_native.py']
    return sorted({str(p) for p in [*names,*extra] if Path(p).is_file()})


def verify_job(protocol, row, task, runtime_settings, *, job_index=None):
    """Cheap per-job check after verify_protocol initializes the execution snapshot."""
    if job_index is None: job_index={j['job_id']:j for j in protocol['schedule']['jobs']}
    if job_index.get(row.get('job_id'))!=row or content_hash(task)!=row['task_hash']:
        raise ValueError('job/task does not match frozen schedule')
    if any(runtime_settings.get(k)!=v for k,v in protocol['methods']['reader'].items()):
        raise ValueError('runtime settings differ from frozen reader')
    if row['mode']!='direct' or row['cache_mode']!='none': raise ValueError('confirmation must be fresh direct execution')
    return row


def materialize_policy(spec, models):
    """Use already verified/loaded local gates; no model file loads per query."""
    from .policies import FixedPolicy, AdaptiveKPolicy, ThresholdPolicy, PostOutcomePolicy, SufficiencyPolicy
    family=spec['family']
    if family=='FIXED': return FixedPolicy(spec['k'])
    if family.startswith('ADAPTIVE-k'): return AdaptiveKPolicy(spec['buffer'],variant='published' if family.endswith('published') else 'tuned')
    if family=='LLM-SUFFICIENCY': return SufficiencyPolicy()
    if family in ('RANDOM-MIXTURE','NO-CONTEXT-DIAGNOSTIC'): return DiagnosticPolicy(family,spec.get('k',0))
    cls=PostOutcomePolicy if family=='POST-OUTCOME' else ThresholdPolicy
    return cls(models[spec['model_name']],{'policy_id':spec['model_name'],
        'threshold_mode':spec['threshold_mode'],'threshold':spec['threshold']})


class DiagnosticPolicy:
    def __init__(self, identity, k):
        if identity not in ('RANDOM-MIXTURE','NO-CONTEXT-DIAGNOSTIC') or k not in (0,2,10):
            raise ValueError('invalid diagnostic policy')
        if (identity=='NO-CONTEXT-DIAGNOSTIC')!=(k==0): raise ValueError('diagnostic action scope mismatch')
        self.policy_id,self.k=identity,k

    def choose(self, question, ranked, paid_draft=None, *, caller_cap=10):
        from dataclasses import replace
        from .policies import FixedPolicy
        from .schemas import Decision
        from .features import feature_schema
        if self.k:
            return replace(FixedPolicy(self.k).choose(question,ranked,paid_draft,caller_cap=caller_cap),policy_id=self.policy_id)
        if paid_draft is not None: raise ValueError('no-context rejects draft')
        return Decision(self.policy_id,0,None,None,None,'no_context_diagnostic',feature_schema()['hash'],0,0)

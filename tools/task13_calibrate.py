"""Development-only prospective capacity and complete-roster timing calibration.

Use prepare on committed source, then run its source snapshot under native.sb.
The only decoder modification is scoped EOS suppression for marked synthetic
maximum-output requests, whose distinct role is explicit in the plan/receipts.
"""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

from outcome_poc.storage import atomic_json, append_jsonl, canonical_bytes, content_hash, read_jsonl
from outcome_poc.protocol import file_hash, execution_source_files, materialize_policy, plan_jobs, _policy

MARKER='SYNTHETIC MAXIMUM OUTPUT CALIBRATION'


def choose_calibration_tasks(tasks,lengths,per_stratum=4):
    if any(t.split not in ('pilot','fit','tune') for t in tasks): raise ValueError('development only calibration')
    ordered=sorted(tasks,key=lambda t:(lengths[t.task_id],t.task_id))
    if len(ordered)<3*per_stratum: raise ValueError('insufficient development strata')
    result=[]
    for number in range(3):
        group=ordered[len(ordered)*number//3:len(ordered)*(number+1)//3]
        result.extend(t.task_id for t in sorted(group,key=lambda t:content_hash([271828,'task13-calibration',t.task_id]))[:per_stratum])
    return result


@contextmanager
def force_max_output(module,eos_ids):
    original=module.stream_generate
    def suppress(tokens,logits):
        import mlx.core as mx
        mask=mx.zeros(logits.shape[-1],dtype=logits.dtype)
        mask[mx.array(list(eos_ids))]=-float('inf')
        return logits+mask
    def wrapped(*args,**kwargs):
        return original(*args,**kwargs,logits_processors=[suppress])
    module.stream_generate=wrapped
    try: yield suppress
    finally: module.stream_generate=original


class CalibrationFactory:
    def __init__(self,path,settings):self.path,self.settings=path,settings
    def __call__(self):
        from outcome_poc.generation import ReaderBackend
        class CalibrationBackend(ReaderBackend):
            def generate(self,prompt,request,**kwargs):
                if MARKER not in prompt: return super().generate(prompt,request,**kwargs)
                import mlx_lm
                with force_max_output(mlx_lm,self.tokenizer.eos_token_ids):
                    result=super().generate(prompt,request,**kwargs)
                if result.generated_tokens!=256 or result.prompt_tokens!=7936:
                    raise ValueError('forced maximum calibration did not reach exact limits')
                return result
        backend=CalibrationBackend();backend.load(Path(self.path),self.settings);return backend


def _artifact_paths(config):
    manifest=json.loads(Path(config['inputs']['asset_manifest']).read_text())
    paths=[Path(config['inputs']['asset_manifest']),Path(config['selection_path']),Path('requirements.lock')]
    for role in ('reader','encoder','original_reader'):
        asset=manifest['assets'][role]
        paths.extend(Path(asset['local_path'])/name for name in asset['files'])
    for root in (config['training_dir'],config['post_training_dir']):
        origin=Path(root)/'fit-origin.json';paths.append(origin)
        models=json.loads(origin.read_text())['models']
        paths.extend(Path(m['artifact_root'])/m['artifact_file'] for m in models.values())
    paths.extend(Path(config['inputs']['prepared_dir'])/name for name in ('manifest.json','tasks.jsonl','documents.jsonl'))
    paths.extend(p for p in Path(config['index_dir']).rglob('*') if p.is_file())
    packages=Path('.venv/lib/python3.12/site-packages')
    for package in ('mlx_lm','sentence_transformers','transformers','tokenizers','sklearn','numpy','mlx'):
        paths.extend(p for p in (packages/package).rglob('*') if p.is_file() and p.suffix in ('.py','.so','.dylib'))
    return sorted(set(paths))


def prepare(config_path):
    from outcome_poc.data_runtime import load_tasks,DocumentStore
    from outcome_poc.select import native_sandbox_profile
    start=time.perf_counter_ns();config=json.loads(Path(config_path).read_text())
    source_files=execution_source_files([str(config_path)])
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    from outcome_poc.protocol import _capture_source
    source=_capture_source(commit,source_files)
    root=Path(config['prelaunch_dir']);root.mkdir(parents=True,exist_ok=False)
    snapshot=root/'source'
    for name in source_files:
        destination=snapshot/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(name,destination)
    binding={'source':source,'artifact_sha256':{str(p):file_hash(p) for p in _artifact_paths(config)},
             'captured_utc':datetime.now(timezone.utc).isoformat(),'config_hash':content_hash(config)}
    atomic_json(root/'binding.json',binding)
    tasks=load_tasks(Path(config['inputs']['prepared_dir'])/'tasks.jsonl','tune')
    documents=DocumentStore(Path(config['inputs']['prepared_dir'])/'documents.jsonl')
    lengths={t.task_id:len(t.question)+sum(documents.get(i).character_count+len(documents.get(i).title) for i in t.candidate_ids) for t in tasks}
    ids=choose_calibration_tasks(tasks,lengths,config['per_stratum'])
    window=json.loads(Path('artifacts/provenance/execution-window.json').read_text())
    plan={'binding_path':str(root/'binding.json'),'binding_hash':content_hash(binding),'source_snapshot':str(snapshot),
        'config':str(snapshot/config_path),'run_dir':config['run_dir'],'task_ids':ids,
        'lengths':{i:lengths[i] for i in ids},'strata':{i:k//config['per_stratum'] for k,i in enumerate(ids)},
        'deadline_utc':window['deadline_utc'],'full_roster_repetitions':2,'total_pair_repetitions':4,
        'synthetic_cases':2,'synthetic_prompt_tokens':7936,'forced_output_tokens':256,
        'synthetic_sampler':'greedy with EOS logits suppressed only on synthetic marked capacity requests',
        'warmup_jobs':2,'no_context_ids':sorted(ids,key=lambda i:content_hash([271828,'task13-no-context',i]))[:4],
        'prepare_seconds':(time.perf_counter_ns()-start)/1e9}
    atomic_json(root/'plan.json',plan)
    (root/'native.sb').write_text(native_sandbox_profile(Path.cwd(),Path(config['inputs']['prepared_dir'])))
    atomic_json(Path('artifacts/provenance/task13-calibration-prelaunch.json'),
        {'source_commit':commit,'binding_hash':plan['binding_hash'],'plan_sha256':file_hash(root/'plan.json'),
         'sandbox_sha256':file_hash(root/'native.sb'),'binding_path':str(root/'binding.json'),
         'task_count':len(ids),'task_ids_hash':content_hash(ids),'prepare_seconds':plan['prepare_seconds']})
    return plan


def run(plan_path):
    import psutil
    from outcome_poc.assets import verify_configured_assets
    from outcome_poc.data_runtime import DocumentStore,load_tasks
    from outcome_poc.environment import discover,resource_gate
    from outcome_poc.generation import SupervisedBackend,Reader,offline_network,render_prompt
    from outcome_poc.retrieval import EncoderBackend,Retrieval
    from outcome_poc.runner import Runtime,execute_job,close_run,record_shared_cost
    from outcome_poc.schemas import Task
    start=time.perf_counter_ns();plan=json.loads(Path(plan_path).read_text())
    binding=json.loads(Path(plan['binding_path']).read_text())
    if content_hash(binding)!=plan['binding_hash']:raise ValueError('prelaunch binding changed')
    for name,digest in binding['artifact_sha256'].items():
        if file_hash(name)!=digest:raise ValueError('artifact changed '+name)
    for name,digest in binding['source']['sha256'].items():
        if file_hash(Path(plan['source_snapshot'])/name)!=digest:raise ValueError('source snapshot changed '+name)
    config=json.loads(Path(plan['config']).read_text())
    if content_hash(config)!=binding['config_hash']:raise ValueError('configuration changed')
    root=Path(plan['run_dir']);root.mkdir(parents=True,exist_ok=False)
    if datetime.now(timezone.utc)>=datetime.fromisoformat(plan['deadline_utc']):raise TimeoutError('deadline')
    probe="import errno,json,socket,sys\nr={}\nfor i,p in enumerate(sys.argv[1:]):\n try: open(p,'rb').read(1)\n except PermissionError: r[str(i)]=True\n else: r[str(i)]=False\ns=socket.socket();s.settimeout(.1)\ntry:s.connect(('1.1.1.1',443))\nexcept OSError as e:r['network']=e.errno in (errno.EPERM,errno.EACCES)\nelse:r['network']=False\nprint(json.dumps(r))"
    denied=['data/prepared/gold/gold.jsonl','models/pinned/data/hotpot_train_v1.1.json','models/pinned/data/hotpot_dev_distractor_v1.json','artifacts/runs/task10-fit256/scores.gold.jsonl','artifacts/runs/task12-tune128-retry/scores.gold.jsonl']
    denials=json.loads(subprocess.run([sys.executable,'-c',probe,*denied],capture_output=True,text=True,check=True).stdout)
    atomic_json(root/'os-denials.json',denials)
    if not all(denials.values()):raise ValueError('independent OS gold/raw/projection/network denial failed')
    env=discover(root/'environment')
    if not env['native_supported'] or not env['resource_gate']['passed']:raise ValueError('native prerequisites')
    process=psutil.Process();peak=[process.memory_info().rss];stop=threading.Event()
    def monitor():
        while not stop.wait(.05):
            try:peak[0]=max(peak[0],process.memory_info().rss+sum(p.memory_info().rss for p in process.children(recursive=True) if p.is_running()))
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    observer=threading.Thread(target=monitor,daemon=True);observer.start()
    manifest=json.loads(Path(config['inputs']['asset_manifest']).read_text())
    verify_configured_assets({r:config[r] for r in ('reader','encoder','original_reader')},{'required':['reader','encoder','original_reader'],'assets':manifest['assets']})
    tasks_by_id={t.task_id:t for t in load_tasks(Path(config['inputs']['prepared_dir'])/'tasks.jsonl','tune')}
    tasks=[tasks_by_id[i] for i in plan['task_ids']]
    documents=DocumentStore(Path(config['inputs']['prepared_dir'])/'documents.jsonl')
    selection=json.loads(Path(config['selection_path']).read_text())
    methods={'representatives':[_policy(v['representative']) for k,v in sorted(selection['families'].items())],
        'anchor':_policy(selection['fixed_ten_anchor']),'oracle_source':{'config_id':'FIXED-2','family':'FIXED','k':2},
        'selected':{'A':_policy(selection['A*']),'B':_policy(selection['B*'])},'repetitions':2,
        'random':{'config_id':'RANDOM-MIXTURE','family':'RANDOM-MIXTURE','probability':selection['A*']['fit_escalation_probability']}}
    models={};model_manifests={}
    from outcome_poc.train import load_gate
    for dirname in (config['training_dir'],config['post_training_dir']):
        model_manifests.update(json.loads((Path(dirname)/'fit-origin.json').read_text())['models'])
    for name,value in model_manifests.items():models[name]=load_gate(value)
    with offline_network() as network:
        encoder=EncoderBackend(Path(manifest['assets']['encoder']['local_path']))
        retrieval=Retrieval(Path(config['index_dir']),documents,encoder)
        asset=manifest['assets']['reader']
        with SupervisedBackend(CalibrationFactory(str(asset['local_path']),{**config['reader'],'asset':asset})) as backend:
            settings={'model_revision':asset['revision'],'model_hash':asset['snapshot_hash'],
                'decoding_hash':content_hash({**config['reader'],'temperature':0,'draft_model':None,'max_kv_size':None,'kv_bits':None}),
                **{k:config['reader'][k] for k in ('max_context_tokens','max_new_tokens','timeout_seconds')},
                'backend':'persistent-supervised-native-mlx','prompt_version':1,'source_binding':plan['binding_hash'],
                'index_manifest_hash':content_hash(retrieval.manifest)}
            runtime=Runtime(retrieval,documents,Reader(backend),settings)
            # Capacity prompts are synthetic. Natural development questions remain untouched.
            synthetic=[]
            for number in range(plan['synthetic_cases']):
                question=MARKER+f' case {number}. Continue writing numbered words without stopping.'
                base=len(backend.tokenizer.encode(render_prompt(question,[],{},backend.tokenizer),add_special_tokens=False))
                question+=' a'*(7936-base)
                if len(backend.tokenizer.encode(render_prompt(question,[],{},backend.tokenizer),add_special_tokens=False))!=7936:
                    raise ValueError('synthetic rendered prompt construction failed')
                synthetic.append(Task(f'synthetic-capacity-{number}','pilot',question,tasks[0].candidate_ids))
            def decorate(row,phase):
                return {**row,'phase':phase,'job_id':content_hash([plan['binding_hash'],phase,row])}
            rows=[]
            for number in range(2):
                rows.append(decorate({'task_id':tasks[0].task_id,'method':{'family':'FIXED','config_id':'FIXED-10','k':10},
                    'repetition_id':number,'scope':'warmup','arm':None},'warmup'))
            rows += [decorate(row,'full-roster') for row in plan_jobs(methods,tasks)]
            extra=plan_jobs({**methods,'repetitions':4},tasks)
            rows += [decorate(row,'later-pair-block') for row in extra if row['scope']=='primary' and row['repetition_id']>2]
            for t in synthetic:
                rows.append(decorate({'task_id':t.task_id,'method':{'family':'NO-CONTEXT-DIAGNOSTIC','config_id':'NO-CONTEXT-DIAGNOSTIC'},
                    'repetition_id':0,'scope':'synthetic-capacity','arm':None},'synthetic-capacity'))
            for tid in plan['no_context_ids']:
                rows.append(decorate({'task_id':tid,'method':{'family':'NO-CONTEXT-DIAGNOSTIC','config_id':'NO-CONTEXT-DIAGNOSTIC'},
                    'repetition_id':0,'scope':'no-context','arm':None},'no-context'))
            all_tasks={**tasks_by_id,**{t.task_id:t for t in synthetic}}
            jobs=[{**row,'task':all_tasks[row['task_id']],'policy':materialize_policy(row['method'],models),
                'run_id':root.name,'protocol_hash':'development-task13-'+plan['binding_hash'],'mode':'direct','cache_mode':'none',
                'allow_no_context_diagnostic':row['method']['family']=='NO-CONTEXT-DIAGNOSTIC'} for row in rows]
            atomic_json(root/'schedule.json',{'jobs':rows,'settings':settings,'plan':plan,'model_manifests':model_manifests})
            setup_stop=time.perf_counter_ns();record_shared_cost(root,'cold_setup',start,setup_stop,[j['job_id'] for j in jobs],source_id='task13-native-setup')
            runtime._lifecycle_seen=len(backend.lifecycle)
            operational=[]
            for number,job in enumerate(jobs):
                if datetime.now(timezone.utc)>=datetime.fromisoformat(plan['deadline_utc']):raise TimeoutError('deadline')
                runtime.config={**settings,'decoding_hash':content_hash([settings['decoding_hash'],'synthetic-only-greedy-EOS-suppression'])} if job['phase']=='synthetic-capacity' else settings
                if number%18==0:
                    power=subprocess.run(['/usr/bin/pmset','-g','batt'],capture_output=True,text=True)
                    append_jsonl(root/'power.jsonl',{'utc':datetime.now(timezone.utc).isoformat(),'completed_before':number,'pmset_stdout':power.stdout,'returncode':power.returncode})
                p=execute_job(job,runtime,root)
                record={'job_id':p.job_id,'task_id':p.task_id,'phase':job['phase'],'scope':job['scope'],
                    'arm':job['arm'],'repetition_id':p.repetition_id,'elapsed_seconds':p.elapsed_seconds,
                    'generation_calls':p.generation_calls,'status':p.status,'generated_tokens':p.generated_tokens,
                    'prompt_tokens':p.prompt_tokens,'output_hash':content_hash([p.raw_output,p.status,p.answer,p.citations])}
                operational.append(record);append_jsonl(root/'operational.jsonl',record)
                append_jsonl(root/'resources.jsonl',{'job_id':p.job_id,**backend.last_resources})
                if number%18==0:print(json.dumps({'completed':number+1,'assigned':len(jobs),'phase':job['phase']}),flush=True)
            closure=close_run(root,jobs)
    stop.set();observer.join()
    resources=list(read_jsonl(root/'resources.jsonl'));peak_mlx=max((r.get('peak_mlx_bytes') or 0 for r in resources),default=0)
    summary={'source_binding_hash':plan['binding_hash'],'closure':closure,'assigned_jobs':len(jobs),
        'generation_calls':sum(r['generation_calls'] for r in operational),'elapsed_seconds':(time.perf_counter_ns()-start)/1e9,
        'os_denials':denials,'network_attempts':len(network),'sampled_peak_process_tree_rss_bytes':peak[0],'peak_mlx_bytes':peak_mlx,
        'resource_bound_kind':'sampled parent+recursive-child RSS plus overlapping MLX conservative bound',
        'resource_gate':resource_gate(env['physical_memory_bytes'],peak[0]+peak_mlx)}
    atomic_json(root/'native-summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='closure'}),flush=True)
    return summary


if __name__=='__main__':
    if sys.argv[1]=='prepare': print(json.dumps(prepare(Path(sys.argv[2])),allow_nan=False))
    elif sys.argv[1]=='run': run(Path(sys.argv[2]))
    else: raise ValueError('prepare or run required')

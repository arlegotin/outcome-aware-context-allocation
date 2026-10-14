"""Frozen, annotation-free development checks; invoke under independent OS denial."""
import json
from pathlib import Path
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone

from outcome_poc.assets import verify_configured_assets
from outcome_poc.data_runtime import DocumentStore, load_tasks
from outcome_poc.environment import discover, resource_gate
from outcome_poc.generation import (NativeReaderFactory, SupervisedBackend, Reader, offline_network,
                                    common_prefix_length, prompt_identity)
from outcome_poc.policies import PostOutcomePolicy, SufficiencyPolicy
from outcome_poc.retrieval import EncoderBackend, Retrieval
from outcome_poc.runner import (Runtime, execute_job, close_run, action_signature, job_id,
                                record_shared_cost, load_events, optimistic_post_cost)
from outcome_poc.schemas import GenerationRequest
from outcome_poc.storage import atomic_json, append_jsonl, content_hash


def main():
    start=time.perf_counter_ns()
    plan=json.loads(Path(sys.argv[1]).read_text())
    root=Path(plan['run_dir']);root.mkdir(parents=True,exist_ok=False)
    config=json.loads(Path(plan['config']).read_text())
    if datetime.now(timezone.utc) >= datetime.fromisoformat(plan['deadline_utc']): raise TimeoutError('deadline')
    probe="import errno,json,socket,sys\nr={}\nfor i,p in enumerate(sys.argv[1:]):\n try: open(p,'rb').read(1)\n except PermissionError: r[str(i)]=True\n else: r[str(i)]=False\ns=socket.socket();s.settimeout(.1)\ntry: s.connect(('1.1.1.1',443))\nexcept OSError as e: r['network']=e.errno in (errno.EPERM,errno.EACCES)\nelse: r['network']=False\nprint(json.dumps(r))"
    denied=['data/prepared/gold/gold.jsonl','models/pinned/data/hotpot_train_v1.1.json','models/pinned/data/hotpot_dev_distractor_v1.json', 'artifacts/runs/task10-fit256/scores.gold.jsonl']
    denials=json.loads(subprocess.run([sys.executable,'-c',probe,*denied],capture_output=True,text=True,check=True).stdout)
    atomic_json(root/'os-denials.json',denials)
    if not all(denials.values()): raise ValueError('OS isolation required')
    environment=discover(root/'environment')
    if not environment['native_supported'] or not environment['resource_gate']['passed']: raise ValueError('native prerequisites')
    manifest=json.loads(Path(config['inputs']['asset_manifest']).read_text())
    verify_configured_assets({r:config[r] for r in ('reader','encoder','original_reader')},
                            {'required':['reader','encoder','original_reader'],'assets':manifest['assets']})
    byid={t.task_id:t for t in load_tasks(Path(config['inputs']['prepared_dir'])/'tasks.jsonl','fit')}
    tasks=[byid[i] for i in plan['task_ids']]
    selected=sorted(byid,key=lambda i:content_hash([271828,'task11-development-parity',i]))[:plan['development_count']]
    if selected != plan['task_ids']: raise ValueError('development selection changed')
    documents=DocumentStore(Path(config['inputs']['prepared_dir'])/'documents.jsonl')
    records=[]; fixture_rows=[]; resources=[]
    with offline_network() as attempts:
        encoder=EncoderBackend(Path(manifest['assets']['encoder']['local_path']))
        retrieval=Retrieval(Path(config['inputs']['fit_index_dir']),documents,encoder)
        asset=manifest['assets']['reader']
        with SupervisedBackend(NativeReaderFactory(Path(asset['local_path']),{**config['reader'],'asset':asset})) as backend:
            settings={'model_revision':asset['revision'],'model_hash':asset['snapshot_hash'],
                'decoding_hash':content_hash({**config['reader'],'temperature':0,'draft_model':None,'max_kv_size':None,'kv_bits':None}),
                **{k:config['reader'][k] for k in ('max_context_tokens','max_new_tokens','timeout_seconds')},
                'backend':'persistent-supervised-native-mlx-task11','prompt_version':1,
                'source_binding':plan['source_binding_hash'],'index_manifest_hash':content_hash(retrieval.manifest)}
            runtime=Runtime(retrieval,documents,Reader(backend),settings)
            jobs=[]
            for task in tasks:
                for arm,mode,policy in [('post-none','none',PostOutcomePolicy(None,{'threshold_mode':'always_ten','threshold':None})),
                                        ('post-prefix','within_query_prefix',PostOutcomePolicy(None,{'threshold_mode':'always_ten','threshold':None})),
                                        ('judge','none',SufficiencyPolicy())]:
                    signature=action_signature(task,settings,task.candidate_ids,arm,mode)
                    jobs.append({'task':task,'policy':policy,'run_id':root.name,'protocol_hash':'development-task11',
                        'job_id':job_id(signature,'direct:'+arm,0),'mode':'direct','arm':arm,'cache_mode':mode,'repetition_id':0})
            atomic_json(root/'schedule.json',{'jobs':[{k:v for k,v in j.items() if k!='policy'} for j in jobs],
                                              'runtime_config':settings,'plan':plan})
            setup_stop=time.perf_counter_ns()
            record_shared_cost(root,'cold_setup',start,setup_stop,[j['job_id'] for j in jobs],source_id='task11-native-setup')
            # Initial worker load is enclosed by recorded setup.
            runtime._lifecycle_seen=len(backend.lifecycle)
            for j in jobs:
                p=execute_job(j,runtime,root)
                records.append(p)
                resources.append(dict(backend.last_resources))
                append_jsonl(root/'resources.jsonl',{'job_id':j['job_id'],**backend.last_resources})
                print(json.dumps({'job':j['job_id'],'arm':j['arm'],'status':p.status,'seconds':p.elapsed_seconds,'calls':p.generation_calls}),flush=True)
            closure=close_run(root,jobs)
            # Synthetic prompt/token boundary checks are separately paid; not task-quality evidence.
            for case in plan['boundary_cases']:
                c=case['common']
                a=('a '+'a '*(c-1)+'x') if c else 'x'
                b=('a '+'a '*(c-1)+'y') if c else 'y'
                if case.get('identical'): a=b='a a a'
                ids_a=backend.tokenizer.encode(a,add_special_tokens=False)
                ids_b=backend.tokenizer.encode(b,add_special_tokens=False)
                expected=min(common_prefix_length(ids_a,ids_b),len(ids_a)-1,len(ids_b)-1)
                if not case.get('identical') and expected != c: raise ValueError('boundary token construction mismatch')
                handle={'scope':'synthetic:'+case['name'],'target_prompt':b,'source_prompt_hash':prompt_identity(a,backend.tokenizer)}
                outcomes=[]
                for role,prompt,mode in [('draft',a,'within_query_prefix'),('reuse',b,'within_query_prefix'),('fresh',b,'none')]:
                    request=GenerationRequest(asset['revision'],asset['snapshot_hash'],prompt_identity(prompt,backend.tokenizer),
                        settings['decoding_hash'],'smoke',8192,16,120.,mode)
                    before=time.perf_counter_ns()
                    callid=case['name']+':'+role
                    append_jsonl(root/'boundary-started.jsonl',{'call_id':callid,'start_ns':before,'request':request,'prompt':prompt})
                    result=backend.generate(prompt,request,rendered=True,
                        **({'prefix_cache':{**handle,'operation':'capture' if role=='draft' else 'reuse'}} if mode!='none' else {}))
                    after=time.perf_counter_ns()
                    row={'call_id':callid,'result':result,'start_ns':before,'stop_ns':after,'elapsed_seconds':(after-before)/1e9,
                         'resources':backend.last_resources}
                    append_jsonl(root/'boundary-results.jsonl',row);outcomes.append(result);resources.append(dict(backend.last_resources))
                x,y=outcomes[1:]
                errors=[abs(a-b) for a,b in zip(x.telemetry.get('selected_token_logprobs',[]),y.telemetry.get('selected_token_logprobs',[]))]
                fixture_rows.append({'case':case['name'],'common_tokens':expected,'token_parity':x.generated_token_ids==y.generated_token_ids,
                    'max_logprob_difference':max(errors,default=None),'reused_tokens':x.telemetry.get('reused_prompt_tokens'),
                    'statuses':[o.status for o in outcomes]})
                atomic_json(root/'boundary-summary.json',fixture_rows)
                print(json.dumps(fixture_rows[-1]),flush=True)
    peak_mlx=max((r.get('peak_mlx_bytes') or 0 for r in resources),default=0)
    peak_rss=max((r.get('rss_bytes') or 0 for r in resources),default=0)
    summary={'run_dir':str(root),'record_count':len(records),'generation_calls':sum(p.generation_calls for p in records),
        'synthetic_calls':len(fixture_rows)*3,'os_denials':denials,'network_attempts':len(attempts),
        'resource_gate':resource_gate(environment['physical_memory_bytes'],peak_mlx+peak_rss),
        'peak_mlx_bytes':peak_mlx,'peak_worker_rss_bytes':peak_rss,
        'elapsed_seconds':(time.perf_counter_ns()-start)/1e9,'boundary_cases':fixture_rows,
        'source_binding_hash':plan['source_binding_hash'],'status_counts':{s:sum(p.status==s for p in records) for s in sorted({p.status for p in records})}}
    atomic_json(root/'native-summary.json',summary)
    print(json.dumps(summary),flush=True)


if __name__ == '__main__': main()

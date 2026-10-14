"""Prospectively bound, OS-isolated annotation-free tune acquisition."""
import json
from pathlib import Path
import subprocess
import sys
import time
import threading
from datetime import datetime, timezone

import psutil

from outcome_poc.assets import verify_configured_assets
from outcome_poc.data_runtime import DocumentStore, load_tasks
from outcome_poc.environment import discover, resource_gate
from outcome_poc.generation import NativeReaderFactory, SupervisedBackend, Reader, offline_network
from outcome_poc.retrieval import EncoderBackend, Retrieval
from outcome_poc.runner import Runtime, _digest
from outcome_poc.select import tune
from outcome_poc.storage import atomic_json, content_hash, read_jsonl


def main():
    start=time.perf_counter_ns()
    plan=json.loads(Path(sys.argv[1]).read_text())
    binding=json.loads(Path(plan['binding_path']).read_text())
    if content_hash(binding)!=plan['source_binding_hash']: raise ValueError('source binding digest changed')
    for name,digest in binding['sha256'].items():
        if _digest(Path(name))!=digest: raise ValueError('prelaunch source/config/assets changed: '+name)
    snapshot=Path(binding['source_snapshot'])
    for name,digest in binding['snapshot_sha256'].items():
        if _digest(snapshot/name)!=digest: raise ValueError('executed snapshot changed: '+name)
    config=json.loads(Path(plan['config']).read_text())
    root=Path(plan['run_dir']);root.mkdir(parents=True,exist_ok=False)
    if datetime.now(timezone.utc)>=datetime.fromisoformat(plan['deadline_utc']): raise TimeoutError('deadline')
    probe="import errno,json,socket,sys\nr={}\nfor i,p in enumerate(sys.argv[1:]):\n try: open(p,'rb').read(1)\n except PermissionError: r[str(i)]=True\n else: r[str(i)]=False\ns=socket.socket();s.settimeout(.1)\ntry: s.connect(('1.1.1.1',443))\nexcept OSError as e: r['network']=e.errno in (errno.EPERM,errno.EACCES)\nelse: r['network']=False\nprint(json.dumps(r))"
    denied=['data/prepared/gold/gold.jsonl','models/pinned/data/hotpot_train_v1.1.json',
            'models/pinned/data/hotpot_dev_distractor_v1.json','artifacts/runs/task10-fit256/scores.gold.jsonl']
    denials=json.loads(subprocess.run([sys.executable,'-c',probe,*denied],capture_output=True,text=True,check=True).stdout)
    atomic_json(root/'os-denials.json',denials)
    if not all(denials.values()): raise ValueError('independent OS gold/raw/projection/network denial required')
    process=psutil.Process();peak_rss=[process.memory_info().rss];stop=threading.Event()
    def monitor():
        while not stop.wait(.02):
            try:
                rss=process.memory_info().rss+sum(p.memory_info().rss for p in process.children(recursive=True) if p.is_running())
                peak_rss[0]=max(peak_rss[0],rss)
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
    observer=threading.Thread(target=monitor,daemon=True);observer.start()
    environment=discover(root/'environment')
    if not environment['native_supported'] or not environment['resource_gate']['passed']: raise ValueError('native prerequisites')
    manifest=json.loads(Path(config['inputs']['asset_manifest']).read_text())
    verify_configured_assets({r:config[r] for r in ('reader','encoder','original_reader')},
                            {'required':['reader','encoder','original_reader'],'assets':manifest['assets']})
    prepared=Path(config['inputs']['prepared_dir'])
    reservations=json.loads((prepared/'manifest.json').read_text())['reservations']
    ids=reservations['tune']
    byid={t.task_id:t for t in load_tasks(prepared/'tasks.jsonl','tune')}
    if len(ids)!=128 or set(byid)!=set(ids) or ids!=plan['task_ids']: raise ValueError('fixed tune128 reservation required')
    tasks=[byid[i] for i in ids]
    checks=sorted(ids,key=lambda i:content_hash([271828,'task12-direct-reconstruction',i]))[:config['tuning']['direct_check_count']]
    if checks!=plan['direct_check_ids']: raise ValueError('prospective direct check selection changed')
    models={}
    for origin in (Path(config['training']['output_dir'])/'fit-origin.json',
                   Path(config['tuning']['post_training_dir'])/'fit-origin.json'):
        models.update(json.loads(origin.read_text())['models'])
    expected={'PRE-OUTCOME-GBM','PRE-RF','QUERY-ONLY','PROXY-LABEL','SHUFFLED-LABEL-GBM',
              'PRE-LINEAR-0.1','PRE-LINEAR-1','PRE-LINEAR-10','PRE-LINEAR-100','POST-OUTCOME'}
    if set(models)!=expected: raise ValueError('all fitted family origins required')
    documents=DocumentStore(prepared/'documents.jsonl')
    with offline_network() as attempts:
        encoder=EncoderBackend(Path(manifest['assets']['encoder']['local_path']))
        retrieval=Retrieval(Path(config['tuning']['index_dir']),documents,encoder)
        asset=manifest['assets']['reader']
        with SupervisedBackend(NativeReaderFactory(Path(asset['local_path']),{**config['reader'],'asset':asset})) as backend:
            settings={'model_revision':asset['revision'],'model_hash':asset['snapshot_hash'],
                'decoding_hash':content_hash({**config['reader'],'temperature':0,'draft_model':None,'max_kv_size':None,'kv_bits':None}),
                **{k:config['reader'][k] for k in ('max_context_tokens','max_new_tokens','timeout_seconds')},
                'backend':'persistent-supervised-native-mlx-task12','prompt_version':1,
                'source_binding':plan['source_binding_hash'],'index_manifest_hash':content_hash(retrieval.manifest)}
            runtime=Runtime(retrieval,documents,Reader(backend),settings)
            result=tune({'tasks':tasks,'assigned_ids':ids,'run_dir':str(root),'models':models,
                        'setup_interval':[start,time.perf_counter_ns()],'deadline_utc':plan['deadline_utc'],
                        'direct_check_ids':checks},runtime)
    stop.set();observer.join()
    resources=list(read_jsonl(root/'resources.jsonl'))
    peak_mlx=max((r.get('peak_mlx_bytes') or 0 for r in resources),default=0)
    summary={**{k:v for k,v in result.items() if k!='closure'},'elapsed_seconds':(time.perf_counter_ns()-start)/1e9,
             'source_binding_hash':plan['source_binding_hash'],'os_denials':denials,'network_attempts':len(attempts),
             'peak_mlx_bytes':peak_mlx,'sampled_peak_process_tree_rss_bytes':peak_rss[0],
             'resource_bound_kind':'sampled parent plus recursive child RSS plus MLX overlapping conservative bound',
             'resource_gate':resource_gate(environment['physical_memory_bytes'],peak_rss[0]+peak_mlx)}
    atomic_json(root/'native-summary.json',summary)
    print(json.dumps(summary),flush=True)


if __name__=='__main__': main()

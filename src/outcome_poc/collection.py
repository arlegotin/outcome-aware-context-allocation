"""Annotation-free fit acquisition; scoring and learning run in separate processes."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from .data_runtime import load_tasks
from .features import build_features, feature_schema
from .policies import FixedPolicy
from .runner import (action_signature, job_id, execute_job, close_run, accounting,
                     record_shared_cost, _consume_worker_lifecycle)
from .storage import atomic_json, content_hash, append_jsonl, read_jsonl
from .timing import TimingLedger


def load_fit_inputs(config):
    prepared = Path(config['inputs']['prepared_dir'])
    reservations = json.loads((prepared/'manifest.json').read_text())['reservations']
    identities = reservations['fit']
    tasks = {t.task_id: t for t in load_tasks(prepared/'tasks.jsonl', 'fit')}
    if len(identities) != 256 or set(tasks) != set(identities):
        raise ValueError('first256 exact fit reservation required')
    if set(identities) & set(reservations['tune']): raise ValueError('fit and tune overlap')
    return [tasks[identity] for identity in identities], identities


class _ObservedRetrieval:
    def __init__(self, retrieval): self.retrieval, self.ranking = retrieval, None
    def rank(self, question, candidates):
        self.ranking = self.retrieval.rank(question, candidates)
        return self.ranking


def collect_raw_pairs(tasks, runtime, config):
    """Run two paid actions and seal observable receipts; never assign labels."""
    if any(k in config for k in ('gold', 'answer', 'supporting_facts', 'scoring', 'coverage')):
        raise ValueError('annotation-bearing collection configuration')
    if [t.task_id for t in tasks] != config['assigned_ids'] or len(set(config['assigned_ids'])) != len(tasks):
        raise ValueError('collection assigned membership mismatch')
    root = Path(config['run_dir'])
    if (root/'schedule.json').exists(): raise ValueError('collection already scheduled; preserve original attempts')
    root.mkdir(parents=True, exist_ok=True)
    jobs, schedule = [], []
    for task in tasks:
        for k in (2, 10):
            signature = action_signature(task, runtime.config, task.candidate_ids, f'fit:k={k}', 'none')
            job = {'run_id':root.name, 'task':task, 'policy':FixedPolicy(k),
                   'protocol_hash':'development-unfrozen-task10', 'job_id':job_id(signature,'direct:fit-pair',0),
                   'arm':'fit-pair', 'mode':'direct', 'cache_mode':'none', 'repetition_id':0}
            jobs.append(job)
            schedule.append({'task_id':task.task_id, 'k':k, 'job_id':job['job_id']})
    atomic_json(root/'schedule.json', {'assigned_ids':config['assigned_ids'], 'jobs':schedule,
                                     'runtime_config':runtime.config, 'feature_schema_hash':feature_schema()['hash']})
    assigned = [j['job_id'] for j in jobs]
    if config.get('setup_interval'):
        record_shared_cost(root,'cold_setup',*config['setup_interval'],assigned,source_id='task10-native-runtime-setup')
        lifecycle = getattr(runtime.reader.backend,'lifecycle',[])
        if lifecycle and lifecycle[0]['kind']=='load' and not lifecycle[0].get('owner'):
            if not config['setup_interval'][0] <= lifecycle[0]['start_ns'] <= lifecycle[0]['stop_ns'] <= config['setup_interval'][1]:
                raise ValueError('shared setup must enclose initial reader load')
            runtime._lifecycle_seen = 1
    paths = config.get('offline_attempts_paths', [config['offline_attempts_path']] if config.get('offline_attempts_path') else [])
    if paths:
        seen = set()
        for row in (row for path in paths for row in read_jsonl(Path(path))):
            if row.get('split') not in ('pilot','fit') or row['attempt_id'] in seen: continue
            seen.add(row['attempt_id'])
            start = round(datetime.fromisoformat(row['started_utc']).timestamp()*1e9)
            stop = start+round(row['elapsed_seconds']*1e9)
            source = ('pilot' if row['split']=='pilot' else 'fit')+'-index-attempt:'+row['attempt_id']
            record_shared_cost(root,'offline',start,stop,assigned,source_id=source)
    original = runtime.retrieval
    recording = _ObservedRetrieval(original)
    runtime.retrieval = recording
    predictions, observations = [], []
    try:
        for item, job in zip(schedule, jobs):
            if config.get('deadline_utc') and (datetime.fromisoformat(config['deadline_utc'])-datetime.now(timezone.utc)).total_seconds() <= 3600:
                raise TimeoutError('authoritative deadline reporting reserve exhausted')
            prediction = execute_job(job,runtime,root)
            if prediction.status == 'infra_error': raise ValueError('infrastructure missingness blocks training; attempts preserved')
            capture_start = time.perf_counter_ns()
            ranking = recording.ranking
            values = build_features(job['task'].question, ranking)
            decision = json.loads((root/'jobs'/job['job_id']/f'attempt-{prediction.attempt}'/'decision.json').read_text())
            receipt = {**item, 'ranking':[asdict(d) for d in ranking],
                       'features':dict(zip([f['name'] for f in feature_schema()['features']],map(float,values))),
                       'action_signature':decision['action_signature'], 'runtime_config_hash':content_hash(runtime.config)}
            append_jsonl(root/'observables.jsonl',receipt)
            record_shared_cost(root, 'offline', capture_start, time.perf_counter_ns(), [job['job_id']],
                               source_id='observable-capture:'+job['job_id'])
            predictions.append(prediction)
            print(json.dumps({'stage':'fit-collection','completed':len(predictions),'assigned':len(jobs),'status':prediction.status}),flush=True)
        runtime.synchronize()
        last = {**jobs[-1], '_run_dir':str(root), 'attempt':predictions[-1].attempt}
        _consume_worker_lifecycle(runtime,last,TimingLedger(last,jobs[-1]['policy'].policy_id,runtime.clock))
        closure = close_run(root,jobs)
        for item, p in zip(schedule,predictions):
            observations.append({**item,'status':p.status,'prompt_tokens':p.prompt_tokens,'output_tokens':p.generated_tokens,
                                 **accounting(root,p)})
        result = {'closure':closure,'assigned_tasks':len(tasks),'generation_calls':sum(p.generation_calls for p in predictions),
                  'observations':observations,'determinism':{'checks':[],'passed':None,'reason':'frozen WP3 parity gate; no additional fit parity calls'},
                  'interpretation':'annotation-free raw acquisition; no labels until separate scorer closure'}
        atomic_json(root/'collection_costs.json',result)
        names = ('observables.jsonl','schedule.json','predictions.jsonl','predictions.closed.json')
        atomic_json(root/'collection.closed.json',{'assigned_ids':config['assigned_ids'],
                    'hashes':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}})
        return result
    finally:
        runtime.retrieval = original


def main(args):
    if args.split != 'fit': raise ValueError('collection permits initial fit only')
    config = json.loads(Path(args.config).read_text())
    state = json.loads(Path('artifacts/provenance/experiment-state.json').read_text())
    gate = json.loads(Path(state['evidence']['combined64_gate']).read_text())['gate']
    if not state['wp3_gate']['task10_allowed'] or not gate['task10_allowed']:
        raise ValueError('reviewed WP3 development gate required')
    from .pilot import main as native_main
    return native_main(args)

"""Annotation-free, development-only pilot serving and measured capacity forecast."""

from datetime import datetime, timezone
from dataclasses import replace
import json
import math
from pathlib import Path
import time

from .data_runtime import DocumentStore, load_tasks
from .generation import Reader, ranking_aliases, render_prompt
from .policies import FixedPolicy
from .runner import Runtime, action_signature, job_id, execute_job, close_run, accounting, load_events
from .schemas import Decision, Task
from .storage import atomic_json, content_hash, append_jsonl, read_jsonl


class NoContextDiagnostic:
    policy_id = 'NO-CONTEXT-DIAGNOSTIC'

    def choose(self, question, ranked, paid_draft=None, *, caller_cap=10):
        return Decision(self.policy_id, 0, None, None, None, 'diagnostic', 'no-context', 0, 0)


def load_pilot_inputs(config):
    """Project manifest reservation membership into annotation-free runtime tasks."""
    prepared = Path(config['inputs']['prepared_dir'])
    reservation = json.loads((prepared/'manifest.json').read_text())['reservations']
    mode = config['pilot'].get('reservation_slice', 'active')
    if mode not in ('active', 'extension'):
        raise ValueError('unknown pilot reservation slice')
    active = reservation['active_pilot']
    if mode == 'extension':
        if reservation['pilot'][:len(active)] != active:
            raise ValueError('pilot reservation prefix mismatch')
        identities = reservation['pilot'][len(active):]
        split = 'pilot_reservation'
    else:
        identities, split = active, 'pilot'
    tasks = load_tasks(prepared/'tasks.jsonl', split)
    by_id = {task.task_id: task for task in tasks}
    if set(by_id) != set(identities) or len(identities) != config['pilot']['active_tasks']:
        raise ValueError('pilot count/membership does not match frozen reservation')
    return [replace(by_id[identity], split='pilot') for identity in identities], identities


def job_components(run_dir, prediction):
    """Read every certified job-attempt component, not only paid generation IDs."""
    from .runner import _observed_failure, _owned_reloads
    components = {}
    for attempt in sorted((Path(run_dir)/'jobs'/prediction.job_id).glob('attempt-*')):
        if (attempt/'observed-failure.closed.json').exists():
            _, events = _observed_failure(attempt)
            rows = [event.__dict__ for event in events]
        else:
            rows = list(read_jsonl(attempt/'events.jsonl'))
        rows += [event.__dict__ for event in _owned_reloads(attempt)]
        for event in rows:
            name = event['role']
            components[name] = components.get(name, 0.)+event['elapsed_seconds']
    return components


def capacity_forecast(observations: list[dict], remaining_seconds: float) -> dict:
    if not math.isfinite(remaining_seconds) or remaining_seconds < 0:
        raise ValueError('remaining time must be finite and nonnegative')
    for row in observations:
        for key in ('serving_seconds', 'experiment_seconds'):
            value = row.get(key, 0.)
            if not math.isfinite(value) or value < 0:
                raise ValueError('invalid observed time')
    reserve = 3600.
    if not observations:
        return {'feasible': False, 'reason': 'no_observations', 'reserved_reporting_seconds': reserve}
    times = sorted(max(row.get('serving_seconds', 0.), row.get('experiment_seconds', 0.)) for row in observations)
    # Conservative observed 95th percentile including the full enclosing pipeline;
    # 50% margin covers scheduling, longer outputs and prefill/decode variability.
    per_job = times[min(len(times)-1, math.ceil(.95*len(times))-1)]*1.5
    jobs = max(row.get('planned_jobs', 0) for row in observations)
    seconds = per_job*jobs
    return {'method': 'observed_complete_pipeline_p95_times_1.5',
            'observations': len(observations), 'planned_jobs': jobs,
            'conservative_seconds_per_job': per_job, 'forecast_seconds': seconds,
            'remaining_seconds': remaining_seconds, 'reserved_reporting_seconds': reserve,
            'maximum_affordable_jobs': math.floor(max(0., remaining_seconds-reserve)/per_job) if per_job > 0 else 0,
            'feasible': jobs > 0 and seconds <= max(0., remaining_seconds-reserve),
            'component_means': {name: sum(row.get('components', {}).get(name, 0.) for row in observations)/len(observations)
                                for name in sorted({name for row in observations for name in row.get('components', {})})},
            'scope': 'execution-time forecast from paid development observations; no GPU FLOPS estimate'}


def pilot_schedule(config: dict) -> dict:
    tasks = config['tasks']
    identities = config['assigned_ids']
    by_id = {task.task_id: task for task in tasks}
    if len(by_id) != len(tasks) or len(set(identities)) != len(identities) or set(identities) != set(by_id):
        raise ValueError('pilot membership must exactly match reserved assignments')
    if any(type(task) is not Task or task.split != 'pilot' or len(task.candidate_ids) != 10 for task in tasks):
        raise ValueError('pilot requires active development ten-candidate tasks')
    size = config.get('all_k_size', 4)
    if type(size) is not int or not 0 <= size <= len(tasks):
        raise ValueError('invalid all-k slice size')
    slice_ids = sorted(identities, key=lambda identity: (content_hash([271828, identity, 'pilot-all-k']), identity))[:size]
    jobs = [{'task_id': identity, 'k': k, 'kind': 'primary' if k else 'no_context', 'repetition': 0}
            for position, identity in enumerate(identities)
            for k in ([2, 10, 0] if position % 2 == 0 else [10, 2, 0])]
    jobs += [{'task_id': identity, 'k': k, 'kind': 'all_k', 'repetition': 0}
             for identity in slice_ids for k in range(1, 11) if k not in (2, 10)]
    if config.get('determinism', True):
        jobs += [{'task_id': identities[0], 'k': k, 'kind': 'determinism', 'repetition': 1} for k in (2, 10)]
    return {'assigned_ids': identities, 'all_k_ids': slice_ids, 'all_k_size': size,
            'hash_rule': "SHA256(canonical([271828, task_id, 'pilot-all-k'])) ascending",
            'slice_basis': 'four of 32 reserved pilot tasks: 32 incremental all-k calls; bounded development diagnostic',
            'paired_order': 'alternate small/full by reservation position', 'jobs': jobs}


def run_pilot(config: dict, runtime: object) -> dict:
    if any(key in config for key in ('gold', 'answer', 'supporting_facts', 'scoring', 'coverage')):
        raise ValueError('annotation-bearing pilot configuration rejected')
    schedule = pilot_schedule(config)
    root = Path(config['run_dir'])
    if (root/'schedule.json').exists():
        raise ValueError('pilot run directory already scheduled; do not overwrite attempts')
    root.mkdir(parents=True, exist_ok=True)
    tasks = {task.task_id: task for task in config['tasks']}
    # Freeze selection before even warm-up outcomes. Token strata are structural,
    # measured with the exact installed renderer/tokenizer and full CPU ranking.
    atomic_json(root/'schedule.json', schedule)
    preparation_start = time.perf_counter_ns()
    lengths = []
    feature_durations = []
    if config.get('warmups', True):
        for task in config['tasks']:
            ranking = runtime.retrieval.rank(task.question, task.candidate_ids)
            from .features import build_features
            feature_start = time.perf_counter_ns()
            build_features(task.question, ranking)
            feature_durations.append((time.perf_counter_ns()-feature_start)/1e9)
            aliases = ranking_aliases(ranking)
            for k in range(11):
                prompt = render_prompt(task.question, [runtime.documents.get(row.doc_id) for row in ranking[:k]],
                                       aliases, runtime.reader.backend.tokenizer)
                lengths.append({'task_id': task.task_id, 'k': k,
                                'prompt_tokens': len(runtime.reader.backend.tokenizer.encode(prompt))})
        warmups = []
        for k in range(11):
            shape = sorted([row for row in lengths if row['k'] == k], key=lambda row: (row['prompt_tokens'], row['task_id']))
            for stratum, index in [('short', 0), ('median', len(shape)//2), ('long', len(shape)-1)]:
                warmups.append({**shape[index], 'kind': 'warmup:'+stratum, 'repetition': 2+index})
        schedule['jobs'] = warmups+schedule['jobs']
        schedule['token_lengths'] = lengths
        atomic_json(root/'schedule.json', schedule)
    preparation_stop = time.perf_counter_ns()
    jobs = []
    for item in schedule['jobs']:
        task, k = tasks[item['task_id']], item['k']
        policy = FixedPolicy(k) if k else NoContextDiagnostic()
        signature = action_signature(task, runtime.config, task.candidate_ids, f'pilot:k={k}', 'none')
        job = {'run_id': root.name, 'task': task, 'policy': policy, 'protocol_hash': 'development-unfrozen-task9',
               'job_id': job_id(signature, 'direct:'+item['kind'], item['repetition']),
               'arm': item['kind'], 'mode': 'direct', 'cache_mode': 'none',
               'repetition_id': item['repetition'], 'allow_no_context_diagnostic': k == 0}
        jobs.append(job)
        item['job_id'] = job['job_id']
    atomic_json(root/'schedule.json', schedule)
    from .runner import record_shared_cost
    assigned = [job['job_id'] for job in jobs]
    record_shared_cost(root, 'cold_setup', preparation_start, preparation_stop, assigned,
                       source_id='task9-structural-shape-preparation')
    if config.get('offline_attempts_path'):
        prior = []
        for row in read_jsonl(Path(config['offline_attempts_path'])):
            if row.get('split') != 'pilot':
                continue
            duration = row['elapsed_seconds']
            if not math.isfinite(duration) or duration < 0:
                raise ValueError('invalid historical index duration')
            start = round(datetime.fromisoformat(row['started_utc']).timestamp()*1e9)
            stop = start+round(duration*1e9)
            source = 'pilot-index-attempt:'+row['attempt_id']
            record_shared_cost(root, 'offline', start, stop, assigned, source_id=source)
            prior.append({'source_id': source, 'status': row['status'], 'elapsed_seconds': duration,
                          'start_ns': start, 'stop_ns': stop,
                          'clock_kind': 'historical UTC anchor plus observed monotonic elapsed duration; not serving clock'})
        atomic_json(root/'prior-offline-costs.json', {'records': prior, 'total_seconds': sum(row['elapsed_seconds'] for row in prior),
                                                    'scope': 'persisted pilot indexing attempts; project source identities count once'})
    if config.get('setup_interval'):
        record_shared_cost(root, 'cold_setup', *config['setup_interval'], assigned, source_id='task9-native-runtime-setup')
        lifecycle = getattr(runtime.reader.backend, 'lifecycle', [])
        if lifecycle and lifecycle[0]['kind'] == 'load' and not lifecycle[0].get('owner'):
            if not config['setup_interval'][0] <= lifecycle[0]['start_ns'] <= lifecycle[0]['stop_ns'] <= config['setup_interval'][1]:
                raise ValueError('shared setup must enclose initial reader load')
            runtime._lifecycle_seen = 1
    predictions, observations, identities, resources = [], [], {}, {}
    for item, job in zip(schedule['jobs'], jobs):
        if config.get('deadline_utc'):
            deadline = datetime.fromisoformat(config['deadline_utc'])
            if (deadline-datetime.now(timezone.utc)).total_seconds() <= 3600:
                raise TimeoutError('authoritative execution deadline requires reporting/recovery reserve')
        prediction = execute_job(job, runtime, root)
        predictions.append(prediction)
        result = runtime.last_paid_result
        token_hash = content_hash(result.generated_token_ids) if result else None
        identities[job['job_id']] = {'output_hash': content_hash(prediction.raw_output), 'token_hash': token_hash}
        counters = dict(getattr(runtime.reader.backend, 'last_resources', {}))
        if not counters:
            counters = {'backend_prompt_tokens_per_second': None, 'backend_generation_tokens_per_second': None,
                        'reason': 'backend_resource_telemetry_unavailable'}
        resources[job['job_id']] = counters
        append_jsonl(root/'resources.jsonl', {'job_id': job['job_id'], 'task_id': prediction.task_id,
                                             'status': prediction.status, **counters})
        print(json.dumps({'stage': 'pilot-serving', 'completed': len(predictions), 'assigned': len(jobs),
                          'kind': item['kind'], 'k': item['k'], 'status': prediction.status}), flush=True)
    # The final paid failure can leave recovery pending; settle under its origin
    # ownership before attempting closure, without another answer generation.
    runtime.synchronize()
    from .runner import _consume_worker_lifecycle
    from .timing import TimingLedger
    last = {**jobs[-1], '_run_dir': str(root), 'attempt': predictions[-1].attempt}
    _consume_worker_lifecycle(runtime, last, TimingLedger(last, jobs[-1]['policy'].policy_id, runtime.clock))
    closure = close_run(root, jobs)
    for item, prediction in zip(schedule['jobs'], predictions):
        costs = accounting(root, prediction)
        components = job_components(root, prediction)
        observations.append({**{key: value for key, value in item.items() if key != 'question'},
                             'status': prediction.status, 'prompt_tokens': prediction.prompt_tokens,
                             'output_tokens': prediction.generated_tokens, 'generation_calls': prediction.generation_calls,
                             'serving_seconds': costs['total_serving_seconds'],
                             'experiment_seconds': costs['total_experiment_seconds'], 'components': components,
                             **identities[prediction.job_id], 'resources': resources[prediction.job_id]})
    parity = []
    for k in (2, 10):
        relevant = [row for row in observations if row['task_id'] == schedule['assigned_ids'][0] and row['k'] == k
                    and row['kind'] in ('primary', 'determinism')]
        if len(relevant) == 2:
            parity.append({'k': k, 'output_match': relevant[0]['output_hash'] == relevant[1]['output_hash'],
                           'token_match': relevant[0]['token_hash'] == relevant[1]['token_hash']})
    result = {'closure': closure, 'assigned_tasks': len(tasks), 'scheduled_calls': len(jobs),
              'generation_calls': sum(p.generation_calls for p in predictions), 'observations': observations,
              'determinism': {'checks': parity, 'passed': bool(parity) and all(r['output_match'] and r['token_match'] for r in parity)},
              'interpretation': 'serving closed; no outcome scoring performed'}
    result['feature_overhead_seconds_per_task'] = max(feature_durations) if feature_durations else None
    atomic_json(root/'pilot_costs.json', result)
    return result


def main(args) -> int:
    from .assets import verify_configured_assets
    from .environment import discover, resource_gate
    from .generation import NativeReaderFactory, SupervisedBackend, offline_network
    from .retrieval import EncoderBackend, Retrieval
    import psutil
    import subprocess
    import sys
    import threading
    main_start = time.perf_counter_ns()
    config = json.loads(Path(args.config).read_text())
    window = json.loads(Path('artifacts/provenance/execution-window.json').read_text())
    if (datetime.fromisoformat(window['deadline_utc'])-datetime.now(timezone.utc)).total_seconds() <= 3600:
        raise TimeoutError('project execution deadline reserve exhausted')
    root = Path(config['pilot']['run_dir'])
    root.mkdir(parents=True, exist_ok=True)
    # Fresh subprocess proves OS isolation independently of the Python guard.
    probe = "import errno,json,socket,sys\nr={}\nfor i,p in enumerate(sys.argv[1:]):\n try: open(p,'rb').read(1)\n except PermissionError: r[str(i)]=True\n else: r[str(i)]=False\ns=socket.socket();s.settimeout(.1)\ntry: s.connect(('1.1.1.1',443))\nexcept OSError as e: r['network']=e.errno in (errno.EPERM,errno.EACCES)\nelse: r['network']=False\nprint(json.dumps(r))"
    denied = [Path(config['inputs']['prepared_dir'])/'gold/gold.jsonl',
              Path('models/pinned/data/hotpot_train_v1.1.json'), Path('models/pinned/data/hotpot_dev_distractor_v1.json')]
    denials = json.loads(subprocess.run([sys.executable, '-c', probe, *map(str, denied)], capture_output=True, text=True, check=True).stdout)
    if not all(denials.values()):
        raise ValueError('pilot requires OS network, raw data and gold denial')
    atomic_json(root/'os-denials.json', denials)
    environment = discover(root/'environment')
    if not environment['native_supported'] or not environment['resource_gate']['passed']:
        raise ValueError('native pilot prerequisites failed')
    manifest = json.loads(Path(config['inputs']['asset_manifest']).read_text())
    verify_configured_assets({role: config[role] for role in ('reader', 'encoder', 'original_reader')},
                             {'required': ['reader', 'encoder', 'original_reader'], 'assets': manifest['assets']})
    asset = manifest['assets']['reader']
    stop, backend, rss_peak = threading.Event(), None, [psutil.Process().memory_info().rss]
    def monitor():
        while not stop.wait(.02):
            rss = psutil.Process().memory_info().rss
            if backend and backend.worker_pid:
                try: rss += psutil.Process(backend.worker_pid).memory_info().rss
                except psutil.Error: pass
            rss_peak[0] = max(rss_peak[0], rss)
    observer = threading.Thread(target=monitor, daemon=True)
    observer.start()
    try:
        with offline_network() as attempts:
            start = main_start
            prepared = Path(config['inputs']['prepared_dir'])
            tasks, reservation = load_pilot_inputs(config)
            documents = DocumentStore(prepared/'documents.jsonl')
            encoder = EncoderBackend(Path(manifest['assets']['encoder']['local_path']))
            retrieval = Retrieval(Path(config['inputs']['index_dir']), documents, encoder)
            with SupervisedBackend(NativeReaderFactory(Path(asset['local_path']), {**config['reader'], 'asset': asset})) as backend:
                settings = {'model_revision': asset['revision'], 'model_hash': asset['snapshot_hash'],
                            'decoding_hash': content_hash({**config['reader'], 'temperature': 0, 'cache_mode': 'none',
                                                           'draft_model': None, 'max_kv_size': None, 'kv_bits': None}),
                            **{name: config['reader'][name] for name in ('max_context_tokens', 'max_new_tokens', 'timeout_seconds')},
                            'backend': 'persistent-supervised-native-mlx', 'prompt_version': 1,
                            'index_manifest_hash': content_hash(retrieval.manifest)}
                runtime = Runtime(retrieval, documents, Reader(backend), settings)
                result = run_pilot({**config['pilot'], 'tasks': tasks, 'assigned_ids': reservation,
                                    'deadline_utc': window['deadline_utc'],
                                    'offline_attempts_path': config['inputs'].get('offline_attempts_path', 'artifacts/provenance/index-attempts.jsonl'),
                                    'setup_interval': [start, time.perf_counter_ns()]}, runtime)
                result['peak_mlx_bytes'] = backend.peak_mlx_bytes
                result['worker_lifecycle'] = backend.lifecycle
                result['network_attempt_count'] = len(attempts)
    finally:
        stop.set(); observer.join()
    result['sampled_parent_worker_rss_bytes'] = rss_peak[0]
    result['physical_memory_bytes'] = environment['physical_memory_bytes']
    result['resource_gate'] = resource_gate(environment['physical_memory_bytes'], rss_peak[0]+result['peak_mlx_bytes'])
    result['resource_bound_kind'] = 'conservative RSS plus MLX overlap bound; not exact working set'
    result['swap_used_bytes'] = psutil.swap_memory().used
    result['measured_utc'] = datetime.now(timezone.utc).isoformat()
    result['os_denials'] = denials
    atomic_json(root/'pilot_costs.json', result)
    print(json.dumps({'closed': True, 'assigned_tasks': result['assigned_tasks'],
                      'generation_calls': result['generation_calls'], 'resource_gate': result['resource_gate'],
                      'determinism': result['determinism'], 'run_dir': str(root)}), flush=True)
    return 0 if result['resource_gate']['passed'] and not attempts else 1

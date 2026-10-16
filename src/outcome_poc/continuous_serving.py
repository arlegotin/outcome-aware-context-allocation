"""Versioned complete request interval over the existing durable allocation runner.

Inner events are diagnostic. A response is usable only after payload/completion,
a separate durable receipt, and its observed continuous boundary all exist.
No interrupted receipt is adopted and no active-clock sum replaces this interval.
"""
from pathlib import Path

from .followup.clock import continuous_ns,boot_identity,clock_identity
from .storage import atomic_json,content_hash,canonical_bytes
from .followup.study import read,identity

VERSION='complete-continuous-v3'


def settings(config):
    if config.get('request_timing')!=VERSION:
        return {}
    observed={'boot_id':boot_identity(),'clock':clock_identity()}
    expected=config.get('request_clock',observed)
    if expected!=observed:raise ValueError('continuous request boot/clock domain mismatch')
    return {'request_timing':VERSION,'request_clock':observed}


def make_runtime(retrieval,documents,reader,config):
    from .runner import Runtime
    selected=settings(config)
    return Runtime(retrieval,documents,reader,{**config,**selected},
                   **({'clock':continuous_ns} if selected else {}))


def backend_type(config):
    if config.get('request_timing')==VERSION:
        from .followup.supervisor import ContinuousBackend
        return ContinuousBackend
    from .generation import SupervisedBackend
    return SupervisedBackend


def _domain(runtime):
    observed={'boot_id':boot_identity(),'clock':clock_identity()}
    if runtime.config.get('request_clock')!=observed:
        raise ValueError('continuous request boot/clock domain mismatch')
    if runtime.clock is not continuous_ns or getattr(runtime.reader.backend,'clock',None) is not continuous_ns:
        raise ValueError('runtime/supervisor continuous clock domains disagree')
    return observed


def _publish(path,value):
    path=Path(path)
    if path.exists():
        if path.read_bytes()!=canonical_bytes(value):raise ValueError('immutable continuous request record changed')
    else:atomic_json(path,value)


def execute(job,runtime,root,executor):
    start=runtime.clock()  # Before domain/assignment validation and initial sync.
    domain=_domain(runtime)
    if job.get('mode','direct')!='direct' or job.get('cache_mode','none')!='none' or 'replay_prediction' in job:
        raise ValueError('continuous scientific accounting requires fresh direct requests; development replay stays diagnostic')
    root=Path(root)
    name=job.get('job_id')
    if type(name) is not str or not name or Path(name).name!=name or name in ('.','..'):
        raise ValueError('continuous job identity is not a safe component')
    marker={'version':VERSION,**domain}
    _publish(root/'request-timing.json',marker)
    directory=root/'jobs'/name
    requests=root/'continuous-requests'/name
    previous=sorted(requests.glob('attempt-*'),key=lambda p:int(p.name.split('-')[-1]))
    if previous:
        last=previous[-1]
        if not (last/'boundary.json').is_file():
            raise ValueError('incomplete/unobserved continuous request cannot be adopted or rerun')
        record=read(last/'receipt.json')
        if not job.get('retry_infrastructure',False):
            result=executor(job,runtime,root)
            totals(root,result)
            if result.attempt!=record['attempt']:raise ValueError('continuous resume attempt changed')
            return result
    attempt=len(list(directory.glob('attempt-*')))+1
    destination=requests/f'attempt-{attempt}'
    destination.mkdir(parents=True,exist_ok=False)
    config={**runtime.config}
    state={'version':VERSION,**domain,'start_ns':start,'attempt':attempt,
           'job_id':name,'task_id':job['task'].task_id,'policy_id':job['policy'].policy_id,
           'config':config,'config_hash':content_hash(config)}
    _publish(destination/'started.json',state)
    try:
        result=executor(job,runtime,root)
        if getattr(runtime,'unknown_cleanup',None):
            raise RuntimeError('continuous request worker cleanup unknown: '+runtime.unknown_cleanup)
        _domain(runtime)
        core=directory/f'attempt-{result.attempt}'
        if result.attempt!=attempt:raise ValueError('continuous assigned attempt mismatch')
        completion=read(directory/'completion.json')
        receipt={'version':VERSION,'attempt':attempt,'job_id':name,'task_id':result.task_id,
                 'start':identity(destination/'started.json'),'completion_at_response':completion,
                 'prediction':identity(core/'prediction.json'),'ready':identity(core/'ready.json'),
                 'job_identity':identity(directory/'identity.json'),'status':result.status}
        _publish(destination/'receipt.json',receipt)
        _domain(runtime)
        stop=runtime.clock()  # Durable response AND receipt precede this observation.
        if stop<=start:raise ValueError('continuous request clock reversed or nonpositive interval')
        _publish(destination/'boundary.json',{'version':VERSION,**domain,'start_ns':start,'stop_ns':stop,
                 'seconds':(stop-start)/1e9,'receipt':identity(destination/'receipt.json')})
        return result
    except BaseException as error:
        # The lower bound is retained even when closure/cleanup cannot be known.
        _publish(destination/'failure.json',{'error':f'{type(error).__name__}: {error}',
                 'stop_lower_bound_ns':runtime.clock(),'exact_interval_available':False})
        raise


def totals(root,prediction):
    root=Path(root);marker=read(root/'request-timing.json')
    if marker['version']!=VERSION:raise ValueError('unknown continuous accounting version')
    directory=root/'jobs'/prediction.job_id
    attempts=sorted(directory.glob('attempt-*'),key=lambda p:int(p.name.split('-')[-1]))
    requests=root/'continuous-requests'/prediction.job_id
    if {p.name for p in requests.iterdir()}!={p.name for p in attempts}:
        raise ValueError('incomplete continuous attempt assignment')
    total=0.;previous_stop=None
    for core in attempts:
        observed=requests/core.name
        if not (observed/'boundary.json').is_file():raise ValueError('incomplete continuous request receipt')
        if (observed/'failure.json').exists():raise ValueError('failed continuous request interval uncertified')
        start=read(observed/'started.json');receipt=read(observed/'receipt.json');boundary=read(observed/'boundary.json')
        if (boundary['version']!=VERSION or start['version']!=VERSION or
                any(start[k]!=marker[k] or boundary[k]!=marker[k] for k in ('boot_id','clock')) or
                start['config'].get('request_timing')!=VERSION or start['config_hash']!=content_hash(start['config']) or
                start['config'].get('request_clock')!={k:marker[k] for k in ('boot_id','clock')} or
                boundary['start_ns']!=start['start_ns'] or boundary['stop_ns']<=boundary['start_ns'] or
                boundary['seconds']!=(boundary['stop_ns']-boundary['start_ns'])/1e9 or
                (previous_stop is not None and start['start_ns']<previous_stop)):
            raise ValueError('continuous request clock/bounds/config mismatch')
        if (boundary['receipt']!=identity(observed/'receipt.json') or receipt['start']!=identity(observed/'started.json') or
                receipt['prediction']!=identity(core/'prediction.json') or receipt['ready']!=identity(core/'ready.json') or
                receipt['job_identity']!=identity(directory/'identity.json') or
                receipt['job_id']!=prediction.job_id or receipt['task_id']!=prediction.task_id or
                receipt['attempt']!=int(core.name.split('-')[-1])):
            raise ValueError('continuous durable receipt identity mismatch')
        expected=receipt['completion_at_response']
        if (expected['prediction_path']!=str((core/'prediction.json').relative_to(directory)) or
                expected['prediction_sha256']!=receipt['prediction']['sha256'] or
                expected['events_sha256']!=identity(core/'events.jsonl')['sha256']):
            raise ValueError('continuous response does not bind core completion')
        if receipt['attempt']==prediction.attempt and expected!=read(directory/'completion.json'):
            raise ValueError('continuous final completion mismatch')
        total+=boundary['seconds'];previous_stop=boundary['stop_ns']
    return total



def outside_request_cost(root,prediction):
    """Union of diagnostic setup/cleanup intervals outside enclosing requests."""
    from .runner import _owned_reloads,_observed_failure
    from .schemas import CostEvent
    from .storage import read_jsonl
    root=Path(root)
    windows=[(read(p)['start_ns'],read(p)['stop_ns']) for p in
             (root/'continuous-requests'/prediction.job_id).glob('attempt-*/boundary.json')]
    pieces=[]
    events=[]
    for attempt in (root/'jobs'/prediction.job_id).glob('attempt-*'):
        if (attempt/'observed-failure.closed.json').exists():
            _,observed=_observed_failure(attempt);events.extend(observed)
        else:events.extend(CostEvent(**row) for row in read_jsonl(attempt/'events.jsonl'))
        events.extend(_owned_reloads(attempt))
    for event in events:
        if event.task_id!=prediction.task_id or event.policy_id!=prediction.policy_id:
            continue
        if event.role not in {'telemetry','setup','warmup','offline','worker_reload'}:
            continue
        remains=[(event.start_ns,event.stop_ns)]
        for start,stop in windows:
            remains=[part for a,b in remains for part in ((a,min(b,start)),(max(a,stop),b)) if part[1]>part[0]]
        pieces.extend(remains)
    merged=[]
    for start,stop in sorted(pieces):
        if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(stop,merged[-1][1]))
        else:merged.append((start,stop))
    return sum((b-a)/1e9 for a,b in merged)

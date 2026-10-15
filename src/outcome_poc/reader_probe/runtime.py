"""Native isolation and durable lifecycle for exactly three authored reader calls."""
from dataclasses import asdict, dataclass
import importlib
import importlib.abc
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from ..storage import append_jsonl, atomic_json, content_hash, read_jsonl
from ..followup.study import read, identity, publish
from ..followup.clock import continuous_ns, boot_identity
from ..followup.supervisor import ContinuousBackend, CleanupFailure
from ..followup.runtime import (ResourceMonitor, resource_check, stage_lock,
    probe_denials, verify_import_origins, reconcile_sessions, session_accounting,
    _worker_identity_unknown)
from ..generation import parse_answer
from ..schemas import Document, GenerationRequest, validate_record
from .profile import ProfileFactory
from .study import verify, build_prompt, DENIED_MODULES, inventory

STAGE = 'preflight'


class ImportGuard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name+'.') for name in DENIED_MODULES):
            raise ImportError('reader preflight annotation import denied')
        return None


def isolation(root, plan):
    verify_import_origins(root)
    if any(any(name == denied or name.startswith(denied+'.') for denied in DENIED_MODULES)
           for name in sys.modules):
        raise RuntimeError('annotation-enabled module already imported')
    guard = ImportGuard()
    sys.meta_path.insert(0, guard)
    for name in DENIED_MODULES:
        try:
            importlib.import_module(name)
        except ImportError as error:
            if 'reader preflight annotation import denied' in str(error):
                continue
            # Future namespaces need not exist yet; exercise the exact guard.
            try:
                guard.find_spec(name)
            except ImportError:
                continue
        raise RuntimeError('import denial probe failed')
    if plan['freeze']['boot_id'] != boot_identity():
        raise ValueError('plan boot mismatch')
    return {**probe_denials(plan['freeze']['denied_probes']),
            'import_denials': list(DENIED_MODULES), 'snapshot_origins': True}


@dataclass(frozen=True)
class IsolatedReaderFactory:
    factory: object
    root: Path
    plan_hash: str
    session_start: Path

    def __call__(self):
        # Identity is durable even if subsequent isolation/startup checks fail.
        import psutil
        state = read(self.session_start)
        publish(self.session_start.parent/f"session-worker-{state['session']}-{os.getpid()}.json",
            {'session': state['session'], 'plan_hash': self.plan_hash, 'boot_id': boot_identity(),
             'pid': os.getpid(), 'created': psutil.Process().create_time(), 'continuous_ns': continuous_ns()})
        plan = verify(self.root)
        if plan['plan_hash'] != self.plan_hash or state['plan_hash'] != self.plan_hash:
            raise ValueError('worker plan mismatch')
        probes = isolation(self.root, plan)
        publish(self.session_start.parent/f"worker-probes-{state['session']}.json", probes)
        if os.getppid() != state['parent_pid'] or psutil.Process(os.getppid()).create_time() != state['parent_created']:
            raise RuntimeError('reader coordinator identity changed before acquisition')
        settings = {**plan['freeze']['settings']['reader'], 'asset': read(self.root/'assets.json')['assets']['reader']}
        if isinstance(self.factory, ProfileFactory) and (self.factory.config != settings or
                self.factory.snapshot.resolve() != Path(settings['asset']['local_path']).resolve()):
            raise ValueError('worker profile identity mismatch')
        return self.factory()


class AvailabilityMonitor(ResourceMonitor):
    """Keep unchanged RSS/MLX observations; availability is a separate diagnostic."""
    def sample(self):
        values = super().sample()
        available = None
        try:
            import psutil
            available = psutil.virtual_memory().available
        except Exception:
            pass
        append_jsonl(self.path.with_suffix('.availability.jsonl'),
            {'continuous_ns': values['continuous_ns'], 'active_ns': values['active_ns'],
             'system_available_bytes': available})
        return values


class ResourceBlocked(RuntimeError):
    pass


def gate(monitor, directory, boundary, *, acquired=False):
    values = monitor.sample()
    decision = resource_check(values)
    missing = acquired and (values.get('peak_mlx_bytes') is None or
                            getattr(monitor.backend, 'last_resources', {}).get('rss_bytes') is None or
                            getattr(monitor.backend, 'last_resources', {}).get('peak_mlx_bytes') is None)
    if missing:
        decision = {**decision, 'passed': False, 'reason': 'mandatory post-acquisition RSS/MLX counters unavailable'}
    append_jsonl(directory/'gates.jsonl', {'boundary': boundary, 'values': values, **decision})
    if not decision['passed']:
        raise ResourceBlocked(f'resource gate blocked: {boundary}: {decision.get("reason", "headroom")}')


def execute_call(root, plan, call, binding, backend, session):
    directory = root/'jobs'/call['call_id']
    directory.mkdir(parents=True, exist_ok=True)
    settings = plan['freeze']['settings']['reader']
    asset = read(root/'assets.json')['assets']['reader']
    request = GenerationRequest(asset['revision'], asset['snapshot_hash'], binding['prompt_hash'],
        call['decoding_hash'], call['role'], settings['max_context_tokens'], settings['max_new_tokens'],
        settings['timeout_seconds'], settings['cache_mode'])
    durable = {**binding, 'call': call, 'settings': settings, 'request': asdict(request), 'plan_hash': plan['plan_hash']}
    publish(directory/'request.json', durable)
    backend.job_owner = call['call_id']
    backend.synchronize()
    started = {'session': session, 'call_id': call['call_id'], 'plan_hash': plan['plan_hash'],
               'request_identity': identity(directory/'request.json'),
               'start_ns': continuous_ns(), 'active_start_ns': time.perf_counter_ns()}
    publish(directory/'started.json', started)
    def progress(text, prompt_ids, tokens):
        append_jsonl(directory/'progress.jsonl', {'continuous_ns': continuous_ns(),
            'active_ns': time.perf_counter_ns(), 'raw_output': text,
            'prompt_token_ids': list(prompt_ids), 'generated_token_ids': list(tokens)})
    backend.progress_callback = progress
    cleanup = None
    try:
        result = backend.generate(binding['prompt'], request, rendered=True)
    except CleanupFailure as error:
        result = error.result
        cleanup = str(error)
    validate_record(result)
    publish(directory/'result.json', asdict(result))
    parsed = parse_answer(result.raw_output, [Document(**binding['document'])], binding['aliases'],
                          truncated=result.status == 'budget_exhausted' or result.generated_tokens >= 256)
    valid = (result.status == parsed.status == 'ok' and
        ' '.join((parsed.answer or '').split()).casefold() == 'lark-27' and
        parsed.citations == [('authored-reader-probe', 0)] and
        result.prompt_token_ids == binding['prompt_token_ids'] and
        result.prompt_tokens == len(result.prompt_token_ids) and
        result.generated_tokens == len(result.generated_token_ids) and not cleanup)
    publish(directory/'receipt.json', {'call_id': call['call_id'], 'session': session,
        'plan_hash': plan['plan_hash'], 'request_identity': identity(directory/'request.json'),
        'started_identity': identity(directory/'started.json'), 'result_identity': identity(directory/'result.json'),
        'start_ns': started['start_ns'], 'stop_ns': continuous_ns(),
        'active_start_ns': started['active_start_ns'], 'active_stop_ns': time.perf_counter_ns(),
        'valid': valid, 'parsed': asdict(parsed), 'cleanup_error': cleanup})
    if not valid:
        raise RuntimeError(f'authored call failed: {call["shape"]}: {result.status}/{parsed.status}')


def _validate_calls(root, plan):
    receipts = []
    requests = []
    results = []
    for call in plan['calls']:
        directory = root/'jobs'/call['call_id']
        receipt = read(directory/'receipt.json')
        for filename, key in [('request.json','request_identity'), ('started.json','started_identity'), ('result.json','result_identity')]:
            if identity(directory/filename) != receipt[key]:
                raise ValueError('call receipt identity mismatch')
        request = read(directory/'request.json')
        if request['call'] != call or request['plan_hash'] != plan['plan_hash'] or not receipt['valid']:
            raise ValueError('call binding or validity mismatch')
        requests.append(request)
        results.append(read(directory/'result.json'))
        receipts.append(identity(directory/'receipt.json'))
    if any(requests[0][key] != requests[1][key] for key in ('prompt','prompt_token_ids','rendered_identity','request')):
        raise ValueError('repeated prompt identity differs')
    if (results[0]['generated_token_ids'] != results[1]['generated_token_ids'] or
            read(root/'jobs'/plan['calls'][0]['call_id']/'receipt.json')['parsed'] !=
            read(root/'jobs'/plan['calls'][1]['call_id']/'receipt.json')['parsed']):
        raise ValueError('repeated output differs')
    if not 7800 <= len(requests[2]['prompt_token_ids']) <= 7936:
        raise ValueError('long prompt coverage missing')
    return receipts


def _outputs(root):
    return {f'{directory}/{name}': value for directory in ('jobs','stages','launches')
            for name, value in inventory(root/directory).items()}


def validate_closed(root, plan):
    closed = read(root/'closed.json')
    if closed.get('closure_hash') != content_hash({k:v for k,v in closed.items() if k != 'closure_hash'}):
        raise ValueError('closure hash mismatch')
    if closed['status'] != 'passed' or closed['plan_hash'] != plan['plan_hash'] or closed['outputs'] != _outputs(root):
        raise ValueError('closed output inventory changed')
    if closed['calls'] != _validate_calls(root, plan):
        raise ValueError('closed call receipts changed')
    accounting = session_accounting(root, STAGE, plan, require_closed=True)
    if accounting['upper_seconds'] is None:
        raise ValueError('closure requires known quiescence')
    if closed['execution_kind'] == 'native':
        directory = root/'stages'/STAGE
        if not list(directory.glob('worker-probes-*.json')) or not list(directory.glob('coordinator-probes-*.json')):
            raise ValueError('native closure missing isolation receipts')
    return closed


def run(root: Path, *, backend_factory=None) -> dict:
    root = Path(root).resolve()
    with stage_lock(root):
        plan = verify(root)
        if (root/'closed.json').exists():
            return read(root/'closed.json')
        if plan['freeze']['boot_id'] != boot_identity():
            raise ValueError('cross-boot resumption forbidden')
        directory = root/'stages'/STAGE
        directory.mkdir(parents=True, exist_ok=True)
        for path in directory.glob('session-start-*.json'):
            state = read(path)
            if (directory/f"acquisition-{state['session']}.json").exists():
                if _worker_identity_unknown(directory, state, plan,
                        require_identity=state.get('native_execution', False)):
                    raise RuntimeError('owned worker quiescence unknown; resume forbidden')
        reconcile_sessions(root, STAGE, plan)
        # Recovery may bound prior work, but can never authorize another paid call.
        if list((root/'jobs').glob('*/started.json')):
            raise RuntimeError('paid attempt exists: root permanently non-admissible')
        session = uuid.uuid4().hex
        start = continuous_ns()
        active = time.perf_counter_ns()
        import psutil
        state = {'session': session, 'plan_hash': plan['plan_hash'], 'boot_id': boot_identity(),
                 'start_ns': start, 'active_start_ns': active, 'parent_pid': os.getpid(),
                 'parent_created': psutil.Process().create_time(), 'reader_worker_expected': False,
                 'native_execution': backend_factory is None}
        start_path = directory/f'session-start-{session}.json'
        publish(start_path, state)
        monitor = AvailabilityMonitor(directory/f'resources-{session}.jsonl')
        backend = None
        error = cleanup_error = None
        acquired = False
        status = 'blocked'
        try:
            if backend_factory is None:
                if os.environ.get('OUTCOME_READER_PROBE_SERVING') != str(root):
                    raise RuntimeError('native run requires sealed sandbox launch')
                publish(directory/f'coordinator-probes-{session}.json', isolation(root, plan))
            monitor.start()
            gate(monitor, directory, 'before_acquisition')
            asset = read(root/'assets.json')['assets']['reader']
            factory = IsolatedReaderFactory(ProfileFactory(Path(asset['local_path']),
                {**plan['freeze']['settings']['reader'], 'asset': asset}), root, plan['plan_hash'], start_path)
            publish(directory/f'acquisition-{session}.json', {'continuous_ns': continuous_ns(), 'active_ns': time.perf_counter_ns()})
            constructor = backend_factory or ContinuousBackend
            # Assignment precedes __init__: partial constructor ownership survives.
            if isinstance(constructor, type):
                backend = constructor.__new__(constructor)
                constructor.__init__(backend, factory)
            else:
                backend = constructor(factory)
            acquired = True
            monitor.backend = backend
            append_jsonl(directory/'setup.jsonl', {'session': session, 'kind': 'cold_start',
                'start_ns': read(directory/f'acquisition-{session}.json')['continuous_ns'],
                'stop_ns': continuous_ns(), 'active_stop_ns': time.perf_counter_ns()})
            gate(monitor, directory, 'after_acquisition', acquired=True)
            bindings = {shape: build_prompt(backend.tokenizer, shape) for shape in ('short','long')}
            for call in plan['calls']:
                try:
                    execute_call(root, plan, call, bindings[call['shape']], backend, session)
                finally:
                    gate(monitor, directory, 'after_'+call['call_id'], acquired=True)
            _validate_calls(root, plan)
            status = 'passed'
        except BaseException as caught:
            error = f'{type(caught).__name__}: {caught}'
            status = 'blocked' if isinstance(caught, ResourceBlocked) or not acquired else 'incomplete' if isinstance(caught, KeyboardInterrupt) else 'failed'
        finally:
            if backend is not None:
                try:
                    backend.close()
                except BaseException as caught:
                    cleanup_error = f'{type(caught).__name__}: {caught}'
                for row in getattr(backend, 'lifecycle', []):
                    append_jsonl(directory/'lifecycle.jsonl', {'session': session, **row})
            if (directory/f'acquisition-{session}.json').exists():
                try:
                    if _worker_identity_unknown(directory, state, plan, require_identity=backend_factory is None):
                        raise RuntimeError('owned worker identity unknown')
                except BaseException as caught:
                    cleanup_error = cleanup_error or f'{type(caught).__name__}: {caught}'
            try:
                monitor.stop()
            except BaseException as caught:
                error = error or f'resource monitor failure: {caught}'
            if cleanup_error or error:
                status = status if status != 'passed' else 'failed'
            stop = continuous_ns()
            publish(directory/f'session-accounting-{session}.json', {
                'session': session, 'plan_hash': plan['plan_hash'], 'boot_id': state['boot_id'],
                'start_identity': identity(start_path), 'start_ns': start,
                'stop_ns': stop if cleanup_error is None else None,
                'stop_lower_bound_ns': stop, 'stop_upper_bound_ns': stop if cleanup_error is None else None,
                'active_start_ns': active, 'active_stop_ns': time.perf_counter_ns(),
                'timing_status': 'exact' if cleanup_error is None else 'interrupted_stop_unknown',
                'cleanup_error': cleanup_error, 'status': status, 'error': error})
        result = {'status': status, 'plan_hash': plan['plan_hash'], 'session': session,
                  'execution_kind': 'native' if backend_factory is None else 'authored_test',
                  'error': error, 'cleanup_error': cleanup_error,
                  'unresolved_calls': [p.parent.name for p in sorted((root/'jobs').glob('*/started.json'))
                                       if not (p.parent/'receipt.json').exists()],
                  'accounting': session_accounting(root, STAGE, plan, require_closed=True)}
        publish(directory/f'outcome-{session}.json', result)
        if status == 'passed':
            result.update(calls=_validate_calls(root, plan), outputs=_outputs(root))
            result['closure_hash'] = content_hash(result)
            publish(root/'closed.json', result)
            validate_closed(root, plan)
        return result


def native_entry(root):
    root = Path(root).resolve()
    verify_import_origins(root)
    plan = verify(root)
    if os.environ.get('OUTCOME_READER_PROBE_PLAN') != plan['plan_hash']:
        raise ValueError('native launch plan mismatch')
    return run(root)


def launch(root: Path) -> dict:
    root = Path(root).resolve()
    plan = verify(root)
    if (root/'closed.json').exists():
        return read(root/'closed.json')
    directory = root/'launches'/uuid.uuid4().hex
    directory.mkdir(parents=True)
    environment = {**os.environ, 'PYTHONPATH': str(root/'source/src'), 'PYTHONDONTWRITEBYTECODE': '1',
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_DATASETS_OFFLINE': '1',
        'OUTCOME_READER_PROBE_SERVING': str(root), 'OUTCOME_READER_PROBE_PLAN': plan['plan_hash']}
    command = ['/usr/bin/sandbox-exec', '-f', str(root/'native.sb'), sys.executable,
               '-B', '-m', 'outcome_poc.reader_probe', '_serve', '--root', str(root)]
    publish(directory/'launch.json', {'plan_hash': plan['plan_hash'], 'profile': identity(root/'native.sb'),
                                     'command': command, 'start_ns': continuous_ns()})
    # Output remains durable even when the coordinator cannot publish a result.
    with (directory/'stdout.txt').open('w') as stdout, (directory/'stderr.txt').open('w') as stderr:
        completed = subprocess.run(command, cwd=root/'source', env=environment, stdout=stdout, stderr=stderr)
    if (root/'closed.json').exists():
        # stdout is deliberately silent on success, so it was final before sealing.
        verify(root)
        return read(root/'closed.json')
    outcomes = sorted((root/'stages'/STAGE).glob('outcome-*.json'), key=lambda p:p.stat().st_mtime_ns)
    return read(outcomes[-1]) if outcomes else {'status':'blocked', 'returncode':completed.returncode,
                                               'launch':str(directory), 'plan_hash':plan['plan_hash']}

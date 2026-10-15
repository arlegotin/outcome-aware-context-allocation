"""Warm spawned reader with authoritative sleep-inclusive parent deadlines.

The immutable worker's internal timing remains diagnostic. No active-clock
duration contributes to this supervisor's lifecycle records or deadlines.
"""
from dataclasses import replace
import math
import multiprocessing
import queue
import threading

from ..generation import _reader_worker
from ..schemas import ReaderResult, validate_record
from .clock import continuous_ns


class _Receiver:
    """Only this daemon enters recv, which can block on an incomplete frame."""
    def __init__(self, connection):
        self.connection = connection
        self.messages = queue.Queue(maxsize=8)
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _offer(self, item):
        while not self.stopping.is_set():
            try:
                self.messages.put(item, timeout=.1)
                return True
            except queue.Full:
                pass
        return False

    def _run(self):
        try:
            while not self.stopping.is_set():
                if not self._offer((True, self.connection.recv())):
                    return
        except BaseException as error:
            self._offer((False, error))

    def get(self, timeout):
        ok, value = self.messages.get(timeout=timeout)
        if not ok:
            raise value
        return value

    def stop(self):
        self.stopping.set()
        self.thread.join(.1)
        if self.thread.is_alive():
            raise RuntimeError('reader receiver could not be stopped')


class ContinuousBackend:
    """Use the original reader protocol, retaining progress and explicit recovery.

    Startup/recovery and synchronization each have their own bounded interval.
    Generation never retries: a subsequent caller may explicitly reload/sync.
    """
    _poll_seconds = .1

    def __init__(self, factory, *, startup_timeout=120., clock=continuous_ns):
        if not math.isfinite(startup_timeout) or startup_timeout <= 0:
            raise ValueError('startup timeout must be finite and positive')
        self.factory, self.startup_timeout, self.clock = factory, startup_timeout, clock
        self.lifecycle = []
        self.last_resources = {}
        self.job_owner = self.pending_owner = None
        self.peak_mlx_bytes = None
        self.worker = self.connection = self.receiver = None
        self._start()

    @property
    def worker_pid(self):
        return self.worker.pid if self.worker and self.worker.is_alive() else None

    def _deadline(self, start, seconds):
        return start + int(seconds * 1_000_000_000)

    def _check_deadline(self, deadline):
        now = self.clock()
        if now >= deadline:
            raise TimeoutError('continuous reader deadline expired')
        return now

    def _receive(self, deadline):
        while True:
            now = self._check_deadline(deadline)
            try:
                value = self.receiver.get(timeout=min(self._poll_seconds, (deadline - now) / 1e9))
            except queue.Empty:
                self._check_deadline(deadline)
                continue
            except TimeoutError:
                raise
            except (OSError, EOFError):
                # Sleep/deadline expiry dominates a transport error at wake.
                self._check_deadline(deadline)
                raise
            self._check_deadline(deadline)
            return value

    def _record(self, kind, pid, start, *, owner=None, status='ok'):
        self.lifecycle.append({'kind': kind, 'pid': pid, 'start_ns': start,
                               'stop_ns': self.clock(), 'owner': owner,
                               'status': status, 'clock_domain': 'mach_continuous_time'})

    def _resources(self, values):
        self.last_resources = dict(values)
        peak = values.get('peak_mlx_bytes')
        if peak is not None:
            self.peak_mlx_bytes = max(peak, self.peak_mlx_bytes or 0)

    def _start(self):
        start = self.clock()
        deadline = self._deadline(start, self.startup_timeout)
        owner = self.pending_owner
        child = None
        try:
            if self.worker is not None:
                self._terminate('worker_failure')
                owner = self.pending_owner
            context = multiprocessing.get_context('spawn')
            self.connection, child = context.Pipe()
            self.worker = context.Process(target=_reader_worker, args=(child, self.factory), daemon=True)
            self.worker.start()
            child.close()
            child = None
            self.receiver = _Receiver(self.connection)
            message = self._receive(deadline)
            if message[0] != 'ready':
                raise RuntimeError(f'reader startup failed: {message}')
            self.tokenizer = message[1]
            self._resources(message[2])
            self._check_deadline(deadline)
        except BaseException as error:
            try:
                self._terminate('startup_failure')
            finally:
                if child is not None:
                    child.close()
                self._record('load', None, start, owner=owner, status='infra_error')
            if isinstance(error, (OSError, EOFError)) and not isinstance(error, TimeoutError):
                raise RuntimeError(f'reader startup failed: {error}') from error
            raise
        self._record('load', self.worker.pid, start, owner=owner)
        self.pending_owner = None

    def _terminate(self, reason):
        start = self.clock()
        pid = self.worker.pid if self.worker else None
        if reason != 'closed':
            self.pending_owner = self.pending_owner or self.job_owner
        errors = []
        try:
            if self.worker:
                if self.worker.is_alive():
                    self.worker.terminate()
                if self.worker.pid is not None:
                    self.worker.join(self._poll_seconds)
                    if self.worker.is_alive():
                        self.worker.kill()
                        self.worker.join(self._poll_seconds)
                    if self.worker.is_alive():
                        raise RuntimeError('reader worker could not be killed')
                self.worker.close()
                self.worker = None
        except BaseException as error:
            errors.append(error)
        try:
            if self.connection:
                self.connection.close()
                self.connection = None
        except BaseException as error:
            errors.append(error)
        try:
            if self.receiver:
                self.receiver.stop()
                self.receiver = None
        except BaseException as error:
            errors.append(error)
        self._record(reason, pid, start, owner=self.pending_owner,
                     status='infra_error' if errors else 'ok')
        if errors:
            for extra in errors[1:]:
                errors[0].add_note(f'additional cleanup failure: {type(extra).__name__}: {extra}')
            raise errors[0]

    def synchronize(self):
        if self.worker_pid is None:
            self._start()
        deadline = self._deadline(self.clock(), self.startup_timeout)
        try:
            self._check_deadline(deadline)
            self.connection.send(('sync',))
            message = self._receive(deadline)
            if message[0] != 'synced':
                raise RuntimeError(f'reader synchronization failed: {message}')
        except TimeoutError:
            self._terminate('synchronization_timeout')
            raise
        except BaseException:
            self._terminate('synchronization_failure')
            raise

    def generate(self, prompt, request, *, rendered=False, prefix_cache=None):
        validate_record(request)
        if prefix_cache is not None or request.cache_mode != 'none':
            raise ValueError('prefix/cache reuse unsupported in follow-up')
        if self.worker_pid is None:
            self._start()
        deadline = self._deadline(self.clock(), request.timeout_seconds)
        text, prompt_ids, token_ids = '', [], []
        try:
            self._check_deadline(deadline)
            self.connection.send(('generate', prompt, request, rendered, None))
            while True:
                message = self._receive(deadline)
                if message[0] == 'progress':
                    _, text, prompt_ids, token_ids, resources = message
                    self._resources(resources)
                    if getattr(self, 'progress_callback', None):
                        self.progress_callback(text, prompt_ids, token_ids)
                elif message[0] == 'result':
                    result = message[1]
                    validate_record(result)
                    self._resources(message[2])
                    diagnostic = {f'diagnostic_active_clock_{key}': value
                                  for key, value in result.telemetry.items()}
                    diagnostic['diagnostic_active_clock_domain'] = 'legacy worker; not continuous'
                    self._check_deadline(deadline)
                    return replace(result, telemetry=diagnostic)
                else:
                    raise RuntimeError(f'unexpected reader message: {message}')
        except TimeoutError:
            self._terminate('forced_timeout')
            return ReaderResult(text, None, [], 'timeout', len(prompt_ids), len(token_ids),
                                prompt_ids, token_ids, 'forced_timeout')
        except Exception as error:
            self._terminate('worker_failure')
            return ReaderResult(text, None, [], 'infra_error', len(prompt_ids), len(token_ids),
                                prompt_ids, token_ids, f'infra_error:{type(error).__name__}:{error}')
        except BaseException:
            self._terminate('worker_failure')
            raise

    def close(self):
        if self.worker or self.connection or self.receiver:
            # Terminate directly: a close send must not wait on a stalled worker.
            self._terminate('closed')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

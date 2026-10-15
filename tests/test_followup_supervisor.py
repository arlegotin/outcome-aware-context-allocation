"""Deadline faults use a deterministic transport; one fixture uses real spawn."""
from dataclasses import replace
import importlib
import os
import queue
import struct
import threading
import time

import pytest

from outcome_poc.schemas import GenerationRequest, ReaderResult, validate_record


REQUEST = GenerationRequest('r', 'm', 'p', 'd', 'answer', 8192, 256, 1., 'none')
RESULT = ReaderResult('blue', 'blue', [], 'ok', 2, 1, [1, 2], [3], 'stop',
                      {'clean_prefill_seconds': .25, 'logical_prompt_tokens': 2})


class Clock:
    def __init__(self):
        self.now = 10_000_000_000

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += int(seconds * 1_000_000_000)


class Process:
    pid = 42

    def __init__(self, **kwargs):
        self.alive = False

    def start(self): self.alive = True
    def is_alive(self): return self.alive
    def terminate(self): self.alive = False
    def kill(self): self.alive = False
    def join(self, timeout): pass
    def close(self): pass


class Transport:
    def __init__(self, clock, events):
        self.clock, self.events = clock, list(events)
        self.poll_bounds, self.sent = [], []
        self.closed = False
        self.stopped = False

    def poll(self, timeout):
        self.poll_bounds.append(timeout)
        if not self.events:
            self.clock.advance(timeout)
            return False
        event = self.events[0]
        self.clock.advance(event.get('poll_sleep', 0))
        return True

    def recv(self):
        event = self.events.pop(0)
        self.clock.advance(event.get('recv_sleep', 0))
        if 'error' in event:
            raise event['error']
        return event['message']

    def send(self, value): self.sent.append(value)
    def close(self): self.closed = True

    def get(self, timeout):
        if not self.poll(timeout):
            raise queue.Empty
        return self.recv()

    def stop(self): self.stopped = True


class Sender:
    def __init__(self, connection):
        self.connection = connection

    def submit(self, message):
        self.connection.send(message)
        completion = queue.Queue(maxsize=1)
        completion.put_nowait(None)
        return completion

    def stop(self): pass


def message(value, **kwargs):
    return {'message': value, **kwargs}


@pytest.fixture
def harness(monkeypatch):
    module = importlib.import_module('outcome_poc.followup.supervisor')
    # The queue is the scheduling boundary; only deterministic queue waits are
    # substituted. Real spawn and partial-frame tests exercise the actual pump.
    monkeypatch.setattr(module, '_Receiver', lambda connection: connection)
    monkeypatch.setattr(module, '_Sender', Sender)
    import multiprocessing
    clock = Clock()
    transports = []

    def build(events=(), *, ready=None, startup_timeout=1., silent_startup=False):
        startup = [] if silent_startup else [ready or message(('ready', 'tokenizer', {}))]
        transport = Transport(clock, [*startup, *events])
        transports.append(transport)

        class Context:
            def Pipe(self): return transport, Transport(clock, [])
            Process = Process

        monkeypatch.setattr(multiprocessing, 'get_context', lambda method: Context())
        return module.ContinuousBackend(None, startup_timeout=startup_timeout, clock=clock)

    return build, clock, transports


@pytest.mark.parametrize('wake', ['poll_sleep', 'recv_sleep'])
def test_late_result_is_timeout_and_keeps_only_earlier_partial(harness, wake):
    build, clock, transports = harness
    backend = build([
        message(('progress', 'partial', [1, 2], [9], {'peak_mlx_bytes': 64})),
        message(('result', RESULT, {}), **{wake: 200}),
    ])
    backend.job_owner = {'job_id': 'late'}
    result = backend.generate('prompt', REQUEST, rendered=True)
    assert (result.status, result.raw_output, result.stop_reason) == ('timeout', 'partial', 'forced_timeout')
    assert (result.prompt_tokens, result.generated_tokens) == (2, 1)
    assert result.generated_token_ids == [9]
    assert backend.worker_pid is None
    assert backend.pending_owner == {'job_id': 'late'}
    assert backend.peak_mlx_bytes == 64
    assert all(0 < bound <= .1 for bound in transports[0].poll_bounds)
    assert backend.lifecycle[-1]['start_ns'] == 210_000_000_000
    assert backend.lifecycle[-1]['stop_ns'] == clock()


def test_empty_polls_still_reach_generation_deadline(harness):
    build, clock, _ = harness
    backend = build()
    result = backend.generate('prompt', REQUEST)
    assert result.status == 'timeout'
    assert clock() == 11_000_000_000
    assert result.prompt_token_ids == result.generated_token_ids == []


def test_startup_without_ready_reaches_continuous_deadline(harness):
    build, clock, transports = harness
    with pytest.raises(TimeoutError):
        build(silent_startup=True)
    assert clock() == 11_000_000_000
    assert transports[0].closed


@pytest.mark.parametrize('event', [None, 'poll_sleep', 'recv_sleep'])
def test_startup_deadline_is_bounded_even_with_ready_message(harness, event):
    build, clock, transports = harness
    ready = message(('ready', 'tokenizer', {}), **({event: 5} if event else {}))
    if event is None:
        ready = {'error': EOFError('startup worker died')}
    with pytest.raises(RuntimeError if event is None else TimeoutError):
        build(ready=ready)
    assert transports[0].closed
    assert max(transports[0].poll_bounds) <= .1


@pytest.mark.parametrize('event', [None, 'poll_sleep', 'recv_sleep'])
def test_synchronization_deadline_is_bounded(harness, event):
    build, _, _ = harness
    events = [] if event is None else [message(('synced',), **{event: 5})]
    backend = build(events)
    with pytest.raises(TimeoutError):
        backend.synchronize()
    assert backend.worker_pid is None
    assert backend.lifecycle[-1]['kind'] == 'synchronization_timeout'


def test_synchronization_failure_stops_worker_and_retains_owner(harness):
    build, _, _ = harness
    backend = build([message(('error', 'device failed'))])
    backend.job_owner = {'job_id': 'sync'}
    with pytest.raises(RuntimeError, match='synchronization'):
        backend.synchronize()
    assert backend.worker_pid is None
    assert backend.pending_owner == {'job_id': 'sync'}
    assert backend.lifecycle[-1]['kind'] == 'synchronization_failure'


def test_worker_failure_preserves_partial_and_never_retries(harness):
    build, _, transports = harness
    backend = build([message(('progress', 'partial', [1, 2], [9], {})),
                     {'error': EOFError('worker gone')}])
    result = backend.generate('prompt', REQUEST)
    assert (result.status, result.raw_output, result.generated_token_ids) == ('infra_error', 'partial', [9])
    assert backend.worker_pid is None
    assert len([row for row in transports[0].sent if row[0] == 'generate']) == 1


def test_results_keep_worker_timing_only_as_schema_valid_diagnostics(harness):
    build, _, _ = harness
    with build([message(('result', RESULT, {'peak_mlx_bytes': 80}))]) as backend:
        result = backend.generate('prompt', REQUEST)
        assert result.status == 'ok'
        assert 'clean_prefill_seconds' not in result.telemetry
        assert result.telemetry['diagnostic_active_clock_clean_prefill_seconds'] == .25
        validate_record(result)
        assert backend.peak_mlx_bytes == 80
        assert backend.lifecycle[0]['start_ns'] == backend.lifecycle[0]['stop_ns'] == 10_000_000_000
        assert backend.lifecycle[0]['clock_domain'] == 'mach_continuous_time'


def test_prefix_reuse_is_rejected_before_generation(harness):
    build, _, transports = harness
    with build() as backend:
        with pytest.raises(ValueError, match='prefix'):
            backend.generate('prompt', REQUEST, prefix_cache={'operation': 'capture'})
        assert not transports[0].sent


def test_prefix_request_without_cache_is_rejected(harness):
    build, _, transports = harness
    with build() as backend:
        with pytest.raises(ValueError, match='prefix'):
            backend.generate('prompt', replace(REQUEST, cache_mode='within_query_prefix'))
        assert not transports[0].sent


def test_cleanup_failure_result_retains_generated_work_and_failure(harness):
    build, _, _ = harness
    failed = replace(RESULT, status='infra_error', stop_reason='infra_error:cleanup failed')
    with build([message(('result', failed, {}))]) as backend:
        result = backend.generate('prompt', REQUEST)
        assert (result.status, result.raw_output, result.stop_reason) == (
            'infra_error', 'blue', 'infra_error:cleanup failed')
        assert result.generated_token_ids == [3]
        assert result.telemetry['diagnostic_active_clock_clean_prefill_seconds'] == .25


def test_failed_termination_is_visible_and_stamped(harness, monkeypatch):
    build, clock, _ = harness
    backend = build()
    monkeypatch.setattr(backend.worker, 'terminate', lambda: None)
    monkeypatch.setattr(backend.worker, 'kill', lambda: None)
    with pytest.raises(RuntimeError, match='could not be killed'):
        backend.generate('prompt', REQUEST)
    assert backend.lifecycle[-1]['status'] == 'infra_error'
    assert backend.lifecycle[-1]['kind'] == 'forced_timeout'
    assert backend.lifecycle[-1]['start_ns'] == backend.lifecycle[-1]['stop_ns'] == clock()
    assert backend.worker is not None  # retained so cleanup can be retried explicitly
    backend.worker.alive = False
    backend.close()


@pytest.mark.parametrize('primary', ['timeout', 'infra_error'])
def test_cleanup_exception_carries_terminal_result_and_partial(harness, monkeypatch, primary):
    build, _, _ = harness
    events = [message(('progress', 'partial', [1, 2], [9], {}))]
    if primary == 'infra_error':
        events.append({'error': EOFError('worker gone')})
    backend = build(events)
    monkeypatch.setattr(backend.worker, 'terminate', lambda: None)
    monkeypatch.setattr(backend.worker, 'kill', lambda: None)
    try:
        with pytest.raises(RuntimeError) as caught:
            backend.generate('prompt', REQUEST)
        terminal = getattr(caught.value, 'result', None)
        assert isinstance(terminal, ReaderResult)
        assert terminal.status == primary
        assert (terminal.raw_output, terminal.prompt_token_ids, terminal.generated_token_ids) == (
            'partial', [1, 2], [9])
        assert (terminal.prompt_tokens, terminal.generated_tokens) == (2, 1)
        assert 'could not be killed' in str(caught.value.cleanup_error)
        assert caught.value.__cause__ is caught.value.cleanup_error
    finally:
        backend.worker.alive = False
        backend.close()


def test_context_exit_does_not_replace_structured_cleanup_failure(harness, monkeypatch):
    build, _, _ = harness
    backend = build([message(('progress', 'partial', [1, 2], [9], {}))])
    monkeypatch.setattr(backend.worker, 'terminate', lambda: None)
    monkeypatch.setattr(backend.worker, 'kill', lambda: None)
    try:
        with pytest.raises(RuntimeError) as caught:
            with backend:
                backend.generate('prompt', REQUEST)
        terminal = getattr(caught.value, 'result', None)
        assert isinstance(terminal, ReaderResult)
        assert (terminal.status, terminal.raw_output) == ('timeout', 'partial')
    finally:
        backend.worker.alive = False
        backend.close()


class WorkerTokenizer:
    chat_template = 'fixture'


class FixtureBackend:
    tokenizer = WorkerTokenizer()

    def generate(self, prompt, request, *, rendered=False):
        self.progress_callback('partial', [1, 2], [9])
        if prompt == 'stall':
            time.sleep(30)
        if prompt == 'die':
            os._exit(17)
        if prompt == 'raise':
            raise RuntimeError('backend failed after progress')
        return RESULT

    def synchronize(self): pass


def fixture_factory():
    return FixtureBackend()


def partial_frame_worker(connection, factory):
    connection.send(('ready', WorkerTokenizer(), {}))
    connection.recv()  # one paid request
    connection.send(('progress', 'partial', [1, 2], [9], {}))
    # Connection.poll reports readable on this frame, but recv waits forever
    # without the rest. A parent deadline must not enter that blocking recv.
    os.write(connection.fileno(), struct.pack('!i', 100_000) + b'X')
    time.sleep(30)


def stalled_command_reader(connection, factory):
    connection.send(('ready', WorkerTokenizer(), {}))
    time.sleep(30)  # ready but never consumes a command


def test_stalled_command_reader_cannot_block_large_outbound_request(monkeypatch):
    module = importlib.import_module('outcome_poc.followup.supervisor')
    monkeypatch.setattr(module, '_reader_worker', stalled_command_reader)
    before = time.monotonic()
    with module.ContinuousBackend(fixture_factory, startup_timeout=5) as backend:
        result = backend.generate('X' * 1_000_000, replace(REQUEST, timeout_seconds=.1))
        assert result.status == 'timeout'
        assert backend.worker_pid is None
        assert backend.receiver is None
        assert backend.sender is None
    assert time.monotonic() - before < 3


def test_synchronization_send_is_bounded_behind_stalled_write(monkeypatch):
    module = importlib.import_module('outcome_poc.followup.supervisor')
    monkeypatch.setattr(module, '_reader_worker', stalled_command_reader)
    before = time.monotonic()
    with module.ContinuousBackend(fixture_factory, startup_timeout=5) as backend:
        # Occupy the sender with a real write to a nonreading peer. The tiny
        # sync command must wait for its send under its own deadline as well.
        entered = threading.Event()
        send = backend.connection.send
        def entered_send(value):
            entered.set()
            return send(value)
        monkeypatch.setattr(backend.connection, 'send', entered_send)
        backend.sender.submit(('generate', 'X' * 1_000_000, REQUEST, False, None))
        assert entered.wait(1)
        backend.startup_timeout = .15
        with pytest.raises(TimeoutError):
            backend.synchronize()
        assert backend.worker_pid is None
        assert backend.sender is None
    assert time.monotonic() - before < 3


class SerializationGate(str):
    entered = threading.Event()
    release = threading.Event()

    def __reduce_ex__(self, protocol):
        self.entered.set()
        self.release.wait(30)
        return str, (str(self),)


def test_serialization_is_inside_deadline_and_cleanup_failure_keeps_timeout():
    module = importlib.import_module('outcome_poc.followup.supervisor')
    SerializationGate.entered.clear()
    SerializationGate.release.clear()
    backend = module.ContinuousBackend(fixture_factory, startup_timeout=5)
    before = time.monotonic()
    try:
        with pytest.raises(module.CleanupFailure) as caught:
            backend.generate(SerializationGate('prompt'), replace(REQUEST, timeout_seconds=.1))
        assert SerializationGate.entered.is_set()
        assert caught.value.result.status == 'timeout'
        assert 'sender could not be stopped' in str(caught.value.cleanup_error)
        assert time.monotonic() - before < 3
    finally:
        SerializationGate.release.set()
        if backend.sender:
            backend.sender.thread.join(1)
        backend.close()


def test_real_worker_exception_keeps_accepted_progress_and_original_failure():
    module = importlib.import_module('outcome_poc.followup.supervisor')
    with module.ContinuousBackend(fixture_factory, startup_timeout=5) as backend:
        result = backend.generate('raise', REQUEST)
        assert result.status == 'infra_error'
        assert (result.raw_output, result.prompt_token_ids, result.generated_token_ids) == (
            'partial', [1, 2], [9])
        assert (result.prompt_tokens, result.generated_tokens) == (2, 1)
        assert 'backend failed after progress' in result.stop_reason


def test_partial_frame_cannot_block_generation_or_cleanup(monkeypatch):
    module = importlib.import_module('outcome_poc.followup.supervisor')
    monkeypatch.setattr(module, '_reader_worker', partial_frame_worker)
    before = time.monotonic()
    with module.ContinuousBackend(fixture_factory, startup_timeout=5) as backend:
        result = backend.generate('partial-frame', replace(REQUEST, timeout_seconds=.15))
        assert (result.status, result.raw_output, result.generated_token_ids) == ('timeout', 'partial', [9])
        assert backend.worker_pid is None
        assert backend.receiver is None
    assert time.monotonic() - before < 3


def test_real_spawn_stays_warm_then_preserves_timeout_and_death():
    module = importlib.import_module('outcome_poc.followup.supervisor')
    request = replace(REQUEST, timeout_seconds=.3)
    with module.ContinuousBackend(fixture_factory, startup_timeout=5) as backend:
        pid = backend.worker_pid
        backend.synchronize()
        assert backend.generate('ok', request).status == 'ok'
        assert backend.generate('ok', request).status == 'ok'
        assert backend.worker_pid == pid
        timeout = backend.generate('stall', request)
        assert (timeout.status, timeout.raw_output, timeout.generated_token_ids) == ('timeout', 'partial', [9])
        assert backend.worker_pid is None
        backend.synchronize()
        assert backend.worker_pid != pid
        failed = backend.generate('die', request)
        assert (failed.status, failed.raw_output, failed.generated_token_ids) == ('infra_error', 'partial', [9])
        assert backend.worker_pid is None

"""Hardware-bound clock calls are faked; conversion and failure policy are real."""
import ctypes
import importlib

import pytest


class Function:
    def __init__(self, call):
        self.call = call

    def __call__(self, *args):
        return self.call(*args)


class MachLibrary:
    def __init__(self, *, ticks=2**63 + 7, numer=125, denom=3, status=0):
        self.mach_continuous_time = Function(lambda: ticks)

        def timebase(pointer):
            pointer._obj.numer, pointer._obj.denom = numer, denom
            return status

        self.mach_timebase_info = Function(timebase)

        def sysctl(name, output, size, new, new_size):
            assert name == b'kern.bootsessionuuid'
            value = b'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE\0'
            ctypes.memmove(output, value, len(value))
            size._obj.value = len(value)
            return 0

        self.sysctlbyname = Function(sysctl)


@pytest.fixture
def clock_module(monkeypatch):
    module = importlib.import_module('outcome_poc.followup.clock')
    monkeypatch.setattr(module.sys, 'platform', 'darwin')
    module._clock.cache_clear()
    yield module
    module._clock.cache_clear()


def test_large_tick_conversion_is_integer_exact(clock_module, monkeypatch):
    library = MachLibrary()
    monkeypatch.setattr(clock_module, '_load_library', lambda: library)
    # (2**63 + 7) * 125 // 3, hand checked without float intermediates.
    assert clock_module.continuous_ns() == 384307168202282325625
    assert library.mach_continuous_time.restype is ctypes.c_uint64
    identity = clock_module.clock_identity()
    assert identity['name'] == 'mach_continuous_time'
    assert identity['includes_sleep'] is True
    assert (identity['timebase_numer'], identity['timebase_denom']) == (125, 3)
    assert clock_module.boot_identity() == 'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE'


@pytest.mark.parametrize('fault', ['platform', 'library', 'symbol', 'status', 'denom', 'numer'])
def test_unavailable_clock_fails_closed(clock_module, monkeypatch, fault):
    library = MachLibrary(**({'status': 5} if fault == 'status' else
                             {'denom': 0} if fault == 'denom' else
                             {'numer': 0} if fault == 'numer' else {}))
    if fault == 'symbol':
        del library.mach_continuous_time
    if fault == 'platform':
        monkeypatch.setattr(clock_module.sys, 'platform', 'linux')
    if fault == 'library':
        def unavailable():
            raise OSError('missing libSystem')
        monkeypatch.setattr(clock_module, '_load_library', unavailable)
    else:
        monkeypatch.setattr(clock_module, '_load_library', lambda: library)
    with pytest.raises(RuntimeError, match='continuous clock'):
        clock_module.continuous_ns()


def test_boot_identity_refuses_unavailable_or_empty_value(clock_module, monkeypatch):
    library = MachLibrary()
    monkeypatch.setattr(clock_module, '_load_library', lambda: library)
    library.sysctlbyname = Function(lambda *args: -1)
    with pytest.raises(RuntimeError, match='boot identity'):
        clock_module.boot_identity()
    library.sysctlbyname = Function(lambda *args: 0)
    with pytest.raises(RuntimeError, match='boot identity'):
        clock_module.boot_identity()


def test_native_clock_and_boot_identity_are_available_on_darwin():
    import sys
    if sys.platform != 'darwin':
        pytest.skip('requires Darwin continuous clock')
    module = importlib.import_module('outcome_poc.followup.clock')
    assert module.continuous_ns() <= module.continuous_ns()
    assert module.boot_identity() == module.boot_identity()

"""Darwin sleep-inclusive elapsed time; no fallback to an active clock."""
import ctypes
from functools import lru_cache
import sys


class _Timebase(ctypes.Structure):
    _fields_ = [('numer', ctypes.c_uint32), ('denom', ctypes.c_uint32)]


def _load_library():
    return ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)


@lru_cache(maxsize=1)
def _clock():
    try:
        if sys.platform != 'darwin':
            raise RuntimeError('requires Darwin')
        library = _load_library()
        ticks = library.mach_continuous_time
        ticks.argtypes, ticks.restype = [], ctypes.c_uint64
        timebase = library.mach_timebase_info
        timebase.argtypes = [ctypes.POINTER(_Timebase)]
        timebase.restype = ctypes.c_int
        ratio = _Timebase()
        if timebase(ctypes.byref(ratio)) != 0 or ratio.numer == 0 or ratio.denom == 0:
            raise RuntimeError('invalid mach_timebase_info')
        return library, ticks, int(ratio.numer), int(ratio.denom)
    except (AttributeError, OSError, RuntimeError) as error:
        raise RuntimeError(f'continuous clock unavailable: {error}') from error


def continuous_ns() -> int:
    """Integer nanoseconds in this boot's mach_continuous_time domain."""
    _, ticks, numer, denom = _clock()
    return int(ticks()) * numer // denom


def clock_identity() -> dict:
    _, _, numer, denom = _clock()
    return {'name': 'mach_continuous_time', 'unit': 'nanoseconds',
            'platform': 'darwin', 'includes_sleep': True,
            'conversion': 'ticks * numer // denom',
            'timebase_numer': numer, 'timebase_denom': denom}


def boot_identity() -> str:
    """Stable boot-session UUID; callers must refuse a different resume boot."""
    library, _, _, _ = _clock()
    try:
        sysctl = library.sysctlbyname
        sysctl.argtypes = [ctypes.c_char_p, ctypes.c_void_p,
                          ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]
        sysctl.restype = ctypes.c_int
        output = ctypes.create_string_buffer(128)
        size = ctypes.c_size_t(ctypes.sizeof(output))
        if sysctl(b'kern.bootsessionuuid', output, ctypes.byref(size), None, 0) != 0:
            raise RuntimeError('kern.bootsessionuuid unavailable')
        value = output.value.decode('ascii').strip()
        if not value or size.value > ctypes.sizeof(output):
            raise RuntimeError('empty or invalid kern.bootsessionuuid')
        return value
    except (AttributeError, OSError, UnicodeError, RuntimeError) as error:
        raise RuntimeError(f'boot identity unavailable: {error}') from error

"""Measured native environment; denied observations remain null, never guesses."""
from datetime import datetime, timezone
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from .storage import atomic_json


def resource_gate(physical_memory_bytes: int | None, working_set_bytes: int | None) -> dict:
    if physical_memory_bytes is None or working_set_bytes is None:
        return {'passed': False, 'reserve_bytes': None, 'reason': 'memory measurement unavailable'}
    reserve = max(4 * 1024**3, (physical_memory_bytes + 4) // 5)
    return {'passed': working_set_bytes <= physical_memory_bytes - reserve,
            'reserve_bytes': reserve, 'working_set_bytes': working_set_bytes,
            'limit_bytes': physical_memory_bytes - reserve}


def discover(output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    errors = []
    def command(argv):
        try:
            return subprocess.run(argv, check=True, text=True, capture_output=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f'{argv}: {error}; {getattr(error, "stderr", "")}')
            return None
    memory = command(['sysctl', '-n', 'hw.memsize'])
    try:
        memory = int(memory) if memory else None
    except ValueError:
        errors.append('sysctl hw.memsize returned a non-integer')
        memory = None
    chip = command(['sysctl', '-n', 'machdep.cpu.brand_string'])
    rss = swap = None
    try:
        import psutil
        rss = psutil.Process().memory_info().rss
        swap = psutil.swap_memory().used
    except (ImportError, OSError) as error:
        errors.append(f'memory telemetry: {error}')
    result = {'measured_utc': datetime.now(timezone.utc).isoformat(),
              'architecture': platform.machine(), 'chip': chip,
              'physical_memory_bytes': memory, 'macos_version': command(['sw_vers', '-productVersion']),
              'macos_build': command(['sw_vers', '-buildVersion']),
              'python_version': platform.python_version(), 'python_executable': sys.executable,
              'disk_free_bytes': shutil.disk_usage(output_dir).free,
              'rss_bytes': rss, 'swap_used_bytes': swap,
              'cache_bytes': sum(p.stat().st_size for p in Path('.cache').rglob('*') if p.is_file()),
              'packages': {d.metadata['Name']: d.version for d in metadata.distributions()},
              'build_tools': {'clang': command(['clang', '--version']),
                              'xcode': command(['xcodebuild', '-version'])},
              'errors': errors, 'resource_gate': resource_gate(memory, rss)}
    # Native interpreter is independently required, beyond the memory headroom check.
    result['native_supported'] = platform.machine() == 'arm64' and sys.version_info[:2] in {(3, 11), (3, 12)}
    atomic_json(output_dir / 'environment.json', result)
    return result


def main(args) -> int:
    config = json.loads(Path(args.config).read_text())
    result = discover(Path(config['output_dir']))
    print(json.dumps({'native_supported': result['native_supported'], 'resource_gate': result['resource_gate'],
                      'errors': result['errors']}, indent=2))
    return 0 if result['native_supported'] and result['resource_gate']['passed'] else 1

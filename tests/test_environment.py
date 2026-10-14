"""Discovery must fail closed when hardware measurements are unavailable."""
import json
import subprocess

from outcome_poc.environment import discover, resource_gate


def test_denied_sysctl_does_not_guess_physical_memory(tmp_path, monkeypatch):
    real_run = subprocess.run

    def denied(command, **kwargs):
        if command[0] == 'sysctl':
            raise subprocess.CalledProcessError(1, command, stderr='Operation not permitted')
        return real_run(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', denied)
    result = discover(tmp_path)
    assert result['physical_memory_bytes'] is None
    assert any('sysctl' in error for error in result['errors'])
    assert result['resource_gate']['passed'] is False
    assert json.loads((tmp_path / 'environment.json').read_text())['physical_memory_bytes'] is None


def test_resource_gate_reserves_twenty_percent_or_four_gib():
    assert resource_gate(36 * 1024**3, 29 * 1024**3)['passed'] is False
    assert resource_gate(36 * 1024**3, 28 * 1024**3)['passed'] is True
    assert resource_gate(8 * 1024**3, 5 * 1024**3)['passed'] is False
    assert resource_gate(None, 1)['passed'] is False
    assert resource_gate(36 * 1024**3, None)['passed'] is False

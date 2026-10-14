import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from outcome_poc.schemas import Task
from outcome_poc.storage import (
    append_jsonl, atomic_json, canonical_bytes, content_hash, read_jsonl,
)


def test_canonical_bytes_and_hash_use_exact_utf8_json():
    expected = b'{"a":"\xc3\xa9","b":2}'
    assert canonical_bytes({"b": 2, "a": "é"}) == expected
    assert content_hash({"b": 2, "a": "é"}) == hashlib.sha256(expected).hexdigest()


@pytest.mark.parametrize("invalid", [float("inf"), float("-inf"), float("nan")])
def test_canonical_bytes_reject_nonfinite_nested_values(invalid):
    with pytest.raises(ValueError):
        canonical_bytes({"nested": [{"time": invalid}]})


def test_canonical_bytes_validates_dataclass_and_preserves_booleans():
    assert canonical_bytes({"enabled": True}) == b'{"enabled":true}'
    assert canonical_bytes(Task("t", "fit", "Invented?", ["d"])) == (
        b'{"candidate_ids":["d"],"question":"Invented?","split":"fit","task_id":"t"}'
    )
    with pytest.raises(ValueError):
        canonical_bytes(Task("t", "fit", "Invented?", [True]))


def test_atomic_json_digest_matches_persisted_bytes(tmp_path):
    path = tmp_path / "nested" / "manifest.json"
    digest = atomic_json(path, {"value": "é"})
    assert path.read_bytes() == b'{"value":"\xc3\xa9"}'
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert list(path.parent.iterdir()) == [path]


def test_atomic_write_killed_before_replace_preserves_old_file_and_attempt(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_bytes(b'{"old":true}')
    script = '''
import os, sys, time
from pathlib import Path
from outcome_poc.storage import atomic_json
def stop_before_replace(source, destination):
    print(source, flush=True)
    while True:
        time.sleep(1)
os.replace = stop_before_replace
atomic_json(Path(sys.argv[1]), {"new": True})
'''
    process = subprocess.Popen([sys.executable, "-c", script, str(path)],
                               stdout=subprocess.PIPE, text=True)
    try:
        import selectors
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=10), "child never reached atomic replace"
        attempt = Path(process.stdout.readline().strip())
        process.kill()
        process.wait(timeout=10)
        assert path.read_bytes() == b'{"old":true}'
        assert attempt.parent == path.parent
        assert attempt.read_bytes() == b'{"new":true}'
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        process.stdout.close()


@pytest.mark.parametrize("writer", [atomic_json, append_jsonl])
def test_invalid_values_leave_existing_storage_unchanged(tmp_path, writer):
    path = tmp_path / "record.json"
    path.write_bytes(b'{"old":true}\n')
    with pytest.raises(ValueError):
        writer(path, {"elapsed": float("inf")})
    assert path.read_bytes() == b'{"old":true}\n'
    assert list(tmp_path.iterdir()) == [path]


def test_jsonl_appends_canonical_complete_records(tmp_path):
    path = tmp_path / "nested" / "events.jsonl"
    append_jsonl(path, {"b": 2, "a": "é"})
    append_jsonl(path, {"attempt": 2})
    assert path.read_bytes() == b'{"a":"\xc3\xa9","b":2}\n{"attempt":2}\n'
    assert list(read_jsonl(path)) == [{"a": "é", "b": 2}, {"attempt": 2}]


@pytest.mark.parametrize("tail", [b'{"attempt":', b'{"attempt":2}', b'\n', b'[]\n',
                                  b'{"value":NaN}\n'])
def test_jsonl_reports_corruption_or_truncation_with_line_number(tmp_path, tail):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"attempt":1}\n' + tail)
    records = read_jsonl(path)
    assert next(records) == {"attempt": 1}
    with pytest.raises(ValueError, match=r"line 2"):
        next(records)


def test_jsonl_refuses_append_to_incomplete_last_record(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"attempt":1}')
    with pytest.raises(ValueError):
        append_jsonl(path, {"attempt": 2})
    assert path.read_bytes() == b'{"attempt":1}'

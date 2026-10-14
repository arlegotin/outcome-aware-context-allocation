"""Canonical hashing and durable local writes with visible interrupted attempts."""

from collections.abc import Iterator
from dataclasses import fields, is_dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from .schemas import Prediction, validate_record


def _json_value(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        validate_record(value)
        result = {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
        if isinstance(value, Prediction):
            result["citations"] = [
                {"doc_id": doc_id, "sentence_index": sentence_index}
                for doc_id, sentence_index in value.citations
            ]
        return result
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("JSON values must be finite")
        return value
    if type(value) in (list, tuple):
        return [_json_value(item) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("JSON object keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    raise ValueError(f"Unsupported JSON value: {type(value).__name__}")


def canonical_bytes(value: object) -> bytes:
    """Canonical UTF-8 JSON, without a trailing newline or nonfinite values."""
    return json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path: Path, value: object) -> str:
    """Persist complete JSON atomically; retain temp files for interrupted writes."""
    payload = canonical_bytes(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="wb", prefix=f".{path.name}.",
                                     suffix=".tmp", dir=path.parent, delete=False) as stream:
        temporary_path = Path(stream.name)
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_path, path)
    _sync_directory(path.parent)
    return hashlib.sha256(payload).hexdigest()


def append_jsonl(path: Path, value: object) -> None:
    """Durably append one object to a single-writer ledger without repairing tails."""
    payload = canonical_bytes(value)
    if not payload.startswith(b"{"):
        raise ValueError("JSONL records must be objects")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell():
            stream.seek(-1, os.SEEK_END)
            if stream.read(1) != b"\n":
                raise ValueError(f"{path}: incomplete JSONL tail; append refused")
        stream.write(payload + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON value {value}")


def read_jsonl(path: Path) -> Iterator[dict]:
    """Yield ledger objects and report every malformed or incomplete record."""
    path = Path(path)
    with path.open("rb") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            try:
                if not raw_line.endswith(b"\n"):
                    raise ValueError("incomplete JSONL record (missing newline)")
                value = json.loads(raw_line, parse_constant=_reject_constant)
                if type(value) is not dict:
                    raise ValueError("JSONL record is not an object")
                _json_value(value)
            except (ValueError, UnicodeError) as error:
                raise ValueError(f"{path}: line {line_number}: {error}") from error
            yield value

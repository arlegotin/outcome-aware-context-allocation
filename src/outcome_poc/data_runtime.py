"""Annotation-free task/document readers for serving modules.

Serving code imports this module directly, never the preparation module.
"""

from dataclasses import fields
import json
from pathlib import Path

from .schemas import Document, Task, validate_record
from .storage import content_hash


def _loads(line: bytes) -> dict:
    def unique(pairs):
        row = {}
        for key, value in pairs:
            if key in row:
                raise ValueError('duplicate runtime JSON key')
            row[key] = value
        return row

    if not line.endswith(b'\n'):
        raise ValueError('incomplete runtime JSONL record')
    row = json.loads(line, object_pairs_hook=unique)
    if type(row) is not dict:
        raise ValueError('runtime JSONL record must be an object')
    return row


def _record(row: dict, kind):
    if set(row) != {field.name for field in fields(kind)}:
        raise ValueError(f'{kind.__name__} fields do not match runtime schema')
    value = kind(**row)
    validate_record(value)
    if isinstance(value, Document):
        if value.doc_id != content_hash([value.title, value.sentences]):
            raise ValueError('document content hash mismatch')
        if value.character_count != sum(map(len, value.sentences)):
            raise ValueError('document character count mismatch')
    if isinstance(value, Task) and (len(value.candidate_ids) != 10 or
                                   len(set(value.candidate_ids)) != 10):
        raise ValueError('core task must contain ten unique candidates')
    return value


class DocumentStore:
    """Keep only JSONL byte offsets in memory; deserialize one document per get."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.offsets = {}
        with self.path.open('rb') as stream:
            while True:
                offset = stream.tell()
                line = stream.readline()
                if not line:
                    break
                document = _record(_loads(line), Document)
                if document.doc_id in self.offsets:
                    raise ValueError('duplicate document ID')
                self.offsets[document.doc_id] = offset

    def get(self, doc_id: str) -> Document:
        with self.path.open('rb') as stream:
            stream.seek(self.offsets[doc_id])
            document = _record(_loads(stream.readline()), Document)
        if document.doc_id != doc_id:
            raise ValueError('document store changed after indexing')
        return document


def load_tasks(path: Path, split: str) -> list[Task]:
    """Load only the requested partition; reject annotations even on other rows."""
    tasks, seen = [], set()
    with Path(path).open('rb') as stream:
        for line in stream:
            task = _record(_loads(line), Task)
            if task.task_id in seen:
                raise ValueError('duplicate task ID')
            seen.add(task.task_id)
            if task.split == split:
                tasks.append(task)
    return tasks

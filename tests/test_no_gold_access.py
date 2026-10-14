import ast
import builtins
from dataclasses import fields
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from outcome_poc.schemas import Document, Task
from test_data import prepare_rows


def test_serving_import_closure_has_no_scorer_or_preparation_module():
    root = Path(__file__).parents[1] / 'src' / 'outcome_poc'
    pending = [name for name in ('runner', 'generation', 'retrieval', 'features', 'policies', 'data_runtime')
               if (root / f'{name}.py').exists()]
    visited = set()
    while pending:
        name = pending.pop()
        if name in visited: continue
        visited.add(name)
        assert name not in {'scoring', 'data'}, f'serving imported {name}'
        tree = ast.parse((root / f'{name}.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ''
                if node.level == 1:
                    pending.extend([module.split('.')[0]] if module else [alias.name for alias in node.names])
                elif module.startswith('outcome_poc.'):
                    pending.append(module.split('.')[1])
            if isinstance(node, ast.Import):
                pending.extend(alias.name.split('.')[1] for alias in node.names
                               if alias.name.startswith('outcome_poc.'))
    assert 'scoring' not in visited


def test_runtime_denied_gold_access_still_loads_documents_and_tasks(tmp_path, raw_hotpot, monkeypatch):
    output, _ = prepare_rows(tmp_path, [raw_hotpot])
    original_open, original_io_open = builtins.open, io.open
    def guarded(function):
        def access(file, *args, **kwargs):
            if isinstance(file, (str, Path)) and 'gold' in Path(file).parts:
                raise PermissionError('gold access denied')
            return function(file, *args, **kwargs)
        return access
    monkeypatch.setattr(builtins, 'open', guarded(original_open))
    monkeypatch.setattr(io, 'open', guarded(original_io_open))
    monkeypatch.setattr(os, 'open', guarded(os.open))
    runtime = importlib.import_module('outcome_poc.data_runtime')
    task = runtime.load_tasks(output / 'tasks.jsonl', 'pilot')[0]
    assert runtime.DocumentStore(output / 'documents.jsonl').get(task.candidate_ids[0]).sentences[1] == 'Lantern 0 glows.'
    with pytest.raises(PermissionError):
        (output / 'gold' / 'gold.jsonl').open()
    assert {field.name for field in fields(Task)} == {'task_id', 'split', 'question', 'candidate_ids'}
    assert {field.name for field in fields(Document)} == {'doc_id', 'title', 'sentences', 'character_count'}


def test_actual_serving_import_closure_in_fresh_process():
    script = '''
import importlib, importlib.util, json, sys
for name in ('runner', 'generation', 'retrieval', 'features', 'policies', 'data_runtime'):
    module = 'outcome_poc.' + name
    if importlib.util.find_spec(module) is not None:
        importlib.import_module(module)
print(json.dumps(sorted(name for name in sys.modules if name.startswith('outcome_poc.'))))
'''
    result = subprocess.run([sys.executable, '-c', script], text=True,
                            capture_output=True, check=True)
    imported = json.loads(result.stdout)
    assert 'outcome_poc.scoring' not in imported
    assert 'outcome_poc.data' not in imported


def test_ranking_and_indexing_work_with_all_gold_file_access_denied(tmp_path, monkeypatch):
    from outcome_poc.retrieval import build_index, Retrieval
    from retrieval_helpers import Encoder, document, store
    doc = document('Invented lantern', ['A violet lamp glows.'])
    documents = store(tmp_path, [doc])
    def guard(function):
        def access(file, *args, **kwargs):
            if isinstance(file, (str, Path)) and 'gold' in Path(file).parts:
                raise PermissionError('gold access denied')
            return function(file, *args, **kwargs)
        return access
    monkeypatch.setattr(builtins, 'open', guard(builtins.open))
    monkeypatch.setattr(io, 'open', guard(io.open))
    monkeypatch.setattr(os, 'open', guard(os.open))
    encoder = Encoder()
    build_index([doc], encoder, tmp_path / 'index')
    ranker = Retrieval(tmp_path / 'index', documents, encoder)
    assert ranker.rank('Which lamp glows?', [doc.doc_id])[0].doc_id == doc.doc_id
    assert ranker.documents.get(doc.doc_id).sentences == ['A violet lamp glows.']
    with pytest.raises(PermissionError):
        (tmp_path / 'gold/gold.jsonl').open()


def test_failed_offline_attempt_persists_costs_with_gold_file_access_denied(tmp_path, monkeypatch):
    from outcome_poc.retrieval import build_index
    from outcome_poc.storage import read_jsonl
    from retrieval_helpers import Encoder, document
    def guard(function):
        def access(file, *args, **kwargs):
            if isinstance(file, (str, Path)) and 'gold' in Path(file).parts:
                raise PermissionError('gold access denied')
            return function(file, *args, **kwargs)
        return access
    monkeypatch.setattr(builtins, 'open', guard(builtins.open))
    monkeypatch.setattr(io, 'open', guard(io.open))
    monkeypatch.setattr(os, 'open', guard(os.open))
    encoder = Encoder()
    def broken(texts):
        raise RuntimeError('injected offline failure')
    monkeypatch.setattr(encoder, 'encode', broken)
    with pytest.raises(RuntimeError):
        build_index([document('Invented lamp', ['A lamp glows.'])], encoder, tmp_path / 'index')
    attempt = list(read_jsonl(tmp_path / 'index-attempts.jsonl'))[-1]
    assert attempt['status'] == 'failed'
    assert attempt['terminal_stage'] == 'encoding'
    assert attempt['elapsed_seconds'] > 0


def test_physically_committed_index_survives_post_commit_telemetry_fault_with_gold_denied(tmp_path, monkeypatch, caplog):
    from pathlib import Path
    from outcome_poc import retrieval
    from retrieval_helpers import Encoder, document, store
    doc = document('Invented lamp', ['A lamp glows.'])
    documents = store(tmp_path, [doc])
    def guard(function):
        def access(file, *args, **kwargs):
            if isinstance(file, (str, Path)) and 'gold' in Path(file).parts:
                raise PermissionError('gold access denied')
            return function(file, *args, **kwargs)
        return access
    monkeypatch.setattr(builtins, 'open', guard(builtins.open))
    monkeypatch.setattr(io, 'open', guard(io.open))
    monkeypatch.setattr(os, 'open', guard(os.open))
    original = retrieval.append_jsonl
    wrote = [False]
    def readonly_after_write(path, value):
        if wrote[0]:
            raise PermissionError('telemetry retry denied')
        original(path, value)
        wrote[0] = True
        raise OSError('post-commit telemetry fault')
    monkeypatch.setattr(retrieval, 'append_jsonl', readonly_after_write)
    original_unlink = Path.unlink
    def deny_revoke(path, *args, **kwargs):
        if path == tmp_path / 'index/manifest.json':
            raise PermissionError('revocation denied')
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', deny_revoke)
    encoder = Encoder()
    retrieval.build_index([doc], encoder, tmp_path / 'index')
    assert retrieval.Retrieval(tmp_path / 'index', documents, encoder).rank('Which lamp?', [doc.doc_id])[0].doc_id == doc.doc_id
    assert 'post-commit' in caplog.text

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

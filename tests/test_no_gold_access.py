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


def test_serving_import_closure_has_no_scorer_or_preparation_module(tmp_path):
    from importlib.util import resolve_name

    def closure(root, entries):
        package_name = root.name
        pending = []
        visited = set()

        def location(name):
            path = root.parent.joinpath(*name.split('.'))
            initializer = path / '__init__.py'
            if initializer.is_file(): return initializer
            if path.with_suffix('.py').is_file(): return path.with_suffix('.py')
            if path.is_dir(): return None  # Namespace package; inspect its local descendants.
            raise AssertionError(f'project import does not resolve: {name}')

        def enqueue(name):
            if name != package_name and not name.startswith(package_name + '.'):
                return
            # Importing a submodule executes every package initializer on its path.
            parts = name.split('.')
            for count in range(1, len(parts) + 1):
                parent = '.'.join(parts[:count])
                location(parent)
                pending.append(parent)

        for name in entries:
            enqueue(package_name + '.' + name)
        while pending:
            name = pending.pop()
            if name in visited: continue
            visited.add(name)
            assert not any(part in {'scoring', 'data'} or part.startswith('preparation')
                           for part in name.split('.')[1:]), f'serving imported {name}'
            path = location(name)
            if path is None: continue
            package = name if path.name == '__init__.py' else name.rpartition('.')[0]
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom):
                    imported = node.module or ''
                    if node.level:
                        imported = resolve_name('.' * node.level + imported, package)
                    enqueue(imported)
                    # A from-import may refer to a package's submodule or an
                    # exported attribute. Follow every locally resolvable submodule.
                    if imported == package_name or imported.startswith(package_name + '.'):
                        for alias in node.names:
                            if alias.name == '*': continue
                            candidate = imported + '.' + alias.name
                            candidate_path = root.parent.joinpath(*candidate.split('.'))
                            if candidate_path.with_suffix('.py').is_file() or candidate_path.is_dir():
                                enqueue(candidate)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        enqueue(alias.name)
        return visited

    authored = tmp_path / 'authored_pkg'
    graph = {
        '__init__.py': 'from . import exports\n',
        'exports.py': '',
        'entry.py': 'from .nested.clock import tick\nfrom .nested import local\nimport authored_pkg.other.deep\n',
        'nested/__init__.py': 'from . import init_dependency\n',
        'nested/clock.py': 'from .. import storage\nfrom ..other import deep\n',
        'nested/local.py': 'from . import clock\n',
        'nested/init_dependency.py': 'from ..storage import constant\n',
        'storage.py': 'constant = 1\n',
        'other/__init__.py': '',
        'other/deep.py': 'from .. import exports\n',
    }
    for name, source in graph.items():
        path = authored / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    assert closure(authored, ['entry']) == {
        'authored_pkg' + ('.' + name.replace('/', '.').removesuffix('.py').removesuffix('.__init__')
                          if name != '__init__.py' else '')
        for name in graph
    }
    for forbidden in ('scoring', 'data', 'preparation'):
        (authored / 'nested' / (forbidden + '.py')).write_text('')
        (authored / 'nested/__init__.py').write_text(f'from . import {forbidden}\n')
        with pytest.raises(AssertionError, match=f'serving imported .*{forbidden}'):
            closure(authored, ['entry'])

    root = Path(__file__).parents[1] / 'src' / 'outcome_poc'
    visited = closure(root, ['collection', 'pilot', 'runner', 'generation', 'retrieval',
                             'features', 'policies', 'data_runtime'])
    assert 'outcome_poc.followup.clock' in visited


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


def test_reader_answer_operates_with_gold_denied(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from outcome_poc.generation import Reader, render_prompt, prompt_identity
    from outcome_poc.schemas import GenerationRequest, ReaderResult
    from retrieval_helpers import document
    from test_prompt import Tokenizer
    def guard(function):
        def access(file, *args, **kwargs):
            if isinstance(file, (str, Path)) and 'gold' in Path(file).parts:
                raise PermissionError('gold access denied')
            return function(file, *args, **kwargs)
        return access
    monkeypatch.setattr(builtins, 'open', guard(builtins.open))
    monkeypatch.setattr(io, 'open', guard(io.open))
    monkeypatch.setattr(os, 'open', guard(os.open))
    doc, tokenizer = document('Invented lamp', ['A blue lamp.']), Tokenizer()
    aliases = {'D0': doc.doc_id}
    prompt = render_prompt('Color?', [doc], aliases, tokenizer)
    request = GenerationRequest('r', 'h', prompt_identity(prompt, tokenizer), 'd', 'answer', 8192, 256, 120., 'none')
    backend = SimpleNamespace(tokenizer=tokenizer, generate=lambda *args, **kwargs:
        ReaderResult('{"answer":"blue","citations":[{"doc_id":"D0","sentence_index":0}]}',
                     None, [], 'ok', 12, 8, [1]*12, [2]*8, 'stop'))
    assert Reader(backend).answer('Color?', [doc], aliases, request).status == 'ok'
    with pytest.raises(PermissionError):
        (tmp_path / 'gold/gold.jsonl').open()


def test_actual_serving_import_closure_in_fresh_process():
    script = '''
import importlib, importlib.util, json, sys
for name in ('collection', 'pilot', 'runner', 'generation', 'retrieval', 'features', 'policies', 'data_runtime'):
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


def test_observable_features_and_policies_work_when_all_file_opens_are_denied(monkeypatch):
    import numpy as np
    from outcome_poc.features import build_features
    from outcome_poc.policies import FixedPolicy, AdaptiveKPolicy, ThresholdPolicy
    from test_features import packet
    def denied(*args, **kwargs):
        raise PermissionError('all file access denied')
    monkeypatch.setattr(builtins, 'open', denied)
    monkeypatch.setattr(io, 'open', denied)
    monkeypatch.setattr(os, 'open', denied)
    class Model:
        def predict(self, values):
            return np.array([0.])
    ranked = packet()
    assert build_features('Who glows?', ranked).shape == (42,)
    for policy in [FixedPolicy(2), AdaptiveKPolicy(0),
                   ThresholdPolicy(Model(), {'threshold_mode': 'numeric', 'threshold': 0})]:
        assert policy.choose('Who glows?', ranked).effective_budget > 0


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


def test_full_serving_closure_operates_with_gold_denied(tmp_path,monkeypatch):
    from outcome_poc.runner import execute_job,close_run,validate_closed_accounting
    from serving_helpers import fixture_runtime
    runtime,job,_=fixture_runtime(tmp_path)
    def guarded(function):
        def access(file,*args,**kwargs):
            if isinstance(file,(str,Path)) and 'gold' in Path(file).parts:
                raise PermissionError('gold access denied')
            return function(file,*args,**kwargs)
        return access
    monkeypatch.setattr(builtins,'open',guarded(builtins.open))
    monkeypatch.setattr(io,'open',guarded(io.open))
    monkeypatch.setattr(os,'open',guarded(os.open))
    prediction=execute_job(job,runtime,tmp_path)
    assert close_run(tmp_path,[job])['record_count']==1
    validate_closed_accounting(tmp_path,[prediction])
    with pytest.raises(PermissionError): (tmp_path/'gold/gold.jsonl').read_bytes()


def test_missing_accounting_fails_before_scorer_opens_gold(tmp_path,monkeypatch):
    from outcome_poc import runner,scoring
    from serving_helpers import fixture_runtime
    from types import SimpleNamespace
    runtime,job,_=fixture_runtime(tmp_path)
    runner.execute_job(job,runtime,tmp_path)
    runner.close_run(tmp_path,[job])
    (tmp_path/'jobs/job/attempt-1/events.jsonl').unlink()
    accessed=[]
    original=scoring.read_jsonl
    def read(path):
        if path.name=='gold.jsonl': accessed.append(path)
        return original(path)
    monkeypatch.setattr(scoring,'read_jsonl',read)
    with pytest.raises((ValueError,FileNotFoundError)):
        scoring.main(SimpleNamespace(predictions=str(tmp_path/'predictions.jsonl'),
            gold=str(tmp_path/'gold.jsonl'),documents='missing',output='missing',run_dir=str(tmp_path)))
    assert accessed==[]

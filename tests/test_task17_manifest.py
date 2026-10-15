"""A03 writer contracts using only synthetic protocol/index metadata and bytes."""
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from outcome_poc import protocol as p
from outcome_poc.schemas import Task
from outcome_poc.storage import atomic_json, canonical_bytes, content_hash
from test_protocol import inputs


REPO = Path(__file__).resolve().parents[1]
WRITER = REPO / 'tools/task17_manifest.py'
CONFIG = 'configs/task17-timing-replication.json'
AMENDMENT = 'docs/amendments/A03-timing-replication.json'


def api():
    assert WRITER.is_file(), 'Task 17 manifest writer is not implemented'
    spec = importlib.util.spec_from_file_location('task17_manifest', WRITER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_writer_is_available():
    assert callable(api().write_replication)


@pytest.fixture
def case(tmp_path, monkeypatch, request):
    writer = api()
    config = json.loads((REPO / CONFIG).read_text())
    amendment = (REPO / AMENDMENT).read_bytes()
    original_names = p.execution_source_files()
    monkeypatch.chdir(tmp_path)
    for name in original_names:
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('synthetic frozen source ' + name).encode())
    for name in writer.SOURCE_EXTRAS:
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(amendment if name == AMENDMENT else b'synthetic committed extra')
    c = inputs(tmp_path)
    shared_container = getattr(request, 'param', 'dedicated') == 'shared'
    if shared_container:
        c['output_dir'] = str(tmp_path / 'artifacts')
        c['run_dir'] = str(tmp_path / 'artifacts/runs/confirmation')
        artifact = tmp_path / 'artifacts/models/model.bin'
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b'synthetic original bound artifact')
        c['artifact_files'] = [str(artifact)]
    c.update(n=480, population_ids=[str(i) for i in range(7344)],
             tasks=[Task(str(i), 'protected', 'Synthetic question?',
                         [f'doc-{j}' for j in range(10)]) for i in range(7344)],
             source_files=original_names,
             deadline_utc='2026-10-15T12:12:52+00:00')
    c['development']['forecast']['available_seconds'] = 1e9
    index = tmp_path / 'shared-index'
    index.mkdir()
    c['development']['retrieval'].update(index_dir=str(index), reuse_indexes=[],
        operational_realization_path=str(Path(c['run_dir']) / 'index-realization.json'))
    parent = p.freeze(c)
    parent['fixture'] = False
    parent['protocol_hash'] = p._hash_protocol(parent)
    parent_path = Path(c['output_dir']) / 'protocol.json'
    atomic_json(parent_path, parent)
    # Intentionally noncanonical JSON: canonical equality alone must not suffice.
    sample_path = Path(c['output_dir']) / 'sample.json'
    sample_path.write_text(json.dumps(parent['sample'], indent=1) + '\n')
    payloads = {}
    for name in ('metadata.sqlite3', 'vectors.f32'):
        path = index / name
        path.write_bytes(b'synthetic index payload')
        payloads[name] = {'sha256': p.file_hash(path), 'bytes': path.stat().st_size}
    ledger = tmp_path / 'index-attempts.jsonl'
    manifest = {'format_version': 2, 'encoder': {'dimensions': 384},
        'document_count': 10, 'window_count': 10,
        'document_ids_digest': 'a' * 64, 'files': payloads,
        'query_convention': {}, 'offline': {}, 'reuse_sources': [],
        'completion': {'status': 'complete', 'scope': 'selected_documents',
                       'attempt_id': 'original-physical-index-attempt',
                       'attempt_ledger': str(ledger)}}
    atomic_json(index / 'manifest.json', manifest)
    ledger.write_bytes(canonical_bytes({'attempt_id': manifest['completion']['attempt_id'],
        'status': 'ok', 'manifest_hash': content_hash(manifest)}) + b'\n')
    selected = Path(c['run_dir']) / 'selected-documents.jsonl'
    selected.parent.mkdir(parents=True)
    selected.write_bytes(b'synthetic selected document projection\n')
    files = {str(path): p.file_hash(path) for path in
             [selected, index / 'manifest.json', ledger, *(index / n for n in payloads)]}
    seal = {'protocol_hash': parent['protocol_hash'], 'scientific_digests': parent['digests'],
        'algorithm': parent['methods']['retrieval'],
        'document_ids_hash': parent['sample']['document_ids_hash'],
        'manifest_hash': content_hash(manifest), 'files': files,
        'reused_physical_sources': [],
        'new_physical_source_id': 'index-attempt:original-physical-index-attempt'}
    seal_path = Path(parent['methods']['retrieval']['operational_realization_path'])
    atomic_json(seal_path, seal)
    config.update(expected_parent_protocol_hash=parent['protocol_hash'],
                  output_dir=str(tmp_path / ('artifacts/protocol-task17-timing' if shared_container else 'replication-protocol')),
                  run_dir=str(tmp_path / ('artifacts/runs/task17-timing-replication' if shared_container else 'replication-run')))
    amendment_value = json.loads(amendment)
    amendment_value['parent_protocol_hash'] = parent['protocol_hash']
    atomic_json(Path(AMENDMENT), amendment_value)
    committed = {name: Path(name).read_bytes()
                 for name in p.execution_source_files(writer.SOURCE_EXTRAS)}

    def git(command, **kwargs):
        if command == ['git', 'rev-parse', 'HEAD']:
            return 'b' * 40 + '\n'
        assert command[:2] == ['git', 'show']
        commit, name = command[2].split(':', 1)
        assert commit == 'b' * 40
        return committed[name]

    monkeypatch.setattr(p.subprocess, 'check_output', git)
    return writer, parent_path, parent, config, seal_path, committed


@pytest.mark.parametrize('case', ['dedicated', 'shared'], indirect=True)
def test_preserves_sample_bytes_settings_and_exact_seven_job_schedule(case):
    writer, parent_path, parent, config, seal_path, _ = case
    original_bytes = {path: path.read_bytes() for root in
        (Path(parent['output_dir']), Path(parent['run_dir']), Path(parent['methods']['retrieval']['index_dir']))
        for path in root.rglob('*') if path.is_file()}
    new = writer.write_replication(parent_path, config)
    assert p.verify_protocol(Path(new['output_dir']) / 'protocol.json') == new
    assert new['sample'] == parent['sample']
    assert new['digests']['sample'] == parent['digests']['sample']
    assert (Path(new['output_dir']) / 'sample.json').read_bytes() == original_bytes[parent_path.with_name('sample.json')]
    restored = copy.deepcopy(new['methods'])
    assert restored['representatives'] == []
    assert restored['deadline_utc'] == '2026-10-15T10:12:52+00:00'
    assert restored['retrieval']['operational_realization_path'] == str(Path(config['run_dir']) / 'index-realization.json')
    restored['representatives'] = parent['methods']['representatives']
    restored['deadline_utc'] = parent['methods']['deadline_utc']
    restored['retrieval']['operational_realization_path'] = parent['methods']['retrieval']['operational_realization_path']
    assert restored == parent['methods']
    jobs = new['schedule']['jobs']
    assert len(jobs) == 3360
    assert Counter(j['scope'] for j in jobs) == {'primary': 1920, 'anchor': 480, 'random': 480, 'oracle-source': 480}
    assert set(Counter(j['task_id'] for j in jobs).values()) == {7}
    assert new['schedule']['assigned_task_ids'] == parent['sample']['task_ids']
    assert all(j['mode'] == 'direct' and j['cache_mode'] == 'none' for j in jobs)
    old_retained = [j for j in parent['schedule']['jobs'] if j['scope'] != 'representative']
    assert jobs == old_retained  # Preserves original question/pair order and job IDs.
    assert (new['methods']['n'], new['methods']['N']) == (480, 7344)
    assert all(new['source']['sha256'][name] == digest for name, digest in parent['source']['sha256'].items())
    assert new['source']['commit'] == 'b' * 40
    assert all(new['artifact_sha256'][name] == digest for name, digest in parent['artifact_sha256'].items())
    assert new['artifact_sha256'][str(seal_path)] == p.file_hash(seal_path)
    provenance = new['replication']
    assert provenance['parent']['source'] == parent['source']
    assert provenance['parent']['protocol_hash'] == parent['protocol_hash']
    assert provenance['parent']['sample_file_sha256'] == p.file_hash(parent_path.with_name('sample.json'))
    assert provenance['shared_index']['physical_source_id'] == 'index-attempt:original-physical-index-attempt'
    assert provenance['shared_index']['owner_protocol_hash'] == parent['protocol_hash']
    assert provenance['shared_index']['charged_as_new_index'] is False
    assert provenance['cost_identity']['local_work_key'] == ['protocol_hash', 'run_dir', 'local_source_or_job_id']
    assert provenance['launch_authorized'] is False
    assert provenance['forecast']['operational_feasibility_established'] is False
    assert provenance['forecast']['original_values'] == parent['methods']['forecast']
    assert all(path.read_bytes() == before for path, before in original_bytes.items())
    assert not Path(config['run_dir']).exists()
    assert new['fixture'] is False and new['source_history'] == []


@pytest.mark.parametrize('case', ['shared'], indirect=True)
@pytest.mark.parametrize('collision', ['original-run', 'original-run-child', 'index-child',
    'scientific-child', 'source-child', 'artifact-child', 'artifact-ancestor',
    'original-output-ancestor', 'new-roots-nested'])
def test_shared_container_still_protects_original_files_and_exclusive_roots(case, collision):
    writer, parent_path, parent, config, _, _ = case
    if collision == 'original-run': target = Path(parent['run_dir'])
    elif collision == 'original-run-child': target = Path(parent['run_dir']) / 'new'
    elif collision == 'index-child': target = Path(parent['methods']['retrieval']['index_dir']) / 'new'
    elif collision == 'scientific-child': target = parent_path.with_name('sample.json') / 'new'
    elif collision == 'source-child': target = Path(next(iter(parent['source']['sha256']))) / 'new'
    elif collision == 'artifact-child': target = Path(next(iter(parent['artifact_sha256']))) / 'new'
    elif collision == 'artifact-ancestor': target = Path(next(iter(parent['artifact_sha256']))).parent
    elif collision == 'original-output-ancestor': target = Path(parent['output_dir']).parent
    else:
        target = Path(config['output_dir'])
        config['run_dir'] = str(target / 'nested-run')
    config['output_dir'] = str(target)
    originals = {Path(name): Path(name).read_bytes() for name in
        [*parent['source']['sha256'], *parent['artifact_sha256'],
         *(str(parent_path.with_name(name)) for name in ('protocol.json', 'methods.json', 'sample.json', 'schedule.json'))]}
    with pytest.raises(ValueError, match='path|root|exist|overlap|protected'):
        writer.write_replication(parent_path, config)
    assert all(path.read_bytes() == payload for path, payload in originals.items())
    assert not Path(config['run_dir']).exists()


def test_rejects_existing_output_without_overwriting_or_resuming(case):
    writer, parent_path, _, config, _, _ = case
    writer.write_replication(parent_path, config)
    path = Path(config['output_dir']) / 'sample.json'
    before = path.read_bytes()
    with pytest.raises(ValueError, match='exist'):
        writer.write_replication(parent_path, config)
    assert path.read_bytes() == before


@pytest.mark.parametrize('kind', ['parent-output', 'parent-run-child', 'new-roots-nested',
    'symlink', 'dangling-symlink', 'existing-output', 'existing-run'])
def test_rejects_colliding_roots_before_writing(case, kind):
    writer, parent_path, parent, config, _, _ = case
    if kind == 'parent-output': config['output_dir'] = parent['output_dir']
    elif kind == 'parent-run-child': config['output_dir'] = str(Path(parent['run_dir']) / 'child')
    elif kind == 'new-roots-nested': config['run_dir'] = str(Path(config['output_dir']) / 'child')
    elif kind == 'symlink': Path(config['output_dir']).symlink_to(parent['run_dir'], target_is_directory=True)
    elif kind == 'dangling-symlink': Path(config['output_dir']).symlink_to('missing-target', target_is_directory=True)
    else: Path(config['output_dir'] if kind == 'existing-output' else config['run_dir']).mkdir()
    with pytest.raises(ValueError, match='path|root|exist|overlap'):
        writer.write_replication(parent_path, config)
    assert not (Path(config['output_dir']) / 'protocol.json').exists() or kind == 'parent-output'


@pytest.mark.parametrize('kind', ['parent-hash', 'fixture', 'denominator', 'repetitions',
    'source', 'uncommitted-extra', 'missing-extra', 'artifact', 'index-payload',
    'index-identity', 'index-digests', 'sample', 'deadline', 'amendment-parent'])
def test_rejects_changed_bindings_before_any_output(case, kind):
    writer, parent_path, parent, config, seal_path, _ = case
    if kind == 'parent-hash': config['expected_parent_protocol_hash'] = 'f' * 64
    elif kind == 'source': Path(next(iter(parent['source']['sha256']))).write_bytes(b'changed')
    elif kind == 'uncommitted-extra': Path('tools/task17_manifest.py').write_bytes(b'changed')
    elif kind == 'missing-extra': Path('tools/task17_manifest.py').unlink()
    elif kind == 'artifact': Path(next(iter(parent['artifact_sha256']))).write_bytes(b'changed')
    elif kind == 'index-payload': (Path(parent['methods']['retrieval']['index_dir']) / 'vectors.f32').write_bytes(b'changed')
    elif kind in ('index-identity', 'index-digests'):
        seal = json.loads(seal_path.read_text())
        seal['new_physical_source_id' if kind == 'index-identity' else 'scientific_digests'] = 'changed'
        atomic_json(seal_path, seal)
    elif kind == 'sample': parent_path.with_name('sample.json').write_text('{}')
    elif kind == 'amendment-parent':
        amendment = json.loads(Path(AMENDMENT).read_text())
        amendment['parent_protocol_hash'] = 'f' * 64
        atomic_json(Path(AMENDMENT), amendment)
        case[-1][AMENDMENT] = Path(AMENDMENT).read_bytes()
    else:
        if kind == 'fixture': parent['fixture'] = True
        elif kind == 'denominator': parent['sample']['N'] = parent['methods']['N'] = 7345
        elif kind == 'repetitions': parent['methods']['repetitions'] = 3
        elif kind == 'deadline': parent['methods']['deadline_utc'] = '2099-01-01T00:00:00+00:00'
        parent['schedule']['jobs'] = p.plan_jobs(parent['methods'], parent['sample']['tasks'])
        for key in ('methods', 'sample', 'schedule'):
            parent['digests'][key] = content_hash(parent[key])
            atomic_json(parent_path.with_name(key + '.json'), parent[key])
        parent['protocol_hash'] = p._hash_protocol(parent)
        atomic_json(parent_path, parent)
        config['expected_parent_protocol_hash'] = parent['protocol_hash']
    with pytest.raises((ValueError, FileNotFoundError)):
        writer.write_replication(parent_path, config)
    assert not Path(config['output_dir']).exists()


def test_no_resampling_or_unbound_reads_and_partial_write_is_retained(case, monkeypatch):
    writer, parent_path, parent, config, seal_path, _ = case

    def forbidden(*args, **kwargs):
        raise AssertionError('forbidden new sampling/freezing/runtime work')

    for name in ('freeze', 'freeze_methods', 'sample_protected', 'plan'):
        monkeypatch.setattr(p, name, forbidden)
    allowed = {Path(name).resolve() for name in
        [*parent['source']['sha256'], *parent['artifact_sha256'], *writer.SOURCE_EXTRAS,
         *json.loads(seal_path.read_text())['files'], str(seal_path),
         *(str(parent_path.with_name(name)) for name in ('protocol.json', 'sample.json', 'methods.json', 'schedule.json'))]}
    output = Path(config['output_dir']).resolve()
    original_open = Path.open

    def bound_open(path, mode='r', *args, **kwargs):
        if 'r' in mode and path.resolve() not in allowed and not path.resolve().is_relative_to(output):
            raise AssertionError('unbound read: ' + str(path))
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', bound_open)
    original_write = writer.atomic_json

    def interrupt(path, value):
        if path.name == 'schedule.json': raise KeyboardInterrupt('synthetic interrupted write')
        return original_write(path, value)

    monkeypatch.setattr(writer, 'atomic_json', interrupt)
    with pytest.raises(KeyboardInterrupt): writer.write_replication(parent_path, config)
    assert output.is_dir()
    monkeypatch.setattr(writer, 'atomic_json', original_write)
    with pytest.raises(ValueError, match='exist'): writer.write_replication(parent_path, config)

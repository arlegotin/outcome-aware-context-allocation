import json
import sqlite3
import numpy as np
import pytest
from outcome_poc import retrieval
from retrieval_helpers import Encoder, document


def test_index_deduplicates_and_persists_original_mapping_with_float32_vectors(tmp_path):
    doc = document('Title', ['one', 'two'])
    encoder = Encoder()
    manifest = retrieval.build_index(iter([doc, doc]), encoder, tmp_path / 'index')
    assert manifest['document_count'] == 1
    assert manifest['window_count'] == 1
    assert manifest['encoder']['revision'] == 'fixture'
    assert manifest['encoder']['dimensions'] == 384
    assert manifest['offline']['vector_bytes'] == 1536
    assert manifest['offline']['seconds'] >= 0
    assert manifest['query_convention']['prefix'] == 'Represent this sentence for searching relevant passages: '
    vectors = np.memmap(tmp_path / 'index/vectors.f32', dtype=np.float32, mode='r', shape=(1, 384))
    assert np.isfinite(vectors).all()
    assert float(np.linalg.norm(vectors[0])) == 1
    with sqlite3.connect(tmp_path / 'index/metadata.sqlite3') as db:
        assert db.execute('SELECT character_count, sentence_count FROM documents').fetchone() == (11, 2)
        offset, spans = db.execute('SELECT vector_offset, spans FROM windows').fetchone()
        assert offset == 0
        assert [s['sentence_index'] for s in json.loads(spans)] == [0, 1]
    assert encoder.texts == ['Title\none\ntwo']


def test_index_refuses_overwrite_and_corrupt_document_hash(tmp_path):
    doc = document('Title', ['one'])
    retrieval.build_index([doc], Encoder(), tmp_path / 'index')
    with pytest.raises(ValueError, match='exist'):
        retrieval.build_index([doc], Encoder(), tmp_path / 'index')
    from dataclasses import replace
    with pytest.raises(ValueError, match='hash'):
        retrieval.build_index([replace(doc, doc_id='bad')], Encoder(), tmp_path / 'bad')


def test_unindexable_title_writes_error_ledger_without_publishing_manifest(tmp_path):
    doc = document(' '.join(['title'] * 478), ['body'])
    with pytest.raises(ValueError, match='title'):
        retrieval.build_index([doc], Encoder(), tmp_path / 'index')
    assert not (tmp_path / 'index/manifest.json').exists()
    error = json.loads((tmp_path / 'index/errors.json').read_text())
    assert error['doc_id'] == doc.doc_id
    assert error['stage'] == 'windows'


def test_index_cli_requires_config_and_active_split_and_has_no_gold_option():
    import subprocess, sys
    result = subprocess.run([sys.executable, '-m', 'outcome_poc', 'index', '--help'], text=True, capture_output=True)
    assert result.returncode == 0
    assert '--config' in result.stdout
    assert '--split' in result.stdout
    assert '--gold' not in result.stdout


@pytest.fixture
def cli_index_fixture(tmp_path, monkeypatch):
    from outcome_poc.__main__ import main
    from outcome_poc.assets import file_identity
    from outcome_poc.schemas import Task
    from outcome_poc.storage import canonical_bytes, content_hash
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    active = [document(f'Active {i}', [f'Pilot sentence {i}']) for i in range(10)]
    reserve = [document(f'Reserve {i}', [f'Reserved sentence {i}']) for i in range(10)]
    (prepared / 'documents.jsonl').write_bytes(b''.join(canonical_bytes(d) + b'\n' for d in active + reserve))
    tasks = [Task('active', 'pilot', 'Active question', [d.doc_id for d in active]),
             Task('reserve', 'pilot_reservation', 'Reserve question', [d.doc_id for d in reserve]),
             Task('fit', 'fit', 'Fit question', [d.doc_id for d in reserve]),
             Task('unsampled-protected-a', 'protected', 'Protected question A', [d.doc_id for d in reserve]),
             Task('unsampled-protected-b', 'protected', 'Protected question B', [d.doc_id for d in reserve])]
    (prepared / 'tasks.jsonl').write_bytes(b''.join(canonical_bytes(t) + b'\n' for t in tasks))
    snapshot = tmp_path / ('b' * 40)
    snapshot.mkdir()
    (snapshot / 'LICENSE').write_text('MIT invented fixture')
    files = {'LICENSE': file_identity(snapshot / 'LICENSE')}
    asset = {'repo_id': 'BAAI/bge-small-en-v1.5', 'revision': 'b' * 40, 'kind': 'model',
             'status': 'ok', 'license': 'mit', 'local_path': str(snapshot),
             'files': files, 'snapshot_hash': content_hash(files)}
    asset_path = tmp_path / 'assets.json'
    asset_path.write_text(json.dumps({'assets': {'encoder': asset}}))
    config = {'preparation': {'output_dir': str(prepared), 'asset_manifest': str(asset_path)},
              'retrieval': {'output_dir': str(tmp_path / 'indexes')}, 'output_dir': str(tmp_path / 'provenance'),
              'encoder': {'repo_id': asset['repo_id'], 'revision': asset['revision'], 'dimensions': 384,
                          'device': 'cpu', 'precision': 'float32'}}
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(config))
    encoder = Encoder()
    encoder.identity = {'revision': asset['revision'], 'snapshot_hash': asset['snapshot_hash']}
    monkeypatch.setattr(retrieval, 'EncoderBackend', lambda path: encoder)
    return config_path, encoder, active


def test_index_cli_embeds_only_active_pilot_candidates_and_records_provenance(tmp_path, cli_index_fixture):
    from outcome_poc.__main__ import main
    from outcome_poc.storage import content_hash
    config_path, encoder, active = cli_index_fixture
    assert main(['index', '--config', str(config_path), '--split', 'pilot']) == 0
    manifest = json.loads((tmp_path / 'indexes/pilot/manifest.json').read_text())
    assert manifest['scheduled_task_count'] == 1
    assert manifest['document_count'] == 10
    assert len(encoder.texts) == 10
    assert all(text.startswith('Active ') for text in encoder.texts)
    assert manifest['scheduled_task_ids_hash'] == content_hash(['active'])
    assert manifest['offline']['network_attempts'] == 0
    assert manifest['offline']['model_load_seconds'] >= 0
    assert manifest['offline']['setup_seconds'] >= manifest['offline']['model_load_seconds']
    attempt = list(retrieval.read_jsonl(tmp_path / 'provenance/index-attempts.jsonl'))[-1]
    assert attempt['status'] == 'ok'
    assert attempt['elapsed_seconds'] >= manifest['offline']['seconds'] + manifest['offline']['setup_seconds']
    assert attempt['manifest_hash'] == content_hash(manifest)
    assert manifest == json.loads((tmp_path / 'provenance/wp1-index-pilot.json').read_text())
    assert set(attempt['excluded_after_boundary']) == {'attempt_telemetry_publication', 'console_summary'}
    assert (tmp_path / 'provenance/wp1-index-pilot.json').exists()



def test_protected_dispatch_refuses_unsampled_population_before_encoder_work(cli_index_fixture, monkeypatch):
    from argparse import Namespace
    config_path, encoder, active = cli_index_fixture
    def forbidden(*args):
        pytest.fail('protected dispatch reached encoder work')
    monkeypatch.setattr(retrieval, 'EncoderBackend', forbidden)
    with pytest.raises(ValueError, match='protected'):
        retrieval.main(Namespace(config=str(config_path), split='protected'))


@pytest.mark.parametrize('failure_stage', ['document_validation', 'windows', 'calibration', 'encoding'])
def test_build_failure_retains_structured_elapsed_stage_and_partial_bytes(tmp_path, monkeypatch, failure_stage):
    from dataclasses import replace
    from outcome_poc.storage import read_jsonl
    doc = document('Title', ['body'])
    encoder = Encoder()
    if failure_stage == 'document_validation':
        doc = replace(doc, doc_id='bad')
    elif failure_stage == 'windows':
        doc = document(' '.join(['title'] * 478), ['body'])
    else:
        def broken(*args):
            raise RuntimeError('injected encoder failure')
        monkeypatch.setattr(encoder, 'select_batch_size' if failure_stage == 'calibration' else 'encode', broken, raising=False)
    with pytest.raises((ValueError, RuntimeError)):
        retrieval.build_index([doc], encoder, tmp_path / 'index')
    attempt = list(read_jsonl(tmp_path / 'index-attempts.jsonl'))[-1]
    assert attempt['status'] == 'failed'
    assert attempt['terminal_stage'] == failure_stage
    assert attempt['elapsed_seconds'] > 0
    assert attempt['partial_bytes']['index_total'] > 0
    assert not (tmp_path / 'index/manifest.json').exists()


@pytest.mark.parametrize('failure_stage', ['source_fingerprints', 'provenance_publication', 'manifest_publication'])
def test_cli_finalization_failure_is_chargeable_and_never_completed(tmp_path, cli_index_fixture, monkeypatch, failure_stage):
    from argparse import Namespace
    from outcome_poc.storage import read_jsonl
    config_path, encoder, active = cli_index_fixture
    original_identity, original_atomic = retrieval.file_identity, retrieval.atomic_json
    def fingerprint(path):
        if failure_stage == 'source_fingerprints' and path == tmp_path / 'prepared/tasks.jsonl':
            raise OSError('injected source fingerprint failure')
        return original_identity(path)
    def publication(path, value):
        target = tmp_path / ('provenance/wp1-index-pilot.json' if failure_stage == 'provenance_publication' else 'indexes/pilot/manifest.json')
        if failure_stage != 'source_fingerprints' and path == target:
            # Raise after rename too: acceptance must require the successful attempt.
            original_atomic(path, value)
            raise OSError('injected publication failure after rename')
        return original_atomic(path, value)
    monkeypatch.setattr(retrieval, 'file_identity', fingerprint)
    monkeypatch.setattr(retrieval, 'atomic_json', publication)
    with pytest.raises(OSError):
        retrieval.main(Namespace(config=str(config_path), split='pilot'))
    attempt = list(read_jsonl(tmp_path / 'provenance/index-attempts.jsonl'))[-1]
    assert attempt['status'] == 'failed'
    assert attempt['terminal_stage'] == failure_stage
    assert attempt['elapsed_seconds'] > 0
    assert attempt['partial_bytes']['index_total'] >= 15360
    from outcome_poc.data_runtime import DocumentStore
    with pytest.raises(ValueError, match='complet'):
        retrieval.Retrieval(tmp_path / 'indexes/pilot', DocumentStore(tmp_path / 'prepared/documents.jsonl'), encoder)


def test_full_offline_clock_boundary_includes_required_publications(tmp_path, cli_index_fixture, monkeypatch):
    from argparse import Namespace
    from outcome_poc.storage import read_jsonl
    config_path, encoder, active = cli_index_fixture
    clock = [0.]
    original = retrieval.atomic_json
    def publication(path, value):
        if path.name == 'manifest.json' or path.name == 'wp1-index-pilot.json':
            clock[0] += 7.
        return original(path, value)
    monkeypatch.setattr(retrieval.time, 'perf_counter', lambda: clock[0])
    monkeypatch.setattr(retrieval, 'atomic_json', publication)
    retrieval.main(Namespace(config=str(config_path), split='pilot'))
    attempt = list(read_jsonl(tmp_path / 'provenance/index-attempts.jsonl'))[-1]
    assert attempt['elapsed_seconds'] == 14.
    assert attempt['status'] == 'ok'


def test_attempt_telemetry_failure_after_write_cannot_leave_accepted_completion(tmp_path, monkeypatch):
    from outcome_poc.storage import read_jsonl
    from retrieval_helpers import store
    doc = document('Title', ['body'])
    encoder = Encoder()
    original = retrieval.append_jsonl
    def failing_after_write(path, value):
        original(path, value)
        raise OSError('injected attempt telemetry fsync failure')
    monkeypatch.setattr(retrieval, 'append_jsonl', failing_after_write)
    with pytest.raises(OSError, match='telemetry'):
        retrieval.build_index([doc], encoder, tmp_path / 'index')
    with pytest.raises(ValueError, match='complet'):
        retrieval.Retrieval(tmp_path / 'index', store(tmp_path, [doc]), encoder)
    attempt = list(read_jsonl(tmp_path / 'index-attempts.jsonl'))[-1]
    assert attempt['status'] == 'failed'
    assert sum(attempt['stage_seconds'].values()) == pytest.approx(attempt['elapsed_seconds'], abs=1e-8)


def test_failed_attempt_retains_cost_record_when_partial_byte_snapshot_is_unavailable(tmp_path, monkeypatch):
    from pathlib import Path
    from outcome_poc.storage import read_jsonl
    encoder = Encoder()
    def broken(texts):
        raise RuntimeError('injected encoding failure')
    monkeypatch.setattr(encoder, 'encode', broken)
    original = Path.rglob
    def denied(path, pattern):
        if path == tmp_path / 'index':
            raise OSError('injected byte snapshot access failure')
        return original(path, pattern)
    monkeypatch.setattr(Path, 'rglob', denied)
    with pytest.raises(RuntimeError, match='encoding'):
        retrieval.build_index([document('Title', ['body'])], encoder, tmp_path / 'index')
    attempt = list(read_jsonl(tmp_path / 'index-attempts.jsonl'))[-1]
    assert attempt['status'] == 'failed'
    assert attempt['elapsed_seconds'] > 0
    assert attempt['partial_bytes']['measurement_errors']

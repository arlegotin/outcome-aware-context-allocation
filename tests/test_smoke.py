"""Native adapter safety and numerical contracts, without loading public models."""
import numpy as np
import pytest

from outcome_poc.generation import ReaderBackend, offline_network, smoke
from outcome_poc.retrieval import validate_vectors


def test_finite_384_vectors_are_float32_and_normalized():
    values = np.zeros((1, 384), dtype=np.float32)
    values[0, 0] = 1
    assert validate_vectors(values, 1).shape == (1, 384)


@pytest.mark.parametrize('values', [np.zeros((1, 383)), np.full((1, 384), np.nan), np.zeros((1, 384))])
def test_invalid_encoder_vectors_fail(values):
    with pytest.raises(ValueError):
        validate_vectors(values, 1)


def test_reader_rejects_repository_name_before_loading():
    with pytest.raises(ValueError, match='local'):
        ReaderBackend().load('mlx-community/Qwen3-4B-Instruct-2507-4bit', {})


def test_offline_guard_denies_socket_connection():
    import socket
    with offline_network() as attempts:
        with pytest.raises(RuntimeError, match='offline'):
            socket.create_connection(('huggingface.co', 443), timeout=.01)
    assert attempts


def test_reader_only_success_cannot_pass_data_gate(tmp_path):
    config = {'output_dir': str(tmp_path), 'reader': {}, 'encoder': {}}
    manifest = {'required': ['train', 'reader', 'encoder'], 'assets': {
        'train': {'status': 'blocked', 'error': 'origin timeout'},
        'reader': {'status': 'blocked', 'error': 'not downloaded'},
        'encoder': {'status': 'blocked', 'error': 'not downloaded'}}}
    result = smoke(config, manifest)
    assert result['wp0_passed'] is False
    assert result['status'] == 'blocked by prerequisites'
    assert (tmp_path / 'wp0.json').exists()


def test_smoke_parser_accepts_citation_objects_and_rejects_malformed():
    from outcome_poc.generation import parse_citation_json
    assert parse_citation_json('{"answer":"blue","citations":[{"doc_id":"d0","sentence_index":0}]}') == ('blue', [('d0', 0)], 'ok')
    assert parse_citation_json('{"answer":"blue","citations":[{"doc_id":"d0","sentence_index":true}]}')[2] == 'parse_error'
    assert parse_citation_json('```json\n{}\n```')[2] == 'parse_error'


def test_reader_context_guard_reserves_output_and_checks_identity():
    from outcome_poc.schemas import GenerationRequest
    from outcome_poc.generation import ReaderBackend
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            return [1, 2, 3]
    backend = ReaderBackend()
    backend.tokenizer = Tokenizer()
    backend.identity = {'revision': 'r', 'snapshot_hash': 'h'}
    request = GenerationRequest('r', 'h', 'p', 'd', 'smoke', 4, 2, 1., 'none')
    result = backend.generate('invented', request)
    assert result.status == 'context_overflow'
    assert result.prompt_tokens == 3
    assert result.generated_token_ids == []
    wrong = GenerationRequest('wrong', 'h', 'p', 'd', 'smoke', 4, 2, 1., 'none')
    with pytest.raises(ValueError, match='identity'):
        backend.generate('invented', wrong)


def test_successful_native_characterization_does_not_override_missing_data(tmp_path, monkeypatch, matching_assets):
    import outcome_poc.generation as generation
    def native(config, manifest, result):
        result['reader_encoder_passed'] = True
    monkeypatch.setattr(generation, '_native_smoke', native)
    config, manifest = matching_assets
    config['output_dir'] = str(tmp_path)
    manifest['assets']['dev'] = {'status': 'blocked', 'error': 'author origin timeout'}
    result = generation.smoke(config, manifest)
    assert result['reader_encoder_passed'] is True
    assert result['wp0_passed'] is False
    assert result['status'] == 'blocked by prerequisites'


def test_smoke_rejects_manifest_that_omits_configured_data(tmp_path, monkeypatch):
    import outcome_poc.generation as generation
    from outcome_poc.assets import file_identity
    def native(config, manifest, result):
        result['reader_encoder_passed'] = True
    monkeypatch.setattr(generation, '_native_smoke', native)
    (tmp_path / 'LICENSE').write_text('MIT license')
    entry = {'kind': 'model', 'status': 'ok', 'license': 'mit', 'revision': 'a'*40,
             'local_path': str(tmp_path), 'files': {'LICENSE': file_identity(tmp_path / 'LICENSE')}}
    manifest = {'required': ['reader'], 'assets': {'reader': entry}}
    result = generation.smoke({'output_dir': str(tmp_path), 'reader': {}, 'data': [{'name': 'train'}]}, manifest)
    assert result['wp0_passed'] is False
    assert 'train' in ' '.join(result['errors'])


def test_wp0_artifact_binds_configuration_and_asset_manifest(tmp_path):
    import hashlib
    import json
    config = {'output_dir': str(tmp_path), 'reader': {}, 'asset_source_amendment': 'A01'}
    manifest = {'required': ['train'], 'assets': {'train': {'status': 'blocked', 'error': 'missing'}}}
    result = smoke(config, manifest)
    expected_config = hashlib.sha256(json.dumps(config,ensure_ascii=False,sort_keys=True,separators=(',', ':')).encode()).hexdigest()
    expected_manifest = hashlib.sha256(json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',', ':')).encode()).hexdigest()
    assert result['config_hash'] == expected_config
    assert result['asset_manifest_hash'] == expected_manifest
    assert result['source_amendment'] == 'A01'


@pytest.mark.parametrize('role', ['reader', 'encoder', 'original_reader'])
def test_smoke_rejects_changed_pin_before_native_load(matching_assets, tmp_path, monkeypatch, role):
    import outcome_poc.generation as generation
    config, manifest = matching_assets
    config['output_dir'] = str(tmp_path)
    config[role]['revision'] = 'd'*40
    def native(*args):
        pytest.fail('configuration disagreement reached native load')
    monkeypatch.setattr(generation, '_native_smoke', native)
    result = generation.smoke(config, manifest)
    assert result['asset_gate_passed'] is False
    assert result['wp0_passed'] is False
    assert role in ' '.join(result['errors'])


@pytest.mark.parametrize('field,value', [('asset_source_amendment', None), ('asset_source_amendment', 'A02'),
                                        ('asset_source_policy', None), ('asset_source_policy', 'direct_author_host_only')])
def test_smoke_rejects_archive_permission_change_before_native_load(matching_assets, tmp_path, monkeypatch, field, value):
    import outcome_poc.generation as generation
    config, manifest = matching_assets
    config['output_dir'] = str(tmp_path)
    if value is None:
        config.pop(field)
    else:
        config[field] = value
    def native(*args):
        pytest.fail('unpermitted archive reached native load')
    monkeypatch.setattr(generation, '_native_smoke', native)
    result = generation.smoke(config, manifest)
    assert result['asset_gate_passed'] is False
    assert result['wp0_passed'] is False


def test_matching_configuration_with_blocked_data_can_characterize_native(matching_assets, tmp_path, monkeypatch):
    import outcome_poc.generation as generation
    config, manifest = matching_assets
    config['output_dir'] = str(tmp_path)
    manifest['assets']['dev'] = {'status': 'blocked', 'error': 'origin unavailable'}
    def native(config, manifest, result):
        result['reader_encoder_passed'] = True
    monkeypatch.setattr(generation, '_native_smoke', native)
    result = generation.smoke(config, manifest)
    assert result['reader_encoder_passed'] is True
    assert result['wp0_passed'] is False


def test_smoke_rejects_data_manifest_not_declared_by_current_config(matching_assets, tmp_path, monkeypatch):
    import outcome_poc.generation as generation
    config, manifest = matching_assets
    config['output_dir'] = str(tmp_path)
    config['data'] = []
    def native(*args):
        pytest.fail('unconfigured archived source reached native load')
    monkeypatch.setattr(generation, '_native_smoke', native)
    result = generation.smoke(config, manifest)
    assert result['wp0_passed'] is False
    assert 'dev' in ' '.join(result['errors'])


@pytest.mark.parametrize('field,value', [('capture', '20250512032702'),
                                        ('url', 'https://web.archive.org/web/20250512032702id_/wrong')])
def test_smoke_rejects_data_capture_or_replay_change_before_native_load(matching_assets, tmp_path, monkeypatch, field, value):
    import outcome_poc.generation as generation
    config, manifest = matching_assets
    config['output_dir'] = str(tmp_path)
    config['data'][0]['archive'][field] = value
    def native(*args):
        pytest.fail('source configuration disagreement reached native load')
    monkeypatch.setattr(generation, '_native_smoke', native)
    result = generation.smoke(config, manifest)
    assert result['asset_gate_passed'] is False
    assert result['wp0_passed'] is False

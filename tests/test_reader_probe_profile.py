"""Authored profile boundaries; no tokenizer assets or model are loaded."""
import copy
import json
import pickle
from pathlib import Path

import pytest

from outcome_poc.reader_probe import profile


CONFIG = Path('configs/reader-capability-preflight.json')


class Tokenizer:
    chat_template = 'authored template'

    def apply_chat_template(self, messages, **kwargs):
        return (messages, kwargs)

    def encode(self, text, **kwargs):
        return [11, 12]


def test_loaded_profile_prescribes_exact_native_settings_and_provenance():
    config = profile.load_config(CONFIG)
    assert config['reader'] == {
        'repo_id': 'mlx-community/Qwen3-14B-4bit',
        'revision': 'a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4',
        'max_context_tokens': 8192, 'max_new_tokens': 256,
        'timeout_seconds': 120, 'prefill_step_size': 512,
        'enable_thinking': False, 'temperature': 0, 'batch_size': 1,
        'cache_mode': 'none', 'kv_cache': 'default', 'result_reuse': False,
        'repairs': 0, 'semantic_retries': 0,
    }
    assert config['startup_timeout_seconds'] == 120
    assert config['original_reader']['repo_id'] == 'Qwen/Qwen3-14B'
    assert config['original_reader']['revision'] == '40c069824f4251a91eefaf281ebe4c544efd3e18'
    assert set(config['inventories']['original_reader']) == {'README.md', 'config.json', 'LICENSE'}
    assert '.gitattributes' not in config['inventories']['reader']
    assert config['conversion_source_revision_known'] is False


@pytest.mark.parametrize('key,value', [
    ('revision', 'b' * 40), ('repo_id', 'another/model'),
    ('enable_thinking', True), ('max_context_tokens', 8193),
    ('max_new_tokens', 257), ('timeout_seconds', 121), ('temperature', .1),
    ('batch_size', 2), ('prefill_step_size', 1024), ('cache_mode', 'prefix'),
    ('kv_cache', 'quantized'), ('result_reuse', True), ('repairs', 1),
    ('semantic_retries', 1),
])
def test_changed_profile_is_rejected_before_native_use(tmp_path, key, value):
    config = json.loads(CONFIG.read_text())
    config['reader'][key] = value
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='profile|pin|setting'):
        profile.load_config(path)


def test_tokenizer_forces_mode_forwards_api_and_roundtrips_pickle():
    original = Tokenizer()
    tokenizer = pickle.loads(pickle.dumps(profile.NonThinkingTokenizer(original)))
    assert tokenizer.apply_chat_template(['authored'], tokenize=False) == (
        ['authored'], {'tokenize': False, 'enable_thinking': False})
    assert tokenizer.apply_chat_template([], enable_thinking=False)[1]['enable_thinking'] is False
    assert tokenizer.encode('hello') == [11, 12]
    assert tokenizer.chat_template == 'authored template'
    assert original.__dict__ == {}
    with pytest.raises(ValueError, match='thinking'):
        tokenizer.apply_chat_template([], enable_thinking=True)
    with pytest.raises(ValueError, match='thinking'):
        tokenizer.apply_chat_template([], enable_thinking=0)


def test_factory_preserves_loaded_identity_and_wraps_only_its_reader(tmp_path, monkeypatch):
    from outcome_poc import generation
    from outcome_poc.assets import file_identity
    from outcome_poc.storage import content_hash
    (tmp_path / 'README.md').write_text('Authored asset')
    files = {'README.md': file_identity(tmp_path / 'README.md')}
    asset = {'kind': 'model', 'status': 'ok', 'license': 'apache-2.0',
             'repo_id': 'mlx-community/Qwen3-14B-4bit',
             'revision': 'a4d9b2df59d2c150bef02fcbe0d91046b7ca33a4',
             'local_path': str(tmp_path), 'files': files, 'snapshot_hash': content_hash(files)}
    settings = {**profile.load_config(CONFIG)['reader'], 'asset': asset}
    before = copy.deepcopy(settings)
    tokenizer = Tokenizer()

    # Native loading is the external boundary; retain the real native factory.
    def load(backend, snapshot, config):
        assert snapshot == tmp_path
        assert config == before
        backend.identity = config['asset']
        backend.settings = config
        backend.tokenizer = tokenizer
    monkeypatch.setattr(generation.ReaderBackend, 'load', load)
    factory = pickle.loads(pickle.dumps(profile.ProfileFactory(tmp_path, settings)))
    backend = factory()
    assert type(backend) is generation.ReaderBackend
    assert backend.identity == asset
    assert backend.settings == before
    assert isinstance(backend.tokenizer, profile.NonThinkingTokenizer)
    assert backend.tokenizer.apply_chat_template([])[1] == {'enable_thinking': False}
    assert tokenizer.__dict__ == {}
    assert settings == before
    assert (tmp_path / 'README.md').read_text() == 'Authored asset'


def test_factory_rejects_override_before_loading(tmp_path, monkeypatch):
    from outcome_poc import generation
    settings = {**profile.load_config(CONFIG)['reader'], 'enable_thinking': True}
    monkeypatch.setattr(generation.ReaderBackend, 'load', lambda *args: pytest.fail('must reject before load'))
    with pytest.raises(ValueError, match='profile|thinking|setting'):
        profile.ProfileFactory(tmp_path, settings)()

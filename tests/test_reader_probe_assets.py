"""Tiny authored, safetensors-named bytes test integrity without model loading."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from outcome_poc.reader_probe import assets
from outcome_poc.storage import content_hash


def pin(payload, lfs=False):
    result = {'size': len(payload), 'blobId': hashlib.sha1(
        b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()}
    if lfs:
        result['lfs'] = {'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)}
    return result


@pytest.fixture
def authored(tmp_path, monkeypatch):
    config = json.loads(Path('configs/reader-capability-preflight.json').read_text())
    payloads = {
        'reader': {'README.md': b'---\nlicense: apache-2.0\nbase_model: Qwen/Qwen3-14B\n---\n',
                   'config.json': b'{"model_type":"qwen3","architectures":["Qwen3ForCausalLM"]}',
                   'tokenizer_config.json': b'{"chat_template":"{% if enable_thinking is defined %}switch{% endif %}"}',
                   'model-00001-of-00002.safetensors': b'authored first shard',
                   'model-00002-of-00002.safetensors': b'authored second shard',
                   'model.safetensors.index.json': b'{"weight_map":{"a":"model-00001-of-00002.safetensors","b":"model-00002-of-00002.safetensors"}}'},
        'original_reader': {'README.md': b'---\nlicense: apache-2.0\n---\n',
                            'LICENSE': b'Apache License\nVersion 2.0, January 2004\n',
                            'config.json': b'{"model_type":"qwen3","architectures":["Qwen3ForCausalLM"]}'},
    }
    config['inventories'] = {role: {name: pin(payload, name.endswith('.safetensors'))
                                  for name, payload in files.items()}
                             for role, files in payloads.items()}
    config['original_license_sha256'] = hashlib.sha256(payloads['original_reader']['LICENSE']).hexdigest()
    calls = []

    def metadata(repo, revision=None):
        calls.append(('metadata', repo))
        return {'revision': revision, 'license': 'apache-2.0',
                'base_model': 'Qwen/Qwen3-14B' if repo.startswith('mlx-community/') else None,
                'source_url': f'https://huggingface.co/{repo}/tree/{revision}'}

    def snapshot(repo, revision, destination, filenames):
        calls.append(('download', repo))
        role = 'reader' if repo.startswith('mlx-community/') else 'original_reader'
        assert set(filenames) == set(payloads[role])
        destination.mkdir(parents=True, exist_ok=True)
        for name, payload in payloads[role].items():
            (destination / name).write_bytes(payload)
        return destination

    monkeypatch.setattr(assets, 'load_config', lambda _: copy.deepcopy(config))
    monkeypatch.setattr(assets, '_hub_metadata', metadata)
    monkeypatch.setattr(assets, '_download_snapshot', snapshot)
    monkeypatch.setattr(assets, '_verify_installed_support', lambda config: None)
    root, path = tmp_path / 'new-assets', tmp_path / 'manifest.json'
    return config, payloads, calls, root, path


def acquire(authored):
    config, _, _, root, path = authored
    return assets.acquire(Path('authored-config'), root, path)


def reseal(manifest):
    for entry in manifest['assets'].values():
        entry['snapshot_hash'] = content_hash(entry['files'])
    manifest['manifest_hash'] = content_hash({k: v for k, v in manifest.items() if k != 'manifest_hash'})


def test_tiny_inventory_passes_existing_verifier_and_is_immutable(authored, monkeypatch):
    from outcome_poc.assets import verify_assets
    config, payloads, calls, root, path = authored
    manifest = acquire(authored)
    verify_assets(manifest)
    assets.verify_manifest(manifest, config)
    assert manifest['status'] == 'ok'
    assert manifest['acquisition']['verified_bytes'] == sum(len(p) for files in payloads.values() for p in files.values())
    assert manifest['acquisition']['seconds'] >= 0
    assert manifest['original_license_sha256'] == config['original_license_sha256']
    assert manifest['assets']['reader']['source_url'].endswith(config['reader']['revision'])
    before = path.read_bytes()
    count = len(calls)
    assert acquire(authored) == manifest
    assert len(calls) == count
    assert path.read_bytes() == before


@pytest.mark.parametrize('change', ['extra', 'missing', 'unsafe', 'symlink', 'changed-byte', 'changed-size'])
def test_tampered_snapshot_is_rejected(authored, change):
    config, _, _, root, path = authored
    manifest = acquire(authored)
    local = Path(manifest['assets']['reader']['local_path'])
    shard = local / 'model-00001-of-00002.safetensors'
    if change == 'extra':
        (local / 'extra.json').write_text('{}')
    elif change == 'missing':
        shard.unlink()
    elif change == 'unsafe':
        (local / 'run.py').write_text('raise RuntimeError')
    elif change == 'symlink':
        outside = root.parent / 'outside'
        outside.write_bytes(shard.read_bytes())
        shard.unlink()
        shard.symlink_to(outside)
    elif change == 'changed-byte':
        shard.write_bytes(b'X' + shard.read_bytes()[1:])
    else:
        shard.write_bytes(shard.read_bytes() + b'X')
    with pytest.raises(ValueError):
        assets.verify_manifest(manifest, config)
    before = path.read_bytes()
    with pytest.raises(ValueError):
        acquire(authored)
    assert path.read_bytes() == before


@pytest.mark.parametrize('field,value', [('revision', 'b' * 40), ('repo_id', 'other/model'),
                                        ('license', 'mit'), ('kind', 'data'), ('source_url', 'https://wrong/')])
def test_resealed_metadata_disagreement_is_rejected(authored, field, value):
    config, *_ = authored
    manifest = acquire(authored)
    manifest['assets']['reader'][field] = value
    reseal(manifest)
    with pytest.raises(ValueError):
        assets.verify_manifest(manifest, config)


@pytest.mark.parametrize('wrong', ['metadata-revision', 'metadata-license', 'metadata-base-model', 'git-blob', 'lfs-hash', 'index', 'license', 'config'])
def test_invalid_acquisition_never_publishes_manifest(authored, monkeypatch, wrong):
    config, payloads, calls, root, path = authored
    if wrong.startswith('metadata-'):
        field = {'metadata-revision': 'revision', 'metadata-license': 'license', 'metadata-base-model': 'base_model'}[wrong]
        original = assets._hub_metadata
        def bad_metadata(*args, **kwargs):
            return {**original(*args, **kwargs), field: 'incorrect'}
        monkeypatch.setattr(assets, '_hub_metadata', bad_metadata)
    elif wrong == 'git-blob':
        config['inventories']['reader']['README.md']['blobId'] = '0' * 40
    elif wrong == 'lfs-hash':
        config['inventories']['reader']['model-00001-of-00002.safetensors']['lfs']['sha256'] = '0' * 64
    else:
        role, filename, payload = {
            'index': ('reader', 'model.safetensors.index.json', b'{"weight_map":{"x":"missing.safetensors"}}'),
            'license': ('original_reader', 'LICENSE', b'All rights reserved'),
            'config': ('reader', 'config.json', b'{"model_type":"untrusted","auto_map":{}}'),
        }[wrong]
        payloads[role][filename] = payload
        config['inventories'][role][filename] = pin(payload)
    with pytest.raises(ValueError):
        acquire(authored)
    assert not path.exists()
    if wrong.startswith('metadata-'):
        assert not any(kind == 'download' for kind, _ in calls)


def test_resealed_shard_cannot_redefine_the_pinned_hash(authored):
    from outcome_poc.assets import file_identity
    config, *_ = authored
    manifest = acquire(authored)
    entry = manifest['assets']['reader']
    shard = Path(entry['local_path']) / 'model-00001-of-00002.safetensors'
    shard.write_bytes(b'altered pinned content')
    entry['files'][shard.name] = file_identity(shard)
    reseal(manifest)
    with pytest.raises(ValueError):
        assets.verify_manifest(manifest, config)


def test_verification_imports_no_model_stack():
    result = subprocess.run([sys.executable, '-c',
        'import sys; import outcome_poc.reader_probe.assets; '
        'assert not any(n == "mlx" or n.startswith("mlx.") or n == "mlx_lm" or n.startswith("mlx_lm.") for n in sys.modules)'],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_installed_support_is_verified_without_importing_native_code(authored, tmp_path, monkeypatch):
    import types
    config, *_ = authored
    source = tmp_path / 'qwen3.py'
    source.write_text('raise RuntimeError("must never execute during verification")\n')
    config['architecture']['installed_source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.undo()
    monkeypatch.setattr(assets, 'distribution', lambda name: types.SimpleNamespace(locate_file=lambda _: source))
    assets._verify_installed_support(config)
    source.write_text('# changed native implementation\n')
    with pytest.raises(ValueError, match='architecture'):
        assets._verify_installed_support(config)


@pytest.mark.parametrize('part', ['root', 'role', 'revision'])
def test_external_directory_symlink_is_rejected_before_download(authored, monkeypatch, part):
    config, _, calls, root, path = authored
    outside = root.parent / 'external'
    outside.mkdir()
    link = {'root': root, 'role': root / 'reader',
            'revision': root / 'reader' / config['reader']['revision']}[part]
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        acquire(authored)
    assert not any(kind == 'download' for kind, _ in calls)
    assert not list(outside.iterdir())


@pytest.mark.parametrize('name', ['../unsafe.json', 'model-*.safetensors', 'model.bin', 'run.py'])
def test_nonliteral_or_unsafe_allowlist_is_rejected_before_download(authored, name):
    config, _, calls, *_ = authored
    config['inventories']['reader'][name] = pin(b'authored')
    with pytest.raises(ValueError):
        acquire(authored)
    assert not any(kind == 'download' for kind, _ in calls)


def test_resealed_false_source_url_is_rejected(authored):
    config, *_ = authored
    manifest = acquire(authored)
    manifest['assets']['reader']['file_source_urls']['README.md'] = 'https://wrong/source'
    reseal(manifest)
    with pytest.raises(ValueError):
        assets.verify_manifest(manifest, config)


def test_only_verified_preexisting_bytes_are_reused(authored):
    config, payloads, calls, root, path = authored
    local = root / 'reader' / config['reader']['revision']
    local.mkdir(parents=True)
    (local / 'README.md').write_bytes(payloads['reader']['README.md'])
    manifest = acquire(authored)
    assert manifest['acquisition']['reused_verified_bytes'] == len(payloads['reader']['README.md'])
    assert manifest['acquisition']['newly_materialized_bytes'] == (
        manifest['acquisition']['verified_bytes'] - len(payloads['reader']['README.md']))


def test_invalid_preexisting_bytes_are_preserved_and_never_downloaded_over(authored):
    config, _, calls, root, path = authored
    local = root / 'reader' / config['reader']['revision']
    local.mkdir(parents=True)
    (local / 'README.md').write_bytes(b'Unverified existing bytes')
    with pytest.raises(ValueError):
        acquire(authored)
    assert (local / 'README.md').read_bytes() == b'Unverified existing bytes'
    assert not any(kind == 'download' for kind, _ in calls)
    assert not path.exists()


@pytest.mark.parametrize('name', ['extra.bin', 'download/extra.bin', 'download/unrequested.json.metadata'])
def test_unknown_hub_cache_files_are_not_exempt_from_inventory(authored, name):
    config, *_ = authored
    manifest = acquire(authored)
    cache = Path(manifest['assets']['reader']['local_path']) / '.cache' / 'huggingface'
    path = cache / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'Unrecorded content')
    with pytest.raises(ValueError):
        assets.verify_manifest(manifest, config)


def test_expected_hub_download_bookkeeping_is_allowed(authored):
    config, *_ = authored
    manifest = acquire(authored)
    cache = Path(manifest['assets']['reader']['local_path']) / '.cache' / 'huggingface'
    (cache / 'download').mkdir(parents=True)
    (cache / '.gitignore').write_text('*')
    (cache / 'download' / 'README.md.metadata').write_text('author-only fixture metadata')
    (cache / 'download' / 'README.md.lock').touch()
    assets.verify_manifest(manifest, config)


def test_acquisition_records_full_verification_duration(authored, monkeypatch):
    elapsed = [10.0]
    original = assets.verify_manifest
    def verify(*args):
        original(*args)
        elapsed[0] += 7.0
    monkeypatch.setattr(assets.time, 'perf_counter', lambda: elapsed[0])
    monkeypatch.setattr(assets, 'verify_manifest', verify)
    manifest = acquire(authored)
    assert manifest['acquisition']['seconds'] == 7.0


def test_manifest_cannot_route_a_snapshot_through_an_external_symlink(authored):
    config, _, _, root, _ = authored
    manifest = acquire(authored)
    link = root.parent / 'alias'
    link.symlink_to(root, target_is_directory=True)
    manifest['assets']['reader']['local_path'] = str(link / 'reader' / config['reader']['revision'])
    reseal(manifest)
    with pytest.raises(ValueError):
        assets.verify_manifest(manifest, config)


def test_installed_hub_revision_tree_and_cache_tag_bookkeeping(authored):
    from huggingface_hub._local_folder import CACHEDIR_TAG_CONTENT
    config, *_ = authored
    manifest = acquire(authored)
    cache = Path(manifest['assets']['reader']['local_path'])/'.cache/huggingface'
    (cache/'trees').mkdir(parents=True)
    (cache/'CACHEDIR.TAG').write_text(CACHEDIR_TAG_CONTENT)
    tree = cache/'trees'/f"{config['reader']['revision']}.json"
    tree.write_text('{"authored-file":{"size":1,"blob_id":"authored"}}')
    assets.verify_manifest(manifest, config)
    wrong = cache/'trees'/('f'*40+'.json')
    wrong.write_text('{}')
    with pytest.raises(ValueError):assets.verify_manifest(manifest, config)

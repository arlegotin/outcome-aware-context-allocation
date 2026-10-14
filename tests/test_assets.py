"""Asset identity and licenses must precede offline inference."""
from pathlib import Path
import hashlib
import pytest

from outcome_poc import assets


COMMIT = 'a' * 40


def model_config():
    return {'reader': {'repo_id': 'reader'}, 'encoder': {'repo_id': 'encoder'},
            'original_reader': {'repo_id': 'original'}, 'data': []}


def test_resolve_pins_commit_before_download_and_hashes_selected_bytes(tmp_path, monkeypatch):
    def metadata(repo, revision=None):
        return {'revision': COMMIT, 'license': 'apache-2.0'}

    def download(repo, revision, destination):
        assert revision == COMMIT
        destination.mkdir(parents=True)
        (destination / 'README.md').write_text('---\nlicense: apache-2.0\n---\n')
        (destination / 'LICENSE').write_text('Apache License, Version 2.0')
        (destination / 'model.safetensors').write_bytes(b'safe weights')
        return destination

    monkeypatch.setattr(assets, '_hub_metadata', metadata)
    monkeypatch.setattr(assets, '_download_snapshot', download)
    manifest = assets.resolve_assets(model_config(), tmp_path)
    assets.verify_assets(manifest)
    entry = manifest['assets']['reader']
    assert entry['revision'] == COMMIT
    assert entry['files']['model.safetensors']['sha256'] == hashlib.sha256(b'safe weights').hexdigest()
    (Path(entry['local_path']) / 'model.safetensors').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash|bytes'):
        assets.verify_assets(manifest)


def test_missing_license_blocks_asset(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, '_hub_metadata', lambda repo, revision=None: {'revision': COMMIT, 'license': None})
    monkeypatch.setattr(assets, '_download_snapshot', lambda *args: pytest.fail('license must be checked before download'))
    manifest = assets.resolve_assets(model_config(), tmp_path)
    assert manifest['status'] == 'blocked'
    with pytest.raises(ValueError, match='license'):
        assets.verify_assets(manifest)


def test_unpinned_revision_blocks_before_download(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, '_hub_metadata', lambda repo, revision=None: {'revision': 'main', 'license': 'mit'})
    monkeypatch.setattr(assets, '_download_snapshot', lambda *args: pytest.fail('mutable revision'))
    with pytest.raises(ValueError, match='revision'):
        assets.verify_assets(assets.resolve_assets(model_config(), tmp_path))


def test_missing_indispensable_data_fails_overall_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, '_hub_metadata', lambda repo, revision=None: {'revision': revision or COMMIT, 'license': 'mit'})
    def snapshot(repo, revision, path):
        path.mkdir(parents=True)
        (path / 'LICENSE').write_text('MIT license')
        return path
    monkeypatch.setattr(assets, '_download_snapshot', snapshot)
    monkeypatch.setattr(assets, '_download_official', lambda *args: (_ for _ in ()).throw(TimeoutError('origin timed out')))
    config = model_config()
    config['data'] = [{'name': 'train', 'url': 'http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json',
                       'license': 'cc-by-sa-4.0', 'provenance_url': 'https://hotpotqa.github.io/'}]
    manifest = assets.resolve_assets(config, tmp_path)
    assert manifest['assets']['train']['status'] == 'blocked'
    assert manifest['assets']['reader']['status'] == 'ok'
    with pytest.raises(ValueError, match='train'):
        assets.verify_assets(manifest)


def test_external_pickle_cannot_be_verified(tmp_path):
    path = tmp_path / 'model.bin'
    path.write_bytes(b'untrusted pickle')
    manifest = {'required': ['reader'], 'assets': {'reader': {
        'status': 'ok', 'revision': COMMIT, 'license': 'mit', 'local_path': str(tmp_path),
        'files': {'model.bin': {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}},
        'kind': 'model'}}}
    with pytest.raises(ValueError, match='unsafe'):
        assets.verify_assets(manifest)


def test_verification_rejects_unrecorded_snapshot_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, '_hub_metadata', lambda repo, revision=None: {'revision': revision or COMMIT, 'license': 'mit'})
    def snapshot(repo, revision, path):
        path.mkdir(parents=True)
        (path / 'LICENSE').write_text('MIT license')
        return path
    monkeypatch.setattr(assets, '_download_snapshot', snapshot)
    manifest = assets.resolve_assets(model_config(), tmp_path)
    (Path(manifest['assets']['reader']['local_path']) / 'unrecorded.safetensors').write_bytes(b'other weights')
    with pytest.raises(ValueError, match='inventory|unrecorded'):
        assets.verify_assets(manifest)


def test_cached_snapshot_cannot_override_configured_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, '_hub_metadata', lambda repo, revision=None: {'revision': revision or COMMIT, 'license': 'mit'})
    def snapshot(repo, revision, path):
        path.mkdir(parents=True)
        (path / 'LICENSE').write_text('MIT license')
        return path
    monkeypatch.setattr(assets, '_download_snapshot', snapshot)
    assets.resolve_assets(model_config(), tmp_path)
    config = model_config()
    config['reader']['revision'] = 'b' * 40
    manifest = assets.resolve_assets(config, tmp_path)
    assert manifest['assets']['reader']['revision'] == 'b' * 40


def archive_source():
    return {'name': 'train', 'url': 'http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json',
            'archive': {'url': 'https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json',
                        'capture': '20250512032701', 'expected_bytes': 3, 'expected_rows': 1,
                        'sha1_base32': 'VGMT4NSHA2AWVOR6EVYXQUGCNSONBWE5'}}


def fake_archive_response(payload):
    import io
    response = io.BytesIO(payload)
    response.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(payload)),
                        'Memento-Datetime': 'Mon, 12 May 2025 03:27:01 GMT',
                        'X-Archive-Src': 'capture.warc.gz',
                        'Link': '<http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_train_v1.1.json>; rel="original"'}
    response.geturl = lambda: archive_source()['archive']['url']
    return response


def test_archive_rejects_partial_body_and_does_not_promote(tmp_path, monkeypatch):
    monkeypatch.setattr(assets.urllib.request, 'urlopen', lambda *args, **kwargs: fake_archive_response(b'[]'))
    path = tmp_path / 'train.json'
    with pytest.raises(ValueError, match='length'):
        assets._download_archive(archive_source(), path, 1)
    assert not path.exists()
    assert path.with_suffix('.json.partial').exists()


def test_archive_digest_is_full_body_sha1_base32(tmp_path, monkeypatch):
    # Hand-known RFC SHA1("abc") = a9993e364706816aba3e25717850c26c9cd0d89d.
    monkeypatch.setattr(assets.urllib.request, 'urlopen', lambda *args, **kwargs: fake_archive_response(b'abc'))
    source = archive_source()
    source['archive']['sha1_base32'] = 'VGMT4NSHA2AWVOR6EVYXQUGCNSONBWE5'
    result = assets._download_archive(source, tmp_path / 'train.json', 1)
    assert result['sha1_base32'] == 'VGMT4NSHA2AWVOR6EVYXQUGCNSONBWE5'
    source['archive']['sha1_base32'] = 'A' * 32
    with pytest.raises(ValueError, match='digest'):
        assets._download_archive(source, tmp_path / 'other.json', 1)


def test_hotpot_validation_checks_native_pairs_and_expected_count(tmp_path):
    import json
    row = {'_id': 'invented', 'question': 'Which color?', 'answer': 'blue',
           'context': [['Kite', ['The kite is blue.']]], 'supporting_facts': [['Kite', 0]],
           'type': 'bridge', 'level': 'easy'}
    path = tmp_path / 'invented.json'
    path.write_text(json.dumps([row]))
    assert assets._validate_hotpot(path, 1)['rows'] == 1
    with pytest.raises(ValueError, match='count'):
        assets._validate_hotpot(path, 2)
    row['supporting_facts'][0][1] = True
    path.write_text(json.dumps([row]))
    with pytest.raises(ValueError, match='schema'):
        assets._validate_hotpot(path, 1)


def test_data_verification_requires_raw_schema_and_author_provenance(tmp_path):
    path = tmp_path / 'hotpot_train_v1.1.json'
    path.write_text('[]')
    entry = {'kind': 'data', 'status': 'ok', 'license': 'cc-by-sa-4.0',
             'local_path': str(tmp_path), 'files': {path.name: assets.file_identity(path)}}
    with pytest.raises(ValueError, match='schema|provenance'):
        assets.verify_assets({'required': ['train'], 'assets': {'train': entry}})


def test_archive_fallback_requires_explicit_source_amendment(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, '_hub_metadata', lambda repo, revision=None: {'revision': COMMIT, 'license': 'mit'})
    def snapshot(repo, revision, path):
        path.mkdir(parents=True)
        (path / 'LICENSE').write_text('MIT license')
        return path
    monkeypatch.setattr(assets, '_download_snapshot', snapshot)
    def origin(*args):
        raise TimeoutError('origin unavailable')
    monkeypatch.setattr(assets, '_download_official', origin)
    monkeypatch.setattr(assets, '_download_archive', lambda *args: {'final_url': 'unauthorized archive'})
    config = model_config()
    source = archive_source()
    source.update(license='cc-by-sa-4.0', provenance_url='https://hotpotqa.github.io/', expected_rows=1)
    config['data'] = [source]
    manifest = assets.resolve_assets(config, tmp_path)
    assert 'amendment' in manifest['assets']['train']['error']

"""Allowlisted pinned Hub acquisition and CPU-only file identity verification."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import re
import time

from ..assets import _hub_metadata, verify_assets
from ..storage import canonical_bytes, content_hash
from .profile import load_config


ROLES = ('reader', 'original_reader')


def _download_snapshot(repo, revision, destination, filenames):
    from huggingface_hub import snapshot_download
    return Path(snapshot_download(repo_id=repo, revision=revision, local_dir=destination,
                                  allow_patterns=list(filenames), max_workers=4))


def _verify_installed_support(config):
    """Verify the inspected native implementation without importing MLX or code."""
    architecture = config['architecture']
    source = Path(distribution('mlx-lm').locate_file(architecture['installed_module']))
    if (not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() !=
            architecture['installed_source_sha256']):
        raise ValueError('installed architecture support differs from inspected native source')


def _inventory_spec(config, role):
    inventory = config['inventories'][role]
    if not inventory:
        raise ValueError(f'{role}: empty required inventory')
    for name, pin in inventory.items():
        # Explicit flat allowlist: no glob patterns, paths, scripts or checkpoints.
        if (Path(name).name != name or name in {'.', '..'} or
                not (name in {'README.md', 'LICENSE', 'config.json', 'merges.txt', 'vocab.json',
                              'added_tokens.json', 'special_tokens_map.json', 'tokenizer.json',
                              'tokenizer_config.json', 'model.safetensors.index.json'} or
                     re.fullmatch(r'model-[0-9]{5}-of-[0-9]{5}\.safetensors', name))):
            raise ValueError(f'{role}: unsafe inventory filename {name}')
        if (type(pin.get('size')) is not int or pin['size'] <= 0 or
                re.fullmatch(r'[0-9a-f]{40}', pin.get('blobId', '')) is None or
                ('lfs' in pin and (pin['lfs'].get('size') != pin['size'] or
                                  re.fullmatch(r'[0-9a-f]{64}', pin['lfs'].get('sha256', '')) is None))):
            raise ValueError(f'{role}: invalid pinned file metadata')
    if role == 'original_reader' and set(inventory) != {'README.md', 'LICENSE', 'config.json'}:
        raise ValueError('original_reader: only inspected license/card/config allowed')
    return inventory


def _local_inventory(local, filenames, revision):
    if local.is_symlink() or not local.is_dir():
        raise ValueError('expected nonsymlink local snapshot directory')
    inventory = set()
    bookkeeping = {'.cache/huggingface/.gitignore', '.cache/huggingface/.gitignore.lock'}
    bookkeeping.add(f'.cache/huggingface/trees/{revision}.json')
    tag = local / '.cache/huggingface/CACHEDIR.TAG'
    expected_tag = ('Signature: 8a477f597d28d172789f06886806bc55\n'
        '# This file is a cache directory tag created by huggingface_hub.\n'
        '# For information about cache directory tags, see:\n'
        '#\thttps://bford.info/cachedir/\n')
    if tag.exists() and not tag.is_symlink() and tag.read_text() == expected_tag:
        bookkeeping.add('.cache/huggingface/CACHEDIR.TAG')
    bookkeeping.update(f'.cache/huggingface/download/{name}.{suffix}'
                       for name in filenames for suffix in ('metadata', 'lock'))
    for path in local.rglob('*'):
        if path.is_symlink():
            raise ValueError(f'symlink in asset snapshot: {path.name}')
        relative = path.relative_to(local)
        # Only known Hub bookkeeping for the exact allowlist is exempt. Unknown
        # files, partial downloads and symlinks cannot hide in the Hub cache.
        if path.is_file() and str(relative) not in bookkeeping:
            inventory.add(str(relative))
    return inventory


def _verify_file(path, pin):
    size = path.stat().st_size
    if size != pin['size']:
        raise ValueError(f'{path.name}: pinned file bytes mismatch')
    sha256 = hashlib.sha256()
    blob = None if 'lfs' in pin else hashlib.sha1(b'blob ' + str(size).encode('ascii') + b'\0')
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha256.update(block)
            if blob is not None:
                blob.update(block)
    digest = sha256.hexdigest()
    if 'lfs' in pin:
        if digest != pin['lfs']['sha256']:
            raise ValueError(f'{path.name}: pinned LFS SHA256 mismatch')
    elif blob.hexdigest() != pin['blobId']:
        raise ValueError(f'{path.name}: pinned Git blob identity mismatch')
    return {'bytes': size, 'sha256': digest}


def _verified_files(local, config, role):
    spec = _inventory_spec(config, role)
    if _local_inventory(local, spec, config[role]['revision']) != set(spec):
        raise ValueError(f'{role}: extra, missing or unsafe snapshot inventory')
    files = {name: _verify_file(local / name, pin) for name, pin in spec.items()}
    card = (local / 'README.md').read_text(encoding='utf-8')
    frontmatter = card.split('---', 2)
    if (len(frontmatter) != 3 or frontmatter[0].strip() or
            'license: apache-2.0' not in frontmatter[1].splitlines()):
        raise ValueError(f'{role}: missing Apache-2.0 card identity')
    architecture = json.loads((local / 'config.json').read_text())
    if (architecture.get('model_type') != config['architecture']['model_type'] or
            architecture.get('architectures') != config['architecture']['architectures'] or
            'auto_map' in architecture):
        raise ValueError(f'{role}: configuration architecture or remote code mismatch')
    if role == 'reader':
        index = json.loads((local / 'model.safetensors.index.json').read_text())
        mapping = index.get('weight_map')
        shards = {name for name in spec if name.endswith('.safetensors')}
        if (not isinstance(mapping, dict) or not mapping or
                any(type(key) is not str or not key or type(value) is not str
                    for key, value in mapping.items()) or set(mapping.values()) != shards):
            raise ValueError('safetensors index does not cover exactly the verified shards')
        tokenizer = json.loads((local / 'tokenizer_config.json').read_text())
        if ('auto_map' in tokenizer or 'enable_thinking' not in str(tokenizer.get('chat_template', ''))):
            raise ValueError('tokenizer requires safe official nonthinking chat template')
    else:
        if files['LICENSE']['sha256'] != config['original_license_sha256']:
            raise ValueError('original license digest mismatch')
        if 'Apache License' not in (local / 'LICENSE').read_text(encoding='utf-8'):
            raise ValueError('original license is not Apache-2.0')
    return files


def _metadata(config, role):
    source = config[role]
    result = _hub_metadata(source['repo_id'], source['revision'])
    url = f"https://huggingface.co/{source['repo_id']}/tree/{source['revision']}"
    if (result.get('revision') != source['revision'] or result.get('license') != config['license'] or
            result.get('source_url') != url or
            (role == 'reader' and result.get('base_model') != config['original_reader']['repo_id'])):
        raise ValueError(f'{role}: pinned Hub metadata identity/license mismatch')
    return result


def verify_manifest(manifest: dict, config: dict) -> None:
    """Recheck recorded and pinned identities, including every acquired byte."""
    if (manifest.get('status') != 'ok' or manifest.get('required') != list(ROLES) or
            set(manifest.get('assets', {})) != set(ROLES) or
            manifest.get('config_hash') != content_hash(config) or
            manifest.get('original_license_sha256') != config['original_license_sha256'] or
            manifest.get('manifest_hash') != content_hash(
                {key: value for key, value in manifest.items() if key != 'manifest_hash'})):
        raise ValueError('asset manifest/configuration identity mismatch')
    for role in ROLES:
        entry = manifest['assets'][role]
        expected = config[role]
        url = f"https://huggingface.co/{expected['repo_id']}/tree/{expected['revision']}"
        if (entry.get('kind') != 'model' or entry.get('status') != 'ok' or
                entry.get('license') != config['license'] or entry.get('source_url') != url or
                any(entry.get(key) != expected[key] for key in ('repo_id', 'revision')) or
                (role == 'reader' and entry.get('base_model') != config['original_reader']['repo_id'])):
            raise ValueError(f'{role}: manifest metadata pin/license mismatch')
        local = Path(entry.get('local_path', ''))
        if not local.is_absolute() or local.resolve() != local:
            raise ValueError(f'{role}: canonical absolute local snapshot required, without symlinks')
        files = _verified_files(local, config, role)
        urls = {name: f"https://huggingface.co/{expected['repo_id']}/resolve/{expected['revision']}/{name}"
                for name in files}
        if (entry.get('files') != files or entry.get('snapshot_hash') != content_hash(files) or
                entry.get('file_source_urls') != urls):
            raise ValueError(f'{role}: recorded file or snapshot identity mismatch')
    verify_assets(manifest)


def _publish_new(path, manifest):
    """Publish without replacing a completed manifest, even with a second writer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.partial')
    with temporary.open('xb') as stream:
        stream.write(canonical_bytes(manifest))
        stream.flush()
        os.fsync(stream.fileno())
    # link is an atomic create-if-absent; interrupted work remains visible.
    os.link(temporary, path)
    temporary.unlink()
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def acquire(config_path: Path, asset_root: Path, manifest_path: Path) -> dict:
    """Separately measured network acquisition; never loads native/model code."""
    config = load_config(config_path)
    asset_root, manifest_path = Path(asset_root).absolute(), Path(manifest_path).absolute()
    # Check all project-owned path components before the Hub API can write.
    # System aliases above the requested root (e.g. /var -> /private/var) are
    # canonicalized only after rejecting symlinks within the asset namespace.
    for path in [asset_root, *(asset_root / role for role in ROLES),
                 *(asset_root / role / config[role]['revision'] for role in ROLES)]:
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise ValueError('symlink or nondirectory in isolated asset destination')
    asset_root = asset_root.resolve()
    if manifest_path.is_symlink():
        raise ValueError('asset manifest must not be a symlink')
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        verify_manifest(manifest, config)
        for role in ROLES:
            expected = asset_root / role / config[role]['revision']
            if Path(manifest['assets'][role]['local_path']) != expected:
                raise ValueError('completed manifest belongs to a different asset root')
        return manifest
    started = time.perf_counter()
    _verify_installed_support(config)
    # Both licenses and immutable metadata identities gate any byte acquisition.
    metadata = {role: _metadata(config, role) for role in ROLES}
    inventories = {role: _inventory_spec(config, role) for role in ROLES}
    reused = 0
    for role in ROLES:
        local = asset_root / role / config[role]['revision']
        if local.exists():
            inventory = _local_inventory(local, inventories[role], config[role]['revision'])
            if not inventory <= set(inventories[role]):
                raise ValueError('unrecorded preexisting asset files; refusing overwrite')
            for name in inventory:
                reused += _verify_file(local / name, inventories[role][name])['bytes']
    manifest = {'status': 'ok', 'required': list(ROLES), 'assets': {},
                'measured_utc': datetime.now(timezone.utc).isoformat(),
                'config_hash': content_hash(config),
                'original_license_sha256': config['original_license_sha256'],
                'conversion_source_revision_known': False}
    for role in ROLES:
        source = config[role]
        destination = asset_root / role / source['revision']
        local = _download_snapshot(source['repo_id'], source['revision'], destination,
                                   list(inventories[role]))
        if local.absolute() != destination or local.resolve() != destination:
            raise ValueError('Hub snapshot did not use the requested isolated local directory')
        files = _verified_files(local, config, role)
        manifest['assets'][role] = {
            **metadata[role], 'kind': 'model', 'status': 'ok',
            'repo_id': source['repo_id'], 'local_path': str(local),
            'files': files, 'snapshot_hash': content_hash(files),
            'file_source_urls': {name: f"https://huggingface.co/{source['repo_id']}/resolve/{source['revision']}/{name}"
                                 for name in files},
        }
    verified = sum(f['bytes'] for entry in manifest['assets'].values() for f in entry['files'].values())
    manifest['acquisition'] = {
        'seconds': time.perf_counter() - started, 'verified_bytes': verified,
        'reused_verified_bytes': reused, 'newly_materialized_bytes': verified - reused,
        'byte_measurement': 'verified payload bytes; newly materialized bytes exclude preexisting verified files; network transport bytes unavailable',
    }
    manifest['manifest_hash'] = content_hash(manifest)
    verify_manifest(manifest, config)
    # Include validation work in acquisition time. Only the measured duration
    # changes after the full byte/metadata verification, so reseal before publish.
    manifest['acquisition']['seconds'] = time.perf_counter() - started
    manifest['manifest_hash'] = content_hash({key: value for key, value in manifest.items()
                                             if key != 'manifest_hash'})
    _publish_new(manifest_path, manifest)
    return manifest

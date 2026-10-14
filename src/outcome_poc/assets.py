"""Revision-pinned safe assets with author-only data and fail-closed verification."""
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.request

from .storage import atomic_json, content_hash


SAFE_PATTERNS = ['*.safetensors', '*.json', '*.txt', '*.model', '*.jinja', 'README.md', 'LICENSE*']
SUPPORTED_LICENSES = {'apache-2.0', 'mit', 'cc-by-sa-4.0'}
OFFICIAL_DATA = {'hotpot_train_v1.1.json': (566426227, 90447),
                 'hotpot_dev_distractor_v1.json': (46320117, 7405)}


def file_identity(path: Path) -> dict:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return {'bytes': Path(path).stat().st_size, 'sha256': digest.hexdigest()}


def _safe_file(name: str) -> bool:
    path = Path(name)
    return (not path.is_absolute() and '..' not in path.parts and
            (path.suffix in {'.safetensors', '.json', '.txt', '.model', '.jinja'} or
             path.name == 'README.md' or path.name.startswith('LICENSE')))


def _hub_metadata(repo: str, revision: str | None = None) -> dict:
    from huggingface_hub import HfApi
    info = HfApi().model_info(repo, revision=revision)
    card = info.card_data.to_dict() if info.card_data else {}
    return {'revision': info.sha, 'license': card.get('license'),
            'license_link': card.get('license_link'), 'base_model': card.get('base_model'),
            'source_url': f'https://huggingface.co/{repo}/tree/{info.sha}'}


def _download_snapshot(repo: str, revision: str, destination: Path) -> Path:
    from huggingface_hub import snapshot_download
    # The original provides licensing/configuration provenance, not a second reader.
    patterns = ['LICENSE*', 'README.md', 'config.json'] if repo == 'Qwen/Qwen3-4B-Instruct-2507' else SAFE_PATTERNS
    return Path(snapshot_download(repo_id=repo, revision=revision, local_dir=destination,
                                 allow_patterns=patterns, max_workers=4))


def _download_official(url: str, destination: Path, timeout: int) -> dict:
    if not url.startswith('http://curtis.ml.cmu.edu/datasets/hotpot/'):
        raise ValueError('data URL is not the mandatory author source')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.partial')
    # Failed partial bodies remain visible and never become verified assets.
    with urllib.request.urlopen(url, timeout=timeout) as response, temporary.open('wb') as stream:
        final_url = response.geturl()
        while block := response.read(1024 * 1024):
            stream.write(block)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, destination)
    return {'source_url': url, 'final_url': final_url, 'redirected': final_url != url}



def _download_archive(source: dict, destination: Path, timeout: int) -> dict:
    archive = source['archive']
    requested = archive['url']
    expected_url = f"https://web.archive.org/web/{archive['capture']}id_/{source['url']}"
    if requested != expected_url or archive['capture'] != '20250512032701':
        raise ValueError('archive URL/capture differs from source amendment A01')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.partial')
    sha1 = hashlib.sha1()
    started = time.perf_counter()
    with urllib.request.urlopen(requested, timeout=timeout) as response, temporary.open('wb') as stream:
        headers = {key.lower(): value for key, value in response.headers.items()}
        final_url = response.geturl()
        if (final_url != requested or 'application/json' not in headers.get('content-type', '') or
                headers.get('memento-datetime') != 'Mon, 12 May 2025 03:27:01 GMT' or
                not headers.get('x-archive-src') or
                f"<{source['url']}>; rel=\"original\"" not in headers.get('link', '')):
            raise ValueError('archive author-origin response metadata mismatch')
        for block in iter(lambda: response.read(1024 * 1024), b''):
            stream.write(block)
            sha1.update(block)
        stream.flush()
        os.fsync(stream.fileno())
    actual = temporary.stat().st_size
    if actual != archive['expected_bytes'] or int(headers.get('content-length', actual)) != actual:
        raise ValueError('archive full response length mismatch')
    digest = base64.b32encode(sha1.digest()).decode('ascii')
    if archive.get('sha1_base32') and archive['sha1_base32'] != digest:
        raise ValueError('archive payload digest mismatch')
    os.replace(temporary, destination)
    return {'source_url': source['url'], 'requested_url': requested, 'final_url': final_url,
            'source_policy': 'direct_author_or_pinned_raw_author_archive', 'source_amendment': 'A01',
            'archive_capture': archive['capture'], 'archive_headers': headers,
            'sha1_base32': digest, 'archive_digest_verified': bool(archive.get('sha1_base32')),
            'download_seconds': time.perf_counter() - started,
            'integrity_limitation': 'No separately fetched current author file or author cryptographic checksum.'}


def _validate_hotpot(path: Path, expected_rows: int) -> dict:
    started = time.perf_counter()
    with path.open(encoding='utf-8') as stream:
        records = json.load(stream)
    if type(records) is not list or len(records) != expected_rows:
        raise ValueError('native HotpotQA row count mismatch')
    identities = set()
    for row in records:
        if (type(row) is not dict or not {'_id', 'question', 'answer', 'context', 'supporting_facts', 'type', 'level'} <= set(row) or
                any(type(row[key]) is not str for key in ('_id', 'question', 'answer', 'type', 'level')) or
                not row['_id'] or row['_id'] in identities or
                type(row['context']) is not list or type(row['supporting_facts']) is not list):
            raise ValueError('native HotpotQA schema mismatch')
        identities.add(row['_id'])
        for paragraph in row['context']:
            if (type(paragraph) is not list or len(paragraph) != 2 or type(paragraph[0]) is not str or
                    type(paragraph[1]) is not list or any(type(sentence) is not str for sentence in paragraph[1])):
                raise ValueError('native HotpotQA context schema mismatch')
        for support in row['supporting_facts']:
            if (type(support) is not list or len(support) != 2 or type(support[0]) is not str or
                    type(support[1]) is not int or support[1] < 0):
                raise ValueError('native HotpotQA support schema mismatch')
    info = {'rows': len(records), 'schema_verified': True, 'validation_seconds': time.perf_counter() - started}
    try:
        import psutil
        info['validation_rss_bytes'] = psutil.Process().memory_info().rss
    except (ImportError, OSError):
        info['validation_rss_bytes'] = None
    return info

def resolve_assets(config: dict, cache_dir: Path) -> dict:
    cache_dir = Path(cache_dir).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('HF_HOME', str(Path('.cache/huggingface').resolve()))
    os.environ.setdefault('HF_XET_CACHE', str(Path('.cache/huggingface/xet').resolve()))
    manifest = {'measured_utc': datetime.now(timezone.utc).isoformat(), 'required': [], 'assets': {}}
    # Reuse only already verified bytes; never replace a recorded pin with today's main.
    manifest_path = cache_dir / 'asset-manifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'assets': {}}
    for role in ('reader', 'encoder', 'original_reader'):
        if role not in config:
            continue
        manifest['required'].append(role)
        repo = config[role]['repo_id']
        entry = {'kind': 'model', 'repo_id': repo, 'status': 'blocked'}
        try:
            old = previous['assets'].get(role)
            if (old and old.get('status') == 'ok' and old.get('repo_id') == repo and
                    (not config[role].get('revision') or old.get('revision') == config[role]['revision'])):
                verify_assets({'required': [role], 'assets': {role: old}})
                entry = old
            else:
                entry.update(_hub_metadata(repo, config[role].get('revision')))
                revision = entry.get('revision')
                if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{40}', revision):
                    raise ValueError('immutable commit revision unavailable')
                expected_revision = config[role].get('revision')
                if expected_revision and expected_revision != revision:
                    raise ValueError('resolved revision mismatches configured revision')
                if entry.get('license') not in SUPPORTED_LICENSES:
                    raise ValueError('missing or unsupported license')
                destination = cache_dir / role / revision
                local = _download_snapshot(repo, revision, destination).resolve()
                files = {str(p.relative_to(local)): file_identity(p) for p in local.rglob('*')
                         if p.is_file() and '.cache' not in p.relative_to(local).parts}
                if not files or not any(name.startswith('LICENSE') or name == 'README.md' for name in files):
                    raise ValueError('missing preserved license/card evidence')
                if any(not _safe_file(name) for name in files):
                    raise ValueError('unsafe snapshot file')
                entry.update(local_path=str(local), files=files, snapshot_hash=content_hash(files), status='ok')
        except Exception as error:
            entry.update(status='blocked', error=f'{type(error).__name__}: {error}')
        manifest['assets'][role] = entry
    for source in config.get('data', []):
        name = source['name']
        manifest['required'].append(name)
        entry = {'kind': 'data', 'license': source.get('license'), 'provenance_url': source.get('provenance_url'),
                 'source_url': source['url'], 'final_url': None, 'status': 'blocked'}
        try:
            if source.get('archive') and (config.get('asset_source_amendment') != 'A01' or
                    config.get('asset_source_policy') != 'direct_author_or_pinned_raw_author_archive'):
                raise ValueError('raw archive fallback requires explicit source amendment A01')
            if entry['license'] != 'cc-by-sa-4.0' or not entry['provenance_url']:
                raise ValueError('missing author attribution/license')
            old = previous['assets'].get(name)
            if (old and old.get('status') == 'ok' and old.get('source_url') == source['url'] and
                    (not old.get('archive_capture') or source.get('archive'))):
                verify_assets({'required': [name], 'assets': {name: old}})
                entry = old
            else:
                destination = cache_dir / 'data' / Path(source['url']).name
                entry['attempts'] = []
                try:
                    entry.update(_download_official(source['url'], destination, config.get('download_timeout_seconds', 20)))
                    entry['attempts'].append({'url': source['url'], 'status': 'ok'})
                except Exception as origin_error:
                    entry['attempts'].append({'url': source['url'], 'status': 'failed',
                                              'error': f'{type(origin_error).__name__}: {origin_error}'})
                    if not source.get('archive'):
                        raise
                    entry.update(_download_archive(source, destination, config.get('archive_timeout_seconds', 180)))
                    entry['attempts'].append({'url': source['archive']['url'], 'status': 'ok'})
                entry.update(_validate_hotpot(destination, source['expected_rows']))
                entry.update(local_path=str(destination.parent), files={destination.name: file_identity(destination)}, status='ok')
        except Exception as error:
            entry['error'] = f'{type(error).__name__}: {error}'
        manifest['assets'][name] = entry
    manifest['status'] = 'ok' if all(e['status'] == 'ok' for e in manifest['assets'].values()) else 'blocked'
    manifest['manifest_hash'] = content_hash({key: value for key, value in manifest.items() if key != 'manifest_hash'})
    atomic_json(manifest_path, manifest)
    return manifest


def verify_assets(manifest: dict) -> None:
    if not manifest.get('required'):
        raise ValueError('no required assets declared')
    if manifest.get('manifest_hash') and manifest['manifest_hash'] != content_hash(
            {key: value for key, value in manifest.items() if key != 'manifest_hash'}):
        raise ValueError('asset manifest hash mismatch')
    for name in manifest['required']:
        entry = manifest.get('assets', {}).get(name, {})
        if entry.get('status') != 'ok':
            raise ValueError(f'{name}: asset blocked: {entry.get("error", "missing asset")}')
        if entry.get('license') not in SUPPORTED_LICENSES:
            raise ValueError(f'{name}: missing usable license')
        if entry.get('kind') == 'model' and not re.fullmatch('[0-9a-f]{40}', entry.get('revision', '')):
            raise ValueError(f'{name}: unpinned revision')
        if entry.get('kind') == 'data':
            filename = Path(entry.get('source_url', '')).name
            if (filename not in OFFICIAL_DATA or
                    entry.get('source_url') != f'http://curtis.ml.cmu.edu/datasets/hotpot/{filename}' or
                    entry.get('provenance_url') != 'https://hotpotqa.github.io/' or
                    entry.get('schema_verified') is not True or
                    entry.get('rows') != OFFICIAL_DATA.get(filename, (0, 0))[1]):
                raise ValueError(f'{name}: missing verified native data schema/provenance')
            if entry.get('archive_capture'):
                if (entry['archive_capture'] != '20250512032701' or entry.get('source_amendment') != 'A01' or
                        entry.get('files', {}).get(filename, {}).get('bytes') != OFFICIAL_DATA[filename][0]):
                    raise ValueError(f'{name}: archived source identity mismatch')
                if filename == 'hotpot_train_v1.1.json' and (entry.get('sha1_base32') != 'BDCCIMOCFGCPGYXJJXQOMNOHXBMMHT7Q' or
                                                          entry.get('archive_digest_verified') is not True):
                    raise ValueError(f'{name}: archived training payload digest unverified')
        local = Path(entry.get('local_path', ''))
        if not local.is_absolute() or not local.is_dir():
            raise ValueError(f'{name}: expected existing absolute local asset path')
        if not entry.get('files'):
            raise ValueError(f'{name}: empty asset files')
        inventory = {str(p.relative_to(local)) for p in local.rglob('*')
                     if p.is_file() and '.cache' not in p.relative_to(local).parts}
        if entry.get('kind') == 'model' and inventory != set(entry['files']):
            raise ValueError(f'{name}: unrecorded or missing snapshot inventory')
        for relative, expected in entry['files'].items():
            if not _safe_file(relative):
                raise ValueError(f'{name}: unsafe file {relative}')
            path = (local / relative).resolve()
            if not path.is_relative_to(local.resolve()) or not path.is_file():
                raise ValueError(f'{name}: missing or escaping file {relative}')
            if file_identity(path) != expected:
                raise ValueError(f'{name}: hash/bytes mismatch for {relative}')


def main(args) -> int:
    config = json.loads(Path(args.config).read_text())
    manifest = resolve_assets(config, Path(config['cache_dir']))
    atomic_json(Path(config['output_dir']) / 'asset-manifest.json', manifest)
    print(json.dumps({'status': manifest['status'], 'assets': {
        name: {key: entry.get(key) for key in ('status', 'revision', 'license', 'error')}
        for name, entry in manifest['assets'].items()}}, indent=2))
    try:
        verify_assets(manifest)
        return 0
    except ValueError:
        return 1

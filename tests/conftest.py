"""Shared test support; experiment fixtures must contain invented text only."""


import copy
import hashlib
import json
import pytest


@pytest.fixture
def raw_hotpot():
    return {'_id': 'invented-task', 'question': 'Which lantern glows?',
            'answer': 'violet', 'type': 'bridge', 'level': 'easy',
            'context': [[f'Invented lantern {i}', [f'Lantern {i} rests.', f'Lantern {i} glows.']]
                        for i in range(10)],
            'supporting_facts': [['Invented lantern 0', 1], ['Invented lantern 1', 0]]}


@pytest.fixture
def documents10(raw_hotpot):
    from outcome_poc.schemas import Document
    from outcome_poc.storage import content_hash
    return [Document(content_hash([title, sentences]), title, sentences,
                     sum(map(len, sentences))) for title, sentences in raw_hotpot['context']]


@pytest.fixture
def task10(raw_hotpot, documents10):
    from outcome_poc.schemas import Task
    return Task(raw_hotpot['_id'], 'fit', raw_hotpot['question'],
                [doc.doc_id for doc in documents10])


@pytest.fixture(scope='module')
def matching_asset_template(tmp_path_factory):
    """Invented but fully valid native dev bytes; never fed to a public reader."""
    root = tmp_path_factory.mktemp('configured-assets')
    config = {'reader': {'repo_id': 'invented-reader', 'revision': 'a'*40},
              'encoder': {'repo_id': 'invented-encoder', 'revision': 'b'*40,
                          'device': 'cpu', 'precision': 'float32', 'dimensions': 384},
              'original_reader': {'repo_id': 'invented-original', 'revision': 'c'*40},
              'asset_source_amendment': 'A01', 'asset_source_policy': 'direct_author_or_pinned_raw_author_archive',
              'data': [{'name': 'dev', 'url': 'http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json',
                        'license': 'cc-by-sa-4.0', 'provenance_url': 'https://hotpotqa.github.io/', 'expected_rows': 7405,
                        'archive': {'url': 'https://web.archive.org/web/20250512032701id_/http://curtis.ml.cmu.edu/datasets/hotpot/hotpot_dev_distractor_v1.json',
                                    'capture': '20250512032701', 'expected_bytes': 46320117, 'expected_rows': 7405, 'sha1_base32': None}}]}
    entries = {}
    for role in ('reader', 'encoder', 'original_reader'):
        path = root / role
        path.mkdir()
        (path / 'LICENSE').write_text('MIT license for invented fixture')
        payload = (path / 'LICENSE').read_bytes()
        entries[role] = {'status': 'ok', 'kind': 'model', 'license': 'mit',
                         **config[role], 'local_path': str(path),
                         'files': {'LICENSE': {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}}}
    source = config['data'][0]
    data_dir = root / 'data'
    data_dir.mkdir()
    path = data_dir / 'hotpot_dev_distractor_v1.json'
    rows = [{'_id': f'invented-{i}', 'question': 'Which color?', 'answer': 'blue',
             'context': [['Kite', ['The kite is blue.']]], 'supporting_facts': [['Kite', 0]],
             'type': 'bridge', 'level': 'easy'} for i in range(7405)]
    with path.open('wb') as stream:
        stream.write(json.dumps(rows).encode())
        while stream.tell() < 46320117:
            stream.write(b' ' * min(1024 * 1024, 46320117 - stream.tell()))
    from outcome_poc.assets import _validate_hotpot
    _validate_hotpot(path, 7405)
    payload = path.read_bytes()
    entries['dev'] = {'status': 'ok', 'kind': 'data', 'license': 'cc-by-sa-4.0',
                      'source_url': source['url'], 'provenance_url': source['provenance_url'],
                      'requested_url': source['archive']['url'], 'final_url': source['archive']['url'],
                      'source_policy': config['asset_source_policy'], 'source_amendment': 'A01',
                      'archive_capture': '20250512032701', 'schema_verified': True, 'rows': 7405,
                      'archive_headers': {'memento-datetime': 'Mon, 12 May 2025 03:27:01 GMT',
                                         'x-archive-src': 'invented.warc.gz',
                                         'link': f'<{source["url"]}>; rel="original"'},
                      'local_path': str(data_dir),
                      'files': {path.name: {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}}}
    return config, {'required': list(entries), 'assets': entries}


@pytest.fixture
def matching_assets(matching_asset_template):
    return copy.deepcopy(matching_asset_template)

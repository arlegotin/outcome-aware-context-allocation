"""Pre-outcome conversion, structural exclusions, and deterministic reservations.

This command module may read annotations. Serving imports data_runtime instead.
"""

from collections import Counter
from collections.abc import Iterator
import hashlib
import json
import os
from pathlib import Path
import resource
import sqlite3
import sys
import tempfile
import time
import unicodedata

from .data_runtime import DocumentStore, load_tasks, _record
from .schemas import Document, Task
from .storage import atomic_json, canonical_bytes, content_hash, read_jsonl


def normalize_question(question: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', question).casefold().split())


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON object key')
        value[key] = item
    return value


def _nonfinite(value):
    raise ValueError(f'nonfinite JSON value {value}')


def _raw_rows(path: Path, chunk_size: int = 65536) -> Iterator[object]:
    """Stream a strict JSON array, retaining a chunk plus one raw record."""
    decoder = json.JSONDecoder(object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    with Path(path).open('r', encoding='utf-8') as stream:
        buffer, position, eof = '', 0, False

        def fill():
            nonlocal buffer, position, eof
            buffer = buffer[position:]
            position = 0
            chunk = stream.read(chunk_size)
            buffer += chunk
            eof = not chunk

        def whitespace():
            nonlocal position
            while True:
                while position < len(buffer) and buffer[position] in ' \r\n\t':
                    position += 1
                if position < len(buffer) or eof:
                    return
                fill()

        whitespace()
        if position >= len(buffer) or buffer[position] != '[':
            raise ValueError('raw source must be a JSON array')
        position += 1
        first = True
        while True:
            whitespace()
            if position >= len(buffer):
                raise ValueError('incomplete raw JSON array')
            if buffer[position] == ']':
                position += 1
                break
            if not first:
                if buffer[position] != ',':
                    raise ValueError('expected raw array separator')
                position += 1
                whitespace()
                if position >= len(buffer) or buffer[position] == ']':
                    raise ValueError('trailing or incomplete raw array separator')
            while True:
                try:
                    row, end = decoder.raw_decode(buffer, position)
                    break
                except json.JSONDecodeError as error:
                    if eof:
                        raise ValueError('malformed raw JSON record') from error
                    fill()
            position = end
            yield row
            first = False
        whitespace()
        if position < len(buffer):
            raise ValueError('trailing raw JSON content')


def _unicode_valid(value) -> bool:
    if type(value) is str:
        try:
            value.encode('utf-8')
        except UnicodeError:
            return False
    elif type(value) is list:
        return all(_unicode_valid(item) for item in value)
    elif type(value) is dict:
        return all(_unicode_valid(key) and _unicode_valid(item) for key, item in value.items())
    return True


def _convert(row: object):
    if type(row) is not dict:
        raise ValueError('invalid_record')
    if not _unicode_valid(row):
        raise ValueError('invalid_unicode')
    if type(row.get('_id')) is not str or not row['_id'].strip():
        raise ValueError('invalid_id')
    if type(row.get('question')) is not str or not normalize_question(row['question']):
        raise ValueError('invalid_question')
    if type(row.get('answer')) is not str:
        raise ValueError('invalid_answer')
    context = row.get('context')
    if type(context) is not list or len(context) != 10:
        raise ValueError('paragraph_count')
    documents, by_title = [], {}
    for paragraph in context:
        if (type(paragraph) is not list or len(paragraph) != 2 or
                type(paragraph[0]) is not str or not paragraph[0] or type(paragraph[1]) is not list or
                any(type(sentence) is not str for sentence in paragraph[1])):
            raise ValueError('invalid_context')
        title, sentences = paragraph
        doc_id = content_hash([title, sentences])
        documents.append({'doc_id': doc_id, 'title': title, 'sentences': sentences,
                          'character_count': sum(map(len, sentences))})
        by_title.setdefault(title, []).append(documents[-1])
    if len({document['doc_id'] for document in documents}) != 10:
        raise ValueError('duplicate_packet_content')
    support = row.get('supporting_facts')
    if type(support) is not list:
        raise ValueError('invalid_support_reference')
    for pair in support:
        if (type(pair) is not list or len(pair) != 2 or type(pair[0]) is not str or
                type(pair[1]) is not int or pair[0] not in by_title):
            raise ValueError('invalid_support_reference')
        if len(by_title[pair[0]]) != 1:
            raise ValueError('ambiguous_support_title')
        if not 0 <= pair[1] < len(by_title[pair[0]][0]['sentences']):
            raise ValueError('invalid_support_reference')
    return documents, {'task_id': row['_id'], 'answer': row['answer'], 'supporting_facts': support}


def _identity(path: Path) -> dict:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'bytes': Path(path).stat().st_size}


def _write_rows(path: Path, rows) -> None:
    """Publish one canonical sorted store after durable streaming output."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('wb', dir=path.parent, delete=False,
                                     prefix=f'.{path.name}.', suffix='.tmp') as stream:
        temporary = Path(stream.name)
        for row in rows:
            stream.write(canonical_bytes(row) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _reservations(training: list[str], protected: list[str]) -> dict:
    fit_pool = training[192:]
    prefixes = {}
    size = 256
    while len(fit_pool) >= size:
        prefixes[str(size)] = fit_pool[:size]
        size *= 2
    if fit_pool and str(len(fit_pool)) not in prefixes:
        prefixes[str(len(fit_pool))] = fit_pool
    return {'pilot': training[:64], 'tune': training[64:192], 'fit': training[192:448],
            'fit_extension': training[448:], 'fit_prefixes': prefixes,
            'protected': sorted(protected), 'active_pilot': training[:32]}


def prepare(train_path: Path, dev_path: Path, output_dir: Path,
            split_seed: int = 20261014) -> dict:
    """Prepare local raw files. CLI additionally attaches verified acquisition provenance."""
    return _prepare(train_path, dev_path, output_dir, split_seed)


def _prepare(train_path, dev_path, output_dir, split_seed, provenance=None):
    if type(split_seed) is not int:
        raise ValueError('split seed must be an integer')
    started = time.perf_counter()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        raise ValueError('prepared manifest already exists; use a fresh output directory')
    source_paths = {'train': Path(train_path), 'dev': Path(dev_path)}
    sources = {source: {'path': str(path.resolve()), **_identity(path),
                        'source_label': 'local_raw_unverified', **(provenance or {}).get(source, {})}
               for source, path in source_paths.items()}
    # Temporary annotation-bearing SQLite is never used by serving and never published.
    with tempfile.TemporaryDirectory(prefix='.conversion-', dir=output) as temporary:
        db = sqlite3.connect(str(Path(temporary) / 'staging.sqlite'))
        try:
            db.executescript('''
                PRAGMA cache_size=-8192;
                PRAGMA temp_store=FILE;
                CREATE TABLE raw(source TEXT, ordinal INTEGER, task_id TEXT, group_key TEXT,
                                 order_hash TEXT, question TEXT, candidates TEXT, gold TEXT, reason TEXT);
                CREATE INDEX raw_id ON raw(task_id);
                CREATE INDEX raw_group ON raw(source, group_key);
                CREATE TABLE documents(doc_id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE selected(task_id TEXT PRIMARY KEY, split TEXT);
                CREATE TABLE exclusions(source TEXT, ordinal INTEGER, task_id TEXT, reason TEXT);
            ''')
            raw_counts = Counter()
            max_record_bytes = 0
            for source, path in source_paths.items():
                for ordinal, row in enumerate(_raw_rows(path), 1):
                    raw_counts[source] += 1
                    # ensure_ascii also measures/retains malformed surrogate strings safely.
                    max_record_bytes = max(max_record_bytes, len(json.dumps(row).encode('utf-8')))
                    identifier = row.get('_id') if type(row) is dict else None
                    identifier = identifier if type(identifier) is str else None
                    if identifier is not None:
                        identifier = identifier.encode('utf-8', errors='backslashreplace').decode('utf-8')
                    try:
                        documents, gold = _convert(row)
                    except ValueError as error:
                        db.execute('INSERT INTO raw(source,ordinal,task_id,reason) VALUES(?,?,?,?)',
                                   (source, ordinal, identifier, str(error)))
                    else:
                        key = normalize_question(row['question'])
                        db.execute('INSERT INTO raw VALUES(?,?,?,?,?,?,?,?,NULL)',
                                   (source, ordinal, identifier, key, content_hash([split_seed, key]),
                                    row['question'], canonical_bytes([d['doc_id'] for d in documents]).decode(),
                                    canonical_bytes(gold).decode()))
                        db.executemany('INSERT OR IGNORE INTO documents VALUES(?,?)',
                                       [(d['doc_id'], canonical_bytes(d).decode()) for d in documents])
                    if ordinal % 1000 == 0:
                        db.commit()
            db.commit()
            db.execute('''INSERT INTO exclusions SELECT source,ordinal,task_id,reason FROM raw
                          WHERE reason IS NOT NULL''')
            db.execute('''INSERT INTO exclusions SELECT source,ordinal,task_id,'duplicate_id' FROM raw
                          WHERE task_id IN (SELECT task_id FROM raw WHERE task_id IS NOT NULL
                                            GROUP BY task_id HAVING COUNT(*) > 1)''')
            db.execute('''UPDATE raw SET reason='duplicate_id' WHERE task_id IN
                          (SELECT task_id FROM raw WHERE task_id IS NOT NULL GROUP BY task_id HAVING COUNT(*) > 1)''')
            validated = dict(db.execute("SELECT source,COUNT(*) FROM raw WHERE reason IS NULL GROUP BY source"))
            db.execute('''INSERT INTO exclusions SELECT source,ordinal,task_id,'protected_question_overlap'
                          FROM raw WHERE source='train' AND reason IS NULL AND group_key IN
                          (SELECT group_key FROM raw WHERE source='dev' AND reason IS NULL)''')
            removed = db.execute("SELECT COUNT(*) FROM exclusions WHERE reason='protected_question_overlap'").fetchone()[0]
            db.execute('''UPDATE raw SET reason='protected_question_overlap' WHERE source='train'
                          AND reason IS NULL AND group_key IN
                          (SELECT group_key FROM raw WHERE source='dev' AND reason IS NULL)''')
            training = [row[0] for row in db.execute('''SELECT MIN(task_id) FROM raw
                WHERE source='train' AND reason IS NULL GROUP BY group_key ORDER BY order_hash,group_key''')]
            protected = [row[0] for row in db.execute('''SELECT MIN(task_id) FROM raw
                WHERE source='dev' AND reason IS NULL GROUP BY group_key ORDER BY MIN(task_id)''')]
            overlap = db.execute('''SELECT COUNT(DISTINCT train.group_key) FROM raw train JOIN raw dev
                ON train.group_key=dev.group_key WHERE train.source='train' AND dev.source='dev'
                AND train.reason IS NULL AND dev.reason IS NULL''').fetchone()[0]
            reserves = _reservations(training, protected)
            for split, ids in [('pilot', reserves['active_pilot']), ('pilot_reservation', reserves['pilot'][32:]),
                               ('tune', reserves['tune']), ('fit', reserves['fit']),
                               ('fit_extension', reserves['fit_extension']), ('protected', protected)]:
                db.executemany('INSERT INTO selected VALUES(?,?)', [(task_id, split) for task_id in ids])
            db.commit()

            def tasks():
                for task_id, split, question, candidates in db.execute('''SELECT raw.task_id,split,question,candidates
                    FROM raw JOIN selected ON raw.task_id=selected.task_id ORDER BY raw.task_id'''):
                    yield {'task_id': task_id, 'split': split, 'question': question,
                           'candidate_ids': json.loads(candidates)}

            _write_rows(output / 'tasks.jsonl', tasks())
            # Export only documents belonging to representatives, not rejected/duplicate member packets.
            db.execute('CREATE TABLE needed_documents(doc_id TEXT PRIMARY KEY)')
            for row in db.execute('SELECT candidates FROM raw JOIN selected ON raw.task_id=selected.task_id'):
                db.executemany('INSERT OR IGNORE INTO needed_documents VALUES(?)', [(d,) for d in json.loads(row[0])])
            _write_rows(output / 'documents.jsonl', (json.loads(row[0]) for row in db.execute('''
                SELECT payload FROM documents JOIN needed_documents USING(doc_id) ORDER BY doc_id''')))
            _write_rows(output / 'gold' / 'gold.jsonl', (json.loads(row[0]) for row in db.execute('''
                SELECT gold FROM raw JOIN selected ON raw.task_id=selected.task_id ORDER BY raw.task_id''')))
            _write_rows(output / 'exclusions.jsonl', ({'source': source, 'source_row': ordinal,
                         'task_id': task_id, 'reason': reason} for source, ordinal, task_id, reason in
                db.execute('SELECT * FROM exclusions ORDER BY task_id,source,ordinal,reason')))

            def membership():
                for source, key, representative, reason in db.execute('''SELECT source,group_key,MIN(task_id),reason
                    FROM raw WHERE group_key IS NOT NULL AND (reason IS NULL OR reason='protected_question_overlap')
                    GROUP BY source,group_key ORDER BY source,group_key'''):
                    members = [r[0] for r in db.execute('''SELECT task_id FROM raw WHERE source=? AND group_key=?
                        AND (reason IS NULL OR reason='protected_question_overlap') ORDER BY task_id''', (source, key))]
                    yield {'source': source, 'group_key_hash': content_hash(key),
                           'representative_id': representative, 'member_ids': members,
                           'disposition': 'removed_protected_overlap' if reason else 'retained'}

            _write_rows(output / 'duplicate-membership.jsonl', membership())
            reason_counts = dict(db.execute('SELECT reason,COUNT(*) FROM exclusions GROUP BY reason ORDER BY reason'))
            document_count = db.execute('SELECT COUNT(*) FROM needed_documents').fetchone()[0]
            # Titles/entities are diagnostics only: no exclusion based on shared titles.
            title_sets = {'train': set(), 'dev': set()}
            for source, candidates in db.execute('''SELECT source,candidates FROM raw JOIN selected
                ON raw.task_id=selected.task_id'''):
                for doc_id in json.loads(candidates):
                    payload = db.execute('SELECT payload FROM documents WHERE doc_id=?', (doc_id,)).fetchone()[0]
                    title_sets[source].add(json.loads(payload)['title'])
            counts = {'raw_train_rows': raw_counts['train'], 'raw_dev_rows': raw_counts['dev'],
                      'validated_train_rows': validated.get('train', 0), 'validated_dev_rows': validated.get('dev', 0),
                      'removed_training_rows': removed, 'training_groups': len(training),
                      'protected_population': len(protected), 'documents': document_count,
                      'exact_question_overlap_after_removal': overlap,
                      'shared_exact_titles': len(title_sets['train'] & title_sets['dev']),
                      'train_titles': len(title_sets['train']), 'protected_titles': len(title_sets['dev']),
                      'exclusion_reasons': reason_counts}
        finally:
            db.close()
    atomic_json(output / 'protected-population.json', {'N': len(protected), 'task_ids': protected})
    atomic_json(output / 'development-reservations.json', reserves)
    file_names = ['tasks.jsonl', 'documents.jsonl', 'gold/gold.jsonl', 'exclusions.jsonl',
                  'duplicate-membership.jsonl', 'protected-population.json', 'development-reservations.json']
    identities = {name: _identity(output / name) for name in file_names}
    manifest = {'schema_version': 1, 'status': 'prepared', 'split_seed': split_seed,
                'sources': sources, 'counts': counts, 'reservations': reserves, 'files': identities,
                'rules': {'document_id': 'sha256 canonical [title, original_sentences]',
                          'group_key': 'NFC then casefold then whitespace collapse',
                          'order': 'sha256 canonical [split_seed, group_key], then group_key',
                          'representative': 'minimum task_id', 'duplicate_id': 'reject every occurrence',
                          'annotation_boundary': 'serving imports data_runtime directly',
                          'entity_overlap': 'exact titles reported; entity linking not performed'},
                'measurement': {'conversion_seconds': time.perf_counter() - started,
                                'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
                                'max_raw_record_json_bytes': max_record_bytes,
                                'parser_chunk_characters': 65536, 'sqlite_cache_bytes': 8192 * 1024,
                                'raw_bytes': sum(source['bytes'] for source in sources.values()),
                                'prepared_bytes': sum(identity['bytes'] for identity in identities.values()),
                                'reader_loaded': False}}
    manifest['fingerprint'] = content_hash({key: value for key, value in manifest.items() if key != 'measurement'})
    atomic_json(output / 'manifest.json', manifest)
    return manifest


def audit_data(prepared_dir: Path) -> dict:
    """Verify frozen store identities, runtime schema, split isolation and gold references."""
    output = Path(prepared_dir)
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    fingerprint = content_hash({key: value for key, value in manifest.items() if key not in {'measurement', 'fingerprint'}})
    if fingerprint != manifest['fingerprint']:
        raise ValueError('manifest fingerprint hash mismatch')
    for name, expected in manifest['files'].items():
        if _identity(output / name) != expected:
            raise ValueError(f'prepared file hash mismatch: {name}')
    store = DocumentStore(output / 'documents.jsonl')
    tasks, questions, splits = {}, {'train': set(), 'protected': set()}, Counter()
    for row in read_jsonl(output / 'tasks.jsonl'):
        task = _record(row, Task)
        if task.task_id in tasks:
            raise ValueError('duplicate task ID')
        tasks[task.task_id] = task
        if any(doc_id not in store.offsets for doc_id in task.candidate_ids):
            raise ValueError('unknown task document')
        side = 'protected' if task.split == 'protected' else 'train'
        questions[side].add(normalize_question(task.question))
        splits[task.split] += 1
    overlap = len(questions['train'] & questions['protected'])
    if overlap:
        raise ValueError('training/protected exact-question overlap')
    reserves = manifest['reservations']
    expected_splits = {'pilot': reserves['active_pilot'], 'pilot_reservation': reserves['pilot'][32:],
                       'tune': reserves['tune'], 'fit': reserves['fit'],
                       'fit_extension': reserves['fit_extension'], 'protected': reserves['protected']}
    for split, identifiers in expected_splits.items():
        if sorted(task.task_id for task in tasks.values() if task.split == split) != sorted(identifiers):
            raise ValueError(f'reservation mismatch: {split}')
    if len(tasks) != sum(map(len, expected_splits.values())):
        raise ValueError('unexpected task partition')
    gold_ids = set()
    for row in read_jsonl(output / 'gold' / 'gold.jsonl'):
        if set(row) != {'task_id', 'answer', 'supporting_facts'} or type(row['answer']) is not str:
            raise ValueError('invalid gold fields')
        task_id = row['task_id']
        if task_id not in tasks or task_id in gold_ids:
            raise ValueError('gold/task ID mismatch')
        gold_ids.add(task_id)
        documents = [store.get(doc_id) for doc_id in tasks[task_id].candidate_ids]
        if type(row['supporting_facts']) is not list:
            raise ValueError('invalid gold support')
        for pair in row['supporting_facts']:
            if (type(pair) is not list or len(pair) != 2 or type(pair[0]) is not str or type(pair[1]) is not int):
                raise ValueError('invalid gold support')
            matching = [document for document in documents if document.title == pair[0]]
            if len(matching) != 1 or not 0 <= pair[1] < len(matching[0].sentences):
                raise ValueError('invalid gold support')
    if gold_ids != set(tasks):
        raise ValueError('missing gold task')
    return {'status': 'ok', 'fingerprint': fingerprint, 'N': splits['protected'],
            'task_count': len(tasks), 'document_count': len(store.offsets),
            'split_counts': dict(sorted(splits.items())), 'exact_question_overlap_after_removal': overlap,
            'exclusion_reasons': manifest['counts']['exclusion_reasons'],
            'sources': manifest['sources']}


def main(args) -> int:
    config = json.loads(Path(args.config).read_text(encoding='utf-8'))
    settings = config.get('preparation', {})
    output = Path(settings.get('output_dir', 'data/prepared'))
    if args.command == 'prepare':
        train = Path(settings.get('train_path', 'models/pinned/data/hotpot_train_v1.1.json'))
        dev = Path(settings.get('dev_path', 'models/pinned/data/hotpot_dev_distractor_v1.json'))
        provenance = {}
        asset_path = Path(settings.get('asset_manifest', 'artifacts/provenance/asset-manifest.json'))
        if asset_path.exists():
            assets = json.loads(asset_path.read_text(encoding='utf-8'))['assets']
            for source, name, path in [('train', 'hotpot_train', train), ('dev', 'hotpot_dev_distractor', dev)]:
                asset = assets[name]
                if (Path(asset['local_path']) / path.name).resolve() != path.resolve() or asset['files'][path.name] != _identity(path):
                    raise ValueError('raw file does not match pinned asset identity')
                provenance[source] = {key: asset[key] for key in
                    ('source_policy', 'source_amendment', 'source_url', 'requested_url', 'final_url',
                     'archive_capture', 'integrity_limitation', 'license', 'provenance_url') if key in asset}
                provenance[source]['source_label'] = 'archived_author_origin_raw_snapshot' if asset.get('archive_capture') else 'direct_author_raw'
        result = _prepare(train, dev, output, config.get('seeds', {}).get('split', 20261014), provenance)
    else:
        result = audit_data(output)
        atomic_json(output / 'audit.json', result)
    print(json.dumps({'status': result['status'], 'fingerprint': result['fingerprint'],
                      'counts': result.get('counts', result.get('split_counts')), 'N': result.get('N', result.get('counts', {}).get('protected_population'))},
                     sort_keys=True, allow_nan=False))
    return 0

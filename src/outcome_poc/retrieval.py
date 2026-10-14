"""Shared annotation-free CPU paragraph indexing and deterministic ranking."""
from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import threading
import time
import uuid

import numpy as np

from .assets import file_identity, verify_assets
from .data_runtime import DocumentStore, load_tasks
from .environment import resource_gate
from .schemas import Document, RankedDocument, validate_record
from .storage import append_jsonl, atomic_json, canonical_bytes, content_hash, read_jsonl

QUERY_PREFIX = 'Represent this sentence for searching relevant passages: '
QUERY_LIMIT = 512
WINDOW_LIMIT = 480
LOGGER = logging.getLogger(__name__)


def validate_vectors(values: np.ndarray, rows: int) -> np.ndarray:
    if not isinstance(values, np.ndarray) or values.shape != (rows, 384):
        raise ValueError('encoder must produce 384-dimensional rows')
    if values.dtype != np.float32 or not np.isfinite(values).all():
        raise ValueError('encoder rows must be finite float32')
    if not np.allclose(np.linalg.norm(values, axis=1), 1.0, atol=1e-5):
        raise ValueError('encoder rows must be normalized')
    return values


class EncoderBackend:
    def __init__(self, snapshot: Path):
        if not isinstance(snapshot, Path) or not snapshot.is_dir():
            raise ValueError('encoder requires an existing local snapshot Path')
        from sentence_transformers import SentenceTransformer
        files = {str(p.relative_to(snapshot)): file_identity(p) for p in snapshot.rglob('*')
                 if p.is_file() and '.cache' not in p.relative_to(snapshot).parts}
        self.identity = {'revision': snapshot.name, 'snapshot_hash': content_hash(files)}
        self.model = SentenceTransformer(str(snapshot.resolve()), device='cpu', local_files_only=True,
                                         trust_remote_code=False, model_kwargs={'use_safetensors': True})
        self.model.float()
        self.model.eval()
        self.tokenizer = self.model.tokenizer
        self.query_max_tokens = QUERY_LIMIT
        self.model.max_seq_length = QUERY_LIMIT
        if self.tokenizer.truncation_side != 'right':
            raise ValueError('encoder tokenizer must use right truncation')
        self.batch_size = 1
        self.batch_measurements = []

    def encode(self, texts: list[str]) -> np.ndarray:
        if type(texts) is not list or any(type(text) is not str for text in texts):
            raise ValueError('encoder expects list[str]')
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        values = self.model.encode(texts, batch_size=self.batch_size,
                                   normalize_embeddings=True, convert_to_numpy=True,
                                   precision='float32', device='cpu', show_progress_bar=False)
        return validate_vectors(values, len(texts))

    def select_batch_size(self, longest_text: str) -> None:
        """Measure conservative full-length CPU batches before the indexing pass."""
        import psutil
        process = psutil.Process()
        physical = psutil.virtual_memory().total
        for size in (1, 8, 16, 32):
            # Do not launch a larger probe unless the previous peak leaves room for
            # a conservative linear bound on the entire next batch working set.
            if self.batch_measurements:
                previous = self.batch_measurements[-1]
                bound = previous['sampled_peak_rss_bytes'] * size / previous['batch_size']
                if not resource_gate(physical, int(bound))['passed']:
                    break
            self.batch_size = size
            peak = [process.memory_info().rss]
            done = threading.Event()
            def monitor():
                while not done.wait(.01):
                    peak[0] = max(peak[0], process.memory_info().rss)
            worker = threading.Thread(target=monitor, daemon=True)
            worker.start()
            start = time.perf_counter()
            try:
                self.encode([longest_text] * size)
            finally:
                done.set()
                worker.join()
                peak[0] = max(peak[0], process.memory_info().rss)
                gate = resource_gate(physical, peak[0])
                self.batch_measurements.append({'batch_size': size, 'seconds': time.perf_counter() - start,
                                                'sampled_peak_rss_bytes': peak[0], 'resource_gate': gate})
            if not gate['passed']:
                raise ValueError('CPU encoder memory reserve failed')


def _count(tokenizer: object, text: str) -> int:
    return len(tokenizer(text, add_special_tokens=True, truncation=False)['input_ids'])


def embedding_windows(document: Document, tokenizer: object, max_tokens: int = WINDOW_LIMIT) -> list[dict]:
    """Pack original sentences; recount offset-based overlong fragments with title."""
    if type(max_tokens) is not int or max_tokens < 3:
        raise ValueError('invalid window token limit')
    if _count(tokenizer, document.title) >= max_tokens:
        raise ValueError('title overhead leaves no body-token capacity')
    windows, pieces, spans = [], [], []

    def composed(parts):
        return document.title + '\n' + '\n'.join(parts)

    def flush():
        if spans:
            text = composed(pieces)
            windows.append({'text': text, 'token_count': _count(tokenizer, text),
                            'spans': list(spans), 'vector_offset': len(windows)})
            pieces.clear()
            spans.clear()

    for index, sentence in enumerate(document.sentences):
        tokens = tokenizer(sentence, add_special_tokens=False, truncation=False,
                           return_offsets_mapping=True)
        offsets = tokens['offset_mapping']
        count = len(tokens['input_ids'])
        full_span = {'sentence_index': index, 'token_start': 0, 'token_end': count,
                     'char_start': 0, 'char_end': len(sentence)}
        if _count(tokenizer, composed(pieces + [sentence])) <= max_tokens:
            pieces.append(sentence)
            spans.append(full_span)
            continue
        flush()
        if _count(tokenizer, composed([sentence])) <= max_tokens:
            pieces.append(sentence)
            spans.append(full_span)
            continue
        capacity = max_tokens - _count(tokenizer, document.title)
        start = 0
        while start < count:
            end = min(start + capacity, count)
            char_start = 0 if start == 0 else offsets[start][0]
            while end > start:
                char_end = offsets[end][0] if end < count else len(sentence)
                fragment = sentence[char_start:char_end]
                if _count(tokenizer, composed([fragment])) <= max_tokens:
                    break
                end -= 1
            if end == start:
                raise ValueError('original token fragment cannot fit title-inclusive window')
            pieces.append(fragment)
            spans.append({'sentence_index': index, 'token_start': start, 'token_end': end,
                          'char_start': char_start, 'char_end': char_end})
            start = end
            if start < count:
                flush()
    flush()
    if not windows:
        raise ValueError('document has no indexable sentences')
    return windows


def _query_convention(encoder) -> dict:
    return {'prefix': QUERY_PREFIX, 'max_tokens': QUERY_LIMIT, 'truncation_side': 'right',
            'strategy': 'single_text_right_truncation_preserving_special_tokens',
            'lengths_include_special_tokens': True, 'document_prefix': '',
            'window_max_tokens': WINDOW_LIMIT, 'window_separator': '\n',
            'fragment_convention': 'original_character_offsets_recount_composed_single_text',
            'tokenizer_class': type(encoder.tokenizer).__name__,
            'special_tokens': encoder.tokenizer('', add_special_tokens=True)['input_ids']}


def _completed_manifest(index_dir: Path) -> dict:
    """Read the shared physical commit predicate without modifying its artifacts."""
    try:
        manifest = json.loads((index_dir / 'manifest.json').read_text())
        completion = manifest.get('completion', {})
        if manifest.get('format_version') != 2 or completion.get('status') != 'complete':
            raise ValueError('index completion is missing')
        attempts = list(read_jsonl(Path(completion['attempt_ledger'])))
        matching = [row for row in attempts if row['attempt_id'] == completion['attempt_id']]
        if (len(matching) != 1 or matching[0]['status'] != 'ok' or
                matching[0].get('manifest_hash') != content_hash(manifest)):
            raise ValueError('index completion attempt is not successful')
        if completion['scope'] == 'cli':
            provenance = json.loads(Path(completion['provenance_path']).read_text())
            if provenance != manifest:
                raise ValueError('index completion provenance mismatch')
        elif completion['scope'] != 'selected_documents':
            raise ValueError('index completion scope is unsupported')
        for name, expected in manifest['files'].items():
            if file_identity(index_dir / name) != expected:
                raise ValueError('index file digest mismatch')
    except (OSError, KeyError, ValueError) as error:
        raise ValueError(f'index completion unavailable: {error}') from error
    return manifest


class _IndexAttempt:
    """Keep payload completion separate from append-only, post-boundary cost telemetry."""

    def __init__(self, output_dir: Path, ledger: Path, scope: str, split=None):
        self.started = self.stage_started = time.perf_counter()
        self.started_utc = datetime.now(timezone.utc).isoformat()
        self.attempt_id = uuid.uuid4().hex
        self.output_dir, self.ledger = Path(output_dir), Path(ledger)
        self.scope, self.split = scope, split
        self.stage, self.stage_seconds = 'setup', {}
        self.manifest, self.provenance = None, None
        self.record = None

    def mark(self, stage):
        now = time.perf_counter()
        self.stage_seconds[self.stage] = self.stage_seconds.get(self.stage, 0.) + now - self.stage_started
        self.stage, self.stage_started = stage, now

    def __enter__(self):
        return self

    def publish(self, manifest: dict, provenance: Path | None = None):
        self.manifest, self.provenance = manifest, provenance
        manifest['completion'] = {'status': 'complete', 'scope': self.scope,
                                  'attempt_id': self.attempt_id, 'attempt_ledger': str(self.ledger.resolve())}
        if provenance is not None:
            manifest['completion']['provenance_path'] = str(provenance.resolve())
            self.mark('provenance_publication')
            atomic_json(provenance, manifest)
        self.mark('manifest_publication')
        atomic_json(self.output_dir / 'manifest.json', manifest)

    def _revoke_completion(self):
        path = self.output_dir / 'manifest.json'
        try:
            if json.loads(path.read_text()).get('completion', {}).get('attempt_id') == self.attempt_id:
                path.unlink()
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            LOGGER.error('could not revoke failed index completion: %s', error)

    def _partial_bytes(self):
        partial, errors, provenance_bytes = {}, [], 0
        try:
            for path in self.output_dir.rglob('*'):
                if path.is_file():
                    try:
                        partial[str(path.relative_to(self.output_dir))] = path.stat().st_size
                    except OSError as error:
                        errors.append(str(error))
        except OSError as error:
            errors.append(str(error))
        if self.provenance is not None:
            try:
                provenance_bytes = self.provenance.stat().st_size
            except FileNotFoundError:
                pass
            except OSError as error:
                provenance_bytes = None
                errors.append(str(error))
        return {'index_files': partial, 'index_total': sum(partial.values()),
                'required_provenance': provenance_bytes, 'measurement_errors': errors}

    def __exit__(self, error_type, error, traceback):
        if error_type:
            self._revoke_completion()
        # Stop after required publication (or failure/rollback); byte snapshots,
        # cost-ledger telemetry and console presentation are separate afterward.
        stopped = time.perf_counter()
        self.stage_seconds[self.stage] = self.stage_seconds.get(self.stage, 0.) + stopped - self.stage_started
        self.record = {'attempt_id': self.attempt_id, 'scope': self.scope, 'split': self.split,
                       'started_utc': self.started_utc, 'status': 'failed' if error_type else 'ok',
                       'terminal_stage': self.stage, 'elapsed_seconds': stopped - self.started,
                       'stage_seconds': self.stage_seconds, 'partial_bytes': self._partial_bytes(),
                       'excluded_after_boundary': ['attempt_telemetry_publication', 'console_summary']}
        if error_type:
            self.record['error_type'] = error_type.__name__
            self.record['error'] = str(error)
        elif self.manifest is not None:
            self.record['manifest_hash'] = content_hash(self.manifest)
        try:
            append_jsonl(self.ledger, self.record)
        except Exception as telemetry_error:
            if error_type is None and self.manifest is not None:
                try:
                    committed = _completed_manifest(self.output_dir) == self.manifest
                except ValueError:
                    committed = False
                if committed:
                    # Required payload/provenance and the unique success row are
                    # physically committed. A later flush/sync fault is telemetry,
                    # not a failed index invocation; rollback would contradict the
                    # same immutable completion predicate used by readers.
                    self.record['post_commit_telemetry_fault'] = str(telemetry_error)
                    LOGGER.warning('index committed; post-commit telemetry fault: %s; record=%s',
                                   telemetry_error, canonical_bytes(self.record).decode())
                    return False
            # No valid physical commit exists. Preserve failure/rollback costs.
            # A write may have reached disk before fsync failed. Revoke the owned
            # manifest and append a failed record so that such a row cannot pass
            # constructor checks. Include the failed telemetry/rollback work.
            self._revoke_completion()
            self.record.update(status='failed', elapsed_seconds=time.perf_counter() - self.started,
                               telemetry_error=str(telemetry_error), partial_bytes=self._partial_bytes(),
                               excluded_after_boundary=['attempt_telemetry_retry_publication', 'console_summary'])
            self.stage_seconds['attempt_telemetry'] = self.record['elapsed_seconds'] - (stopped - self.started)
            self.record.pop('manifest_hash', None)
            if error_type is None:
                self.record.update(terminal_stage='attempt_telemetry', error_type=type(telemetry_error).__name__,
                                   error=str(telemetry_error))
            try:
                append_jsonl(self.ledger, self.record)
            except Exception as retry_error:
                LOGGER.error('index attempt telemetry persistence failed: %s; record=%s', retry_error,
                             canonical_bytes(self.record).decode())
            if error_type is None:
                raise
        return False


def build_index(documents: Iterable[Document], encoder: EncoderBackend, output_dir: Path, *, reuse_indexes=()) -> dict:
    """Build selected documents; publish completion and preserve every attempt cost."""
    output_dir = Path(output_dir)
    with _IndexAttempt(output_dir, output_dir.parent / 'index-attempts.jsonl', 'selected_documents') as attempt:
        manifest = _build_index_payload(documents, encoder, output_dir, attempt, reuse_indexes=reuse_indexes)
        attempt.publish(manifest)
    return manifest


def _build_index_payload(documents, encoder, output_dir, attempt, *, reuse_indexes=()) -> dict:
    """Deduplicate once on disk; bounded encoding calls write rows into a memmap."""
    attempt.mark("output_validation")
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError('index directory already exists and is nonempty')
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    database = output_dir / 'metadata.sqlite3'
    rows = 0
    reused, reuse_sources = {}, []
    # Source completion, exact encoder and tokenizer/window conventions are
    # prerequisites. Keys bind document identity and every stored window field.
    for source_path in reuse_indexes:
        source_path = Path(source_path)
        source = _completed_manifest(source_path)
        expected_encoder = dict(encoder.identity, dimensions=384, device='cpu', precision='float32', normalized=True)
        if source['encoder'] != expected_encoder or source['query_convention'] != _query_convention(encoder):
            raise ValueError('cross-index encoder/tokenizer identity mismatch')
        source_vectors = np.memmap(source_path/'vectors.f32', dtype=np.float32, mode='r', shape=(source['window_count'], 384))
        with sqlite3.connect(source_path/'metadata.sqlite3') as source_db:
            for offset, doc_id, spans, tokens, text_hash in source_db.execute('SELECT vector_offset,doc_id,spans,token_count,text_hash FROM windows'):
                key = (doc_id, spans, tokens, text_hash)
                reused.setdefault(key, (source_vectors, offset))
        reuse_sources.append({'path': str(source_path), 'manifest_hash': content_hash(source),
                              'attempt_id': source['completion']['attempt_id'], 'vector_sha256': source['files']['vectors.f32']['sha256']})
    reused_offsets = {}
    document_digest = hashlib.sha256()
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE documents (doc_id TEXT PRIMARY KEY, title TEXT, character_count INTEGER, sentence_count INTEGER, vector_start INTEGER, window_count INTEGER)')
        db.execute('CREATE TABLE windows (vector_offset INTEGER PRIMARY KEY, doc_id TEXT, spans TEXT, token_count INTEGER, text_hash TEXT)')
        db.execute('CREATE TABLE pending_texts (vector_offset INTEGER PRIMARY KEY, text TEXT)')
        db.execute('PRAGMA cache_size=-8192')
        for document in documents:
            attempt.mark('document_validation')
            validate_record(document)
            if document.doc_id != content_hash([document.title, document.sentences]):
                raise ValueError('document content hash mismatch')
            if document.character_count != sum(map(len, document.sentences)):
                raise ValueError('document character count mismatch')
            if db.execute('SELECT 1 FROM documents WHERE doc_id=?', (document.doc_id,)).fetchone():
                continue
            attempt.mark('windows')
            try:
                windows = embedding_windows(document, encoder.tokenizer)
            except ValueError as error:
                atomic_json(output_dir / 'errors.json', {'doc_id': document.doc_id, 'stage': 'windows', 'error': str(error)})
                LOGGER.error('indexing error for %s: %s', document.doc_id, error)
                raise
            db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?)',
                       (document.doc_id, document.title, len(document.title) + document.character_count,
                        len(document.sentences), rows, len(windows)))
            for window in windows:
                spans = canonical_bytes(window['spans']).decode()
                text_hash = content_hash(window['text'])
                db.execute('INSERT INTO windows VALUES (?,?,?,?,?)',
                           (rows, document.doc_id, spans, window['token_count'], text_hash))
                key = (document.doc_id, spans, window['token_count'], text_hash)
                if key in reused:
                    reused_offsets[rows] = reused[key]
                else:
                    db.execute('INSERT INTO pending_texts VALUES (?,?)', (rows, window['text']))
                rows += 1
        if not rows:
            raise ValueError('cannot build empty index')
        for (doc_id,) in db.execute('SELECT doc_id FROM documents ORDER BY doc_id'):
            document_digest.update(canonical_bytes(doc_id) + b'\n')
        attempt.mark('calibration')
        selector = getattr(encoder, 'select_batch_size', None)
        if selector:
            longest = db.execute('SELECT p.text FROM pending_texts p JOIN windows w USING(vector_offset) ORDER BY w.token_count DESC LIMIT 1').fetchone()
            if longest:
                selector(longest[0])
        attempt.mark('encoding')
        vectors = np.memmap(output_dir / 'vectors.f32', dtype=np.float32, mode='w+', shape=(rows, 384))
        batch_size = encoder.batch_size
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError('invalid measured encoder batch size')
        for offset, (source_vectors, source_offset) in reused_offsets.items():
            vectors[offset] = validate_vectors(np.asarray(source_vectors[source_offset:source_offset+1]), 1)[0]
        pending = db.execute('SELECT vector_offset,text FROM pending_texts ORDER BY vector_offset')
        while True:
            batch = pending.fetchmany(batch_size)
            if not batch:
                break
            texts = [item[1] for item in batch]
            values = validate_vectors(encoder.encode(texts), len(texts))
            for (offset, _), value in zip(batch, values):
                vectors[offset] = value
        attempt.mark('metadata_finalization')
        vectors.flush()
        del vectors
        db.execute('DROP TABLE pending_texts')
        db.commit()
        db.execute('VACUUM')
        document_count = db.execute('SELECT count(*) FROM documents').fetchone()[0]
    attempt.mark('payload_fingerprints')
    files = {name: file_identity(output_dir / name) for name in ('metadata.sqlite3', 'vectors.f32')}
    manifest = {'format_version': 2, 'encoder': dict(encoder.identity, dimensions=384, device='cpu', precision='float32', normalized=True),
                'document_count': document_count, 'window_count': rows,
                'document_ids_digest': document_digest.hexdigest(), 'files': files,
                'query_convention': _query_convention(encoder),
                'offline': {'seconds': time.perf_counter() - started, 'vector_bytes': files['vectors.f32']['bytes'],
                            'metadata_bytes': files['metadata.sqlite3']['bytes'],
                            'bytes': sum(f['bytes'] for f in files.values()),
                            'reused_window_count': len(reused_offsets), 'encoded_window_count': rows-len(reused_offsets),
                            'reuse_sources': reuse_sources,
                            'batch_size': batch_size, 'batch_measurements': encoder.batch_measurements}}
    return manifest


class Retrieval:
    def __init__(self, index_dir: Path, documents: DocumentStore, encoder: EncoderBackend):
        self.index_dir = Path(index_dir)
        self.documents, self.encoder = documents, encoder
        self.manifest = _completed_manifest(self.index_dir)
        if any(self.manifest['encoder'].get(k) != v for k, v in encoder.identity.items()):
            raise ValueError('index encoder identity mismatch')
        if self.manifest['query_convention'] != _query_convention(encoder):
            raise ValueError('index encoder tokenizer convention mismatch')
        self.vectors = np.memmap(self.index_dir / 'vectors.f32', dtype=np.float32, mode='r',
                                 shape=(self.manifest['window_count'], 384))
        self.last_timings, self.last_query = {}, {}

    def rank(self, question: str, candidate_ids: list[str]) -> list[RankedDocument]:
        self.last_timings, self.last_query = {}, {}
        if type(question) is not str or not question.strip():
            raise ValueError('question must be nonempty text')
        if (type(candidate_ids) is not list or not candidate_ids or
                any(type(v) is not str for v in candidate_ids) or len(set(candidate_ids)) != len(candidate_ids)):
            raise ValueError('candidate IDs must be unique and nonempty')
        timings = self.last_timings
        started = time.perf_counter()
        text = QUERY_PREFIX + question
        tokenizer = self.encoder.tokenizer
        original = tokenizer(text, add_special_tokens=True, truncation=False)['input_ids']
        retained = tokenizer(text, add_special_tokens=True, truncation=True, max_length=QUERY_LIMIT)['input_ids']
        self.last_query = {'original_tokens': len(original), 'retained_tokens': len(retained),
                           'truncated': len(original) > len(retained), 'truncation_side': 'right',
                           'retained_ids_hash': content_hash(retained)}
        if self.last_query['truncated']:
            LOGGER.warning('query truncation: %s', json.dumps(self.last_query, sort_keys=True))
        query = validate_vectors(self.encoder.encode([text]), 1)[0]
        timings['query_encoding_seconds'] = time.perf_counter() - started
        started = time.perf_counter()
        metadata, offsets = {}, []
        with sqlite3.connect(f'file:{self.index_dir / "metadata.sqlite3"}?mode=ro', uri=True) as db:
            for doc_id in sorted(candidate_ids):
                row = db.execute('SELECT title, character_count, sentence_count, vector_start, window_count FROM documents WHERE doc_id=?', (doc_id,)).fetchone()
                if row is None:
                    raise ValueError('candidate missing from index')
                metadata[doc_id] = row
                offsets.extend(range(row[3], row[3] + row[4]))
        values = self.vectors[offsets]
        timings['vector_lookup_seconds'] = time.perf_counter() - started
        started = time.perf_counter()
        # Each row uses the same float32 reduction, independent of packet order.
        scores = np.sum(values * query, axis=1, dtype=np.float32)
        timings['dots_seconds'] = time.perf_counter() - started
        started = time.perf_counter()
        aggregated, cursor = {}, 0
        for doc_id, row in metadata.items():
            aggregated[doc_id] = float(np.max(scores[cursor:cursor + row[4]]))
            cursor += row[4]
        timings['aggregation_seconds'] = time.perf_counter() - started
        started = time.perf_counter()
        ordered = sorted(metadata, key=lambda doc_id: (-aggregated[doc_id], doc_id))
        result = [RankedDocument(doc_id, aggregated[doc_id], rank, metadata[doc_id][1],
                                 metadata[doc_id][2], metadata[doc_id][0]) for rank, doc_id in enumerate(ordered)]
        timings['sort_seconds'] = time.perf_counter() - started
        # Rank returns metadata only. The reader obtains whole originals through
        # documents.get; its actual reads are charged by the later serving wrapper.
        timings['evidence_reads_seconds'] = 0.0
        self.last_timings = timings
        return result


def main(args) -> int:
    """Index development partitions; protected scheduling belongs to later protocol work."""
    attempt = _IndexAttempt(Path('data/index') / args.split, Path('data/index/index-attempts.jsonl'), 'cli', args.split)
    with attempt:
        from .generation import offline_network
        config = json.loads(Path(args.config).read_text())
        settings = config.get('retrieval', {})
        attempt.output_dir = Path(settings.get('output_dir', 'data/index')) / args.split
        attempt.ledger = Path(config['output_dir']) / 'index-attempts.jsonl'
        attempt.mark('split_validation')
        if args.split == 'protected':
            raise ValueError('protected indexing unavailable until verified scheduled-sample integration exists')
        if args.split not in {'pilot', 'fit', 'tune'}:
            raise ValueError('index requires an active development split')
        attempt.mark('setup')
        prepared = Path(config['preparation']['output_dir'])
        tasks = load_tasks(prepared / 'tasks.jsonl', args.split)
        ids = sorted({doc_id for task in tasks for doc_id in task.candidate_ids})
        if not ids:
            raise ValueError('scheduled split has no tasks')
        documents = DocumentStore(prepared / 'documents.jsonl')
        assets = json.loads(Path(config['preparation']['asset_manifest']).read_text())
        asset = assets['assets']['encoder']
        expected = config['encoder']
        if (expected['repo_id'], expected['revision'], expected['dimensions'], expected['device'], expected['precision']) != (
                'BAAI/bge-small-en-v1.5', asset['revision'], 384, 'cpu', 'float32') or asset['repo_id'] != expected['repo_id']:
            raise ValueError('encoder configuration disagrees with pinned CPU asset')
        verify_assets({'required': ['encoder'], 'assets': {'encoder': asset}})
        with offline_network() as network_attempts:
            attempt.mark('model_load')
            model_started = time.perf_counter()
            encoder = EncoderBackend(Path(asset['local_path']))
            model_load_seconds = time.perf_counter() - model_started
            if encoder.identity != {'revision': asset['revision'], 'snapshot_hash': asset['snapshot_hash']}:
                raise ValueError('encoder snapshot identity mismatch')
            setup_seconds = time.perf_counter() - attempt.started
            reuse = (settings.get('reuse_indexes_by_split', {}).get(args.split, settings.get('reuse_indexes', []))
                     if args.split in ('fit', 'tune') else [])
            manifest = _build_index_payload((documents.get(doc_id) for doc_id in ids), encoder, attempt.output_dir, attempt, reuse_indexes=reuse)
            attempt.mark('source_fingerprints')
            manifest['scheduled_split'] = args.split
            manifest['scheduled_task_count'] = len(tasks)
            manifest['scheduled_task_ids_hash'] = content_hash(sorted(t.task_id for t in tasks))
            manifest['prepared_inputs'] = {name: file_identity(prepared / name) for name in ('tasks.jsonl', 'documents.jsonl')}
            manifest['offline']['network_attempts'] = len(network_attempts)
            manifest['offline']['model_load_seconds'] = model_load_seconds
            manifest['offline']['setup_seconds'] = setup_seconds
            attempt.publish(manifest, Path(config['output_dir']) / f'wp1-index-{args.split}.json')
    # Presentation is outside the commit/cost boundary and cannot undo it.
    try:
        print(json.dumps({'split': args.split, 'tasks': len(tasks), 'documents': manifest['document_count'],
                          'windows': manifest['window_count'], 'offline': manifest['offline'],
                          'attempt': attempt.record}, indent=2))
    except OSError as error:
        LOGGER.warning('index committed; post-commit console fault: %s', error)
    return 0

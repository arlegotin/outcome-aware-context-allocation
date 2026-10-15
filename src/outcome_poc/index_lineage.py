"""Recursive physical index dependencies and frozen append-only cost intervals.

An edge means the producer opened a source, not that every source window was
used. Successful dependency records and other observed attempts are separate.
No retained manifest, ledger or seal is ever rewritten here.
"""
import hashlib
import json
import math
import re
from pathlib import Path

from .assets import file_identity
from .retrieval import _completed_manifest
from .storage import content_hash


def _object(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate lineage JSON key: {key}')
            result[key] = value
        return result
    def reject(value):
        raise ValueError(f'nonfinite lineage JSON: {value}')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject)


def _metadata(manifest):
    if type(manifest.get('format_version')) is not int or manifest['format_version'] != 2:
        raise ValueError('unsupported index lineage schema version')
    if 'reuse_sources' in manifest:
        raise ValueError('reuse_sources belongs explicitly in offline metadata')
    payloads = manifest.get('files')
    if type(payloads) is not dict or set(payloads) != {'metadata.sqlite3','vectors.f32'}:
        raise ValueError('index lineage requires both original producer payloads')
    for identity in payloads.values():
        if (type(identity) is not dict or set(identity) != {'bytes','sha256'} or
                type(identity['bytes']) is not int or identity['bytes'] <= 0 or
                type(identity['sha256']) is not str or re.fullmatch('[0-9a-f]{64}',identity['sha256']) is None):
            raise ValueError('malformed index payload identity')
    offline = manifest.get('offline')
    if type(offline) is not dict or type(offline.get('reuse_sources')) is not list:
        raise ValueError('explicit offline.reuse_sources list required')
    counts = [manifest.get('window_count'), offline.get('reused_window_count'), offline.get('encoded_window_count')]
    if (any(type(n) is not int or n < 0 for n in counts) or counts[0] == 0 or
            counts[0] != counts[1] + counts[2] or (counts[1] and not offline['reuse_sources'])):
        raise ValueError('invalid explicit index reuse window counts')
    for reference in offline['reuse_sources']:
        if (type(reference) is not dict or set(reference) != {'path','manifest_hash','attempt_id','vector_sha256'} or
                any(type(v) is not str or not v for v in reference.values())):
            raise ValueError('malformed explicit index reuse reference')
    return offline['reuse_sources']


def capture_lineage(index_dir: Path, *, frozen: dict | None = None) -> dict:
    """Validate real producer manifests recursively, or verify a frozen inventory.

    Cost intervals are newline-aligned prefixes of each observed ledger. Reload
    verifies exactly those bytes; a later unrelated append does not retroactively
    enlarge adaptation cost. Completion predicates still reject duplicate success
    IDs and malformed current ledgers. Additional attempts are observations, not
    automatically attributable costs of a particular policy.
    """
    try:
        if frozen is not None and (type(frozen) is not dict or frozen.get('schema_version') != 1):
            raise ValueError('unsupported frozen lineage schema')
        limits = {p: v for p, v in frozen['ledger_intervals'].items()} if frozen is not None else None
        nodes, edges, files, intervals, records = {}, [], {}, {}, {}
        dependencies, active_paths, active_ids, visited, observed = {}, set(), set(), {}, {}

        def ledger(path):
            path = str(Path(path).resolve(strict=True))
            if path in intervals:
                return intervals[path]['attempts']
            raw = Path(path).read_bytes()
            if not raw or not raw.endswith(b'\n'):
                raise ValueError('incomplete index attempt ledger')
            # Authenticate the present tail without absorbing it into a frozen
            # cost interval. Conflicting IDs cannot be legitimate appends.
            current = {}
            for line in raw.splitlines():
                row = _object(line)
                if (type(row) is not dict or type(row.get('attempt_id')) is not str or not row['attempt_id'] or
                        row.get('status') not in {'ok','failed'} or
                        type(row.get('elapsed_seconds')) not in (int,float) or
                        not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds'] < 0):
                    raise ValueError('invalid index attempt cost record')
                key = row['attempt_id']
                if key in current:
                    raise ValueError('duplicate/conflicting index attempt ID in ledger')
                if key in observed and observed[key] != row:
                    raise ValueError('conflicting index attempt identities across ledgers')
                current[key] = observed[key] = row
            if limits is not None:
                if path not in limits:
                    raise ValueError('unfrozen dependency ledger')
                bound = limits[path]
                size = bound['bytes']
                if (type(size) is not int or size <= 0 or size > len(raw) or
                        hashlib.sha256(raw[:size]).hexdigest() != bound['sha256'] or raw[size-1:size] != b'\n'):
                    raise ValueError('frozen ledger prefix changed')
                raw = raw[:size]
            rows = [_object(line) for line in raw.splitlines()]
            local = {}
            for row in rows:
                if (type(row) is not dict or type(row.get('attempt_id')) is not str or not row['attempt_id'] or
                        row.get('status') not in {'ok','failed'} or
                        type(row.get('elapsed_seconds')) not in (int,float) or
                        not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds'] < 0):
                    raise ValueError('invalid index attempt cost record')
                attempt_id = row['attempt_id']
                if attempt_id in local:
                    raise ValueError('duplicate/conflicting index attempt ID in ledger')
                if attempt_id in records and records[attempt_id] != row:
                    raise ValueError('conflicting index attempt identities across ledgers')
                local[attempt_id] = row
                records[attempt_id] = row
            intervals[path] = {'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest(),
                               'attempts':local, 'record_count':len(rows)}
            return local

        def visit(path):
            path = Path(path).resolve(strict=True)
            if path in active_paths:
                raise ValueError('index reuse cycle')
            if path in visited:
                return visited[path]
            blob = (path/'manifest.json').read_bytes()
            manifest = _object(blob)
            references = _metadata(manifest)
            if _completed_manifest(path) != manifest:
                raise ValueError('index completion identity mismatch')
            completion = manifest['completion']
            attempt_id = completion['attempt_id']
            if type(attempt_id) is not str or not attempt_id:
                raise ValueError('invalid completed index attempt ID')
            if attempt_id in active_ids:
                raise ValueError('index reuse cycle in physical attempt IDs')
            digest = content_hash(manifest)
            rows = ledger(completion['attempt_ledger'])
            record = rows.get(attempt_id)
            if record is None or record['status'] != 'ok' or record.get('manifest_hash') != digest:
                raise ValueError('completed attempt not present in frozen ledger interval')
            signature = {'manifest_hash':digest, 'vector_identity':manifest['files']['vectors.f32'],
                         'attempt_record_hash':content_hash(record)}
            if attempt_id in nodes and any(nodes[attempt_id][key] != value for key,value in signature.items()):
                raise ValueError('conflicting physical index attempt identities')
            # Validate references before deduplication, including aliases of shared
            # ancestors. Their path, manifest, vector and successful row all bind.
            active_paths.add(path)
            active_ids.add(attempt_id)
            for reference in references:
                parent_id, parent = visit(reference['path'])
                if (reference['manifest_hash'] != content_hash(parent) or reference['attempt_id'] != parent_id or
                        reference['vector_sha256'] != parent['files']['vectors.f32']['sha256']):
                    raise ValueError('reused parent manifest/vector/attempt identity changed')
                edge = {'child_attempt_id':attempt_id, 'parent_attempt_id':parent_id, 'reference':reference}
                if edge not in edges:
                    edges.append(edge)
            active_ids.remove(attempt_id)
            active_paths.remove(path)
            for name in ('manifest.json', *manifest['files']):
                candidate = path/name
                if not candidate.resolve().is_relative_to(path):
                    raise ValueError('index payload escapes its physical root')
                actual = file_identity(candidate)
                expected = ({'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}
                            if name == 'manifest.json' else manifest['files'][name])
                if actual != expected:
                    raise ValueError('index payload identity changed during lineage validation')
                files[str(candidate)] = actual
            if completion['scope'] == 'cli':
                provenance = Path(completion['provenance_path']).resolve(strict=True)
                files[str(provenance)] = file_identity(provenance)
            if attempt_id not in nodes:
                nodes[attempt_id] = {'attempt_id':attempt_id, 'path':str(path), **signature}
            dependencies[attempt_id] = record
            visited[path] = (attempt_id,manifest)
            return attempt_id, manifest

        root = Path(index_dir).resolve(strict=True)
        root_id, _ = visit(root)
        for name,expected in files.items():
            if file_identity(Path(name)) != expected:
                raise ValueError('index dependency changed during lineage capture')
        for name,interval in intervals.items():
            with Path(name).open('rb') as stream:
                if hashlib.sha256(stream.read(interval['bytes'])).hexdigest() != interval['sha256']:
                    raise ValueError('ledger prefix changed during lineage capture')
        result = {'schema_version':1, 'root':str(root), 'root_attempt_id':root_id,
                  'edge_scope':'producer dependencies; not every parent window necessarily used',
                  'nodes':sorted(nodes.values(), key=lambda n:n['attempt_id']),
                  'edges':sorted(edges, key=content_hash), 'files':dict(sorted(files.items())),
                  'ledger_intervals':dict(sorted(intervals.items())),
                  'dependency_attempts':[dependencies[k] for k in sorted(dependencies)],
                  'additional_attempts':[records[k] for k in sorted(records) if k not in dependencies]}
        if frozen is not None and result != frozen:
            raise ValueError('frozen recursive index lineage changed')
        return result
    except (OSError, KeyError, TypeError, ValueError, RecursionError) as error:
        raise ValueError(f'index lineage unavailable: {error}') from error


def reused_sources(lineage: dict) -> list[dict]:
    """Expose deduplicated ancestry without charging old work as new indexing."""
    costs = {r['attempt_id']:r['elapsed_seconds'] for r in lineage['dependency_attempts']}
    return [{'source_id':'index-attempt:'+n['attempt_id'], 'path':n['path'],
             'manifest_hash':n['manifest_hash'], 'original_elapsed_seconds':costs[n['attempt_id']],
             'cost_scope':'existing dependency adaptation; attribution/reuse fraction not inferred'}
            for n in lineage['nodes'] if n['attempt_id'] != lineage['root_attempt_id']]

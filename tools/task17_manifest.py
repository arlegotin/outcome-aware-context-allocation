"""A03 manifest writer; never launches, samples, scores, or loads a model/index.

Run from the repository root only after source review and root's separate release.
Creating these manifests does not authorize native execution.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from outcome_poc import protocol as p
from outcome_poc.storage import atomic_json, content_hash, read_jsonl, _sync_directory


SOURCE_EXTRAS = (
    'tools/task17_manifest.py',
    'tests/test_task17_manifest.py',
    'configs/task17-timing-replication.json',
    'docs/amendments/A03-timing-replication.json',
)
DEADLINES = {
    'latest_launch_utc': '2026-10-15T08:12:52+00:00',
    'collection_deadline_utc': '2026-10-15T10:12:52+00:00',
    'original_project_deadline_utc': '2026-10-15T12:12:52+00:00',
    'original_collector_cutoff_utc': '2026-10-15T06:12:52+00:00',
}


def _new_roots(parent, config):
    roots = []
    for key in ('output_dir', 'run_dir'):
        path = Path(config[key])
        if path.exists() or path.is_symlink():
            raise ValueError('new path already exists: ' + str(path))
        roots.append(path.resolve())
    old = [Path(parent[key]).resolve() for key in ('output_dir', 'run_dir')]
    old.append(Path(parent['methods']['retrieval']['index_dir']).resolve())
    for i, root in enumerate(roots):
        if any(root.is_relative_to(other) or other.is_relative_to(root)
               for other in [*old, *roots[:i]]):
            raise ValueError('new roots overlap an original or new path')
    return roots


def _index_origin(parent):
    """Check the existing operational seal and metadata, without opening an index."""
    settings = parent['methods']['retrieval']
    path = Path(settings['operational_realization_path']).resolve()
    if path != Path(parent['run_dir']).resolve() / 'index-realization.json':
        raise ValueError('parent index realization path does not belong to parent run')
    seal = p._read(path)
    if (seal['protocol_hash'] != parent['protocol_hash'] or
            seal['scientific_digests'] != parent['digests'] or
            seal['algorithm'] != settings or
            seal['document_ids_hash'] != parent['sample']['document_ids_hash']):
        raise ValueError('parent index seal identity changed')
    files = seal['files']
    for name, digest in files.items():
        if p.file_hash(name) != digest:
            raise ValueError('parent index file checksum changed: ' + name)
    index = Path(settings['index_dir']).resolve()
    manifest_path = index / 'manifest.json'
    bound = {Path(name).resolve(): digest for name, digest in files.items()}
    if manifest_path not in bound:
        raise ValueError('parent index manifest is not sealed')
    manifest = p._read(manifest_path)
    completion = manifest['completion']
    physical_id = 'index-attempt:' + completion['attempt_id']
    if (manifest['format_version'] != 2 or completion['status'] != 'complete' or
            completion['scope'] != 'selected_documents' or
            content_hash(manifest) != seal['manifest_hash'] or
            physical_id != seal['new_physical_source_id']):
        raise ValueError('parent physical index identity changed')
    ledger = Path(completion['attempt_ledger']).resolve()
    if ledger not in bound or Path(parent['run_dir']).resolve() / 'selected-documents.jsonl' not in bound:
        raise ValueError('parent index completion/projection is not sealed')
    for name, identity in manifest['files'].items():
        payload = (index / name).resolve()
        if (not payload.is_relative_to(index) or bound.get(payload) != identity['sha256'] or
                payload.stat().st_size != identity['bytes']):
            raise ValueError('parent index payload binding changed')
    attempts = [row for row in read_jsonl(ledger) if row['attempt_id'] == completion['attempt_id']]
    if (len(attempts) != 1 or attempts[0]['status'] != 'ok' or
            attempts[0]['manifest_hash'] != seal['manifest_hash']):
        raise ValueError('parent physical index completion missing')
    return {
        'index_dir': str(index), 'parent_seal_path': str(path),
        'parent_seal_sha256': p.file_hash(path), 'manifest_hash': seal['manifest_hash'],
        'physical_source_id': physical_id,
        'owner_protocol_hash': parent['protocol_hash'], 'owner_run_dir': parent['run_dir'],
        'charged_as_new_index': False,
        'reused_physical_sources': copy.deepcopy(seal['reused_physical_sources']),
        'files': copy.deepcopy(files),
    }


def write_replication(parent_protocol_path: Path, config: dict) -> dict:
    """Write one new immutable manifest set. No source or original artifact edits."""
    if (set(config) != {*DEADLINES, 'expected_parent_protocol_hash', 'output_dir', 'run_dir'} or
            any(config[key] != value for key, value in DEADLINES.items())):
        raise ValueError('A03 configuration/deadlines changed')
    parent_protocol_path = Path(parent_protocol_path).resolve()
    parent = p.verify_protocol(parent_protocol_path)
    m, sample = parent['methods'], parent['sample']
    if (parent['fixture'] is not False or
            parent['protocol_hash'] != config['expected_parent_protocol_hash'] or
            (m['n'], m['N'], sample['n'], sample['N'], sample['seed'], m['repetitions']) !=
            (480, 7344, 480, 7344, 271828, 2) or
            datetime.fromisoformat(m['deadline_utc']) !=
            datetime.fromisoformat(DEADLINES['original_project_deadline_utc'])):
        raise ValueError('parent identity/sample/settings differ from A03')
    if parent_protocol_path != Path(parent['output_dir']).resolve() / 'protocol.json':
        raise ValueError('parent protocol path differs from original root')
    root, run_root = _new_roots(parent, config)
    sample_path = parent_protocol_path.with_name('sample.json')
    sample_bytes = sample_path.read_bytes()
    if json.loads(sample_bytes) != sample:
        raise ValueError('parent sample changed during copy')
    origin = _index_origin(parent)

    required = sorted(set(parent['source']['sha256']) | set(SOURCE_EXTRAS))
    for name in required:
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or not path.is_file():
            raise ValueError('required repository-relative source missing: ' + name)
    source = p._capture_source(
        subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        p.execution_source_files(required), fixture=False)
    if any(source['sha256'].get(name) != digest for name, digest in parent['source']['sha256'].items()):
        raise ValueError('original source bytes changed')
    amendment = p._read(Path(SOURCE_EXTRAS[-1]))
    if (amendment['amendment_id'] != 'A03' or
            amendment['parent_protocol_hash'] != parent['protocol_hash'] or
            amendment['operational_gate']['maximum_conditional_replications'] != 1 or
            any(amendment['operational_gate'][key] != value for key, value in DEADLINES.items())):
        raise ValueError('invalid A03 amendment')

    methods = copy.deepcopy(m)
    methods['representatives'] = []
    methods['retrieval']['operational_realization_path'] = str(run_root / 'index-realization.json')
    methods['deadline_utc'] = DEADLINES['collection_deadline_utc']
    schedule = {'jobs': p.plan_jobs(methods, sample['tasks']), 'assigned_task_ids': sample['task_ids']}
    if len(schedule['jobs']) != 3360 or sum(j['scope'] == 'primary' for j in schedule['jobs']) != 1920:
        raise ValueError('A03 frozen scheduler counts differ')
    artifacts = copy.deepcopy(parent['artifact_sha256'])
    added = {**origin['files'], origin['parent_seal_path']: origin['parent_seal_sha256']}
    for name in ('protocol.json', 'methods.json', 'sample.json', 'schedule.json'):
        path = parent_protocol_path.with_name(name)
        added[str(path)] = p.file_hash(path)
    for name, digest in added.items():
        if name in artifacts and artifacts[name] != digest:
            raise ValueError('original artifact binding collision')
        artifacts[name] = digest
    replication = {
        'amendment_id': 'A03', 'amendment_path': SOURCE_EXTRAS[-1],
        'amendment_sha256': source['sha256'][SOURCE_EXTRAS[-1]],
        'parent': {'protocol_path': str(parent_protocol_path),
            'protocol_hash': parent['protocol_hash'], 'protocol_file_sha256': added[str(parent_protocol_path)],
            'sample_file_sha256': added[str(sample_path)], 'scientific_digests': parent['digests'],
            'source': parent['source'], 'output_dir': parent['output_dir'], 'run_dir': parent['run_dir']},
        'methods_changes': {
            'representatives': {'previous': m['representatives'], 'new': []},
            'deadline_utc': {'previous': m['deadline_utc'], 'new': methods['deadline_utc']},
            'retrieval.operational_realization_path': {
                'previous': m['retrieval']['operational_realization_path'],
                'new': methods['retrieval']['operational_realization_path']}},
        'shared_index': origin,
        'cost_identity': {'local_work_key': ['protocol_hash', 'run_dir', 'local_source_or_job_id'],
            'shared_index_key': ['physical_source_id', 'manifest_hash'],
            'rule': 'Retain every new setup/execution cost; deduplicate original physical index construction once.'},
        'forecast': {'original_values': m['forecast'], 'operational_feasibility_established': False,
            'rule': 'Inherited original-plan forecast is provenance only. Root must record a measured prospective budget before launch.'},
        'deadlines': DEADLINES, 'launch_authorized': False,
        'launch_rule': amendment['operational_gate'],
        'original_wall_time_endpoint': 'invalid',
        'claim_scope': amendment['unchanged']['comparison'],
    }
    result = {'version': parent['version'], 'methods': methods, 'sample': sample, 'schedule': schedule,
        'digests': {key: content_hash(value) for key, value in
                    [('methods', methods), ('sample', sample), ('schedule', schedule)]},
        'source': source, 'artifact_sha256': artifacts, 'output_dir': str(root), 'run_dir': str(run_root),
        'fixture': False, 'source_history': [], 'created_utc': datetime.now(timezone.utc).isoformat(),
        'replication': replication}
    result['protocol_hash'] = p._hash_protocol(result)
    # Validation is complete before claiming a destination. Interrupted output is
    # deliberately retained and cannot be overwritten or silently resumed.
    if p.verify_protocol(parent_protocol_path) != parent:
        raise ValueError('parent changed while constructing replication')
    _new_roots(parent, config)
    root.mkdir(parents=True, exist_ok=False)
    atomic_json(root / 'methods.json', methods)
    with (root / 'sample.json').open('xb') as stream:
        stream.write(sample_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(root)
    atomic_json(root / 'schedule.json', schedule)
    atomic_json(root / 'protocol.json', result)
    checked = p.verify_protocol(root / 'protocol.json')
    if p.file_hash(root / 'sample.json') != replication['parent']['sample_file_sha256']:
        raise ValueError('sample bytes changed during replication publication')
    return checked


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-protocol', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=Path(SOURCE_EXTRAS[2]))
    args = parser.parse_args(argv)
    result = write_replication(args.parent_protocol, p._read(args.config))
    print(json.dumps({'protocol_hash': result['protocol_hash'], 'output_dir': result['output_dir'],
        'run_dir': result['run_dir'], 'assigned_unique_tasks': result['sample']['n'],
        'assigned_jobs': len(result['schedule']['jobs']), 'launch_authorized': False}, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

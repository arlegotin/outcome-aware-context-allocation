"""Real index-producer integrations; fake encoding is software-test data only."""
import json
from pathlib import Path

import pytest

from outcome_poc import retrieval
from outcome_poc.storage import append_jsonl, atomic_json, content_hash, read_jsonl
from retrieval_helpers import Encoder, document, store


def capture(path, **kwargs):
    from outcome_poc.index_lineage import capture_lineage
    return capture_lineage(path, **kwargs)


def build(tmp_path, name, parents=()):
    path = tmp_path / name / 'index'
    doc = document('Authored bridge', ['The invented vessel is named Iris.', 'Iris is violet.'])
    manifest = retrieval.build_index([doc], Encoder(), path, reuse_indexes=parents)
    return path, manifest


def reseal(path, change):
    """Authored corruption fixtures update the local producer completion predicate.

    This is never used on retained evidence. The recursive validator must still
    reject metadata which the shallow producer predicate accepts.
    """
    manifest = json.loads((path / 'manifest.json').read_text())
    change(manifest)
    atomic_json(path / 'manifest.json', manifest)
    ledger = Path(manifest['completion']['attempt_ledger'])
    rows = list(read_jsonl(ledger))
    for row in rows:
        if row['attempt_id'] == manifest['completion']['attempt_id']:
            row['manifest_hash'] = content_hash(manifest)
    ledger.write_bytes(b''.join(json.dumps(r, sort_keys=True).encode() + b'\n' for r in rows))


def test_fresh_chain_diamond_inventory_and_ranking_parity(tmp_path):
    a, ma = build(tmp_path, 'a')
    b, mb = build(tmp_path, 'b', [a])
    c, mc = build(tmp_path, 'c', [b])
    d, md = build(tmp_path, 'diamond', [b, c])
    fresh = capture(a)
    assert len(fresh['nodes']) == 1 and not fresh['edges']
    inventory = capture(d)
    assert {v['attempt_id'] for v in inventory['nodes']} == {
        m['completion']['attempt_id'] for m in (ma, mb, mc, md)}
    assert len(inventory['edges']) == 4  # d->b,c; c->b; b->a
    assert len(inventory['dependency_attempts']) == 4
    assert capture(d, frozen=inventory) == inventory
    assert md['offline']['reused_window_count'] == 1
    assert md['offline']['encoded_window_count'] == 0
    assert (a / 'vectors.f32').read_bytes() == (d / 'vectors.f32').read_bytes()
    doc = document('Authored bridge', ['The invented vessel is named Iris.', 'Iris is violet.'])
    docs = store(tmp_path, [doc])
    ranks = [retrieval.Retrieval(p, docs, Encoder()).rank('What color is Iris?', [doc.doc_id]) for p in (a, d)]
    assert ranks[0] == ranks[1]
    assert all(Path(n['path']).is_absolute() for n in inventory['nodes'])


def test_failed_attempts_are_cost_inventory_and_later_appends_do_not_rewrite_freeze(tmp_path):
    a, ma = build(tmp_path, 'a')
    ledger = Path(ma['completion']['attempt_ledger'])
    failed = {'attempt_id': 'failed-authored', 'status': 'failed', 'elapsed_seconds': 2.5}
    append_jsonl(ledger, failed)
    before = capture(a)
    assert before['additional_attempts'] == [failed]
    append_jsonl(ledger, {'attempt_id': 'later-unrelated', 'status': 'failed', 'elapsed_seconds': 9.0})
    assert capture(a, frozen=before) == before
    assert len(capture(a)['additional_attempts']) == 2
    data = ledger.read_bytes()
    ledger.write_bytes(data.replace(b'2.5', b'2.6'))
    with pytest.raises(ValueError, match='ledger|prefix'):
        capture(a, frozen=before)


@pytest.mark.parametrize('mutation', [
    lambda m: m['offline'].pop('reuse_sources'),
    lambda m: m['offline'].update(reuse_sources=None),
    lambda m: m['offline'].update(reuse_sources={}),
    lambda m: m['offline'].update(reused_window_count=True),
    lambda m: m['offline'].update(encoded_window_count=-1),
    lambda m: m.update(reuse_sources=[]),
    lambda m: m.update(format_version=True),
])
def test_malformed_explicit_metadata_never_becomes_no_ancestry(tmp_path, mutation):
    a, _ = build(tmp_path, 'a')
    reseal(a, mutation)
    with pytest.raises(ValueError):
        capture(a)


@pytest.mark.parametrize('target', ['manifest.json', 'vectors.f32', 'ledger'])
@pytest.mark.parametrize('operation', ['missing', 'tampered'])
def test_missing_or_tampered_ancestor_is_rejected(tmp_path, target, operation):
    a, ma = build(tmp_path, 'a')
    b, _ = build(tmp_path, 'b', [a])
    path = Path(ma['completion']['attempt_ledger']) if target == 'ledger' else a / target
    if operation == 'missing':
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b'corruption')
    with pytest.raises(ValueError):
        capture(b)


def test_parent_reference_vector_and_attempt_id_must_both_match(tmp_path):
    a, _ = build(tmp_path, 'a')
    b, _ = build(tmp_path, 'b', [a])
    reseal(b, lambda m: m['offline']['reuse_sources'][0].update(vector_sha256='0' * 64))
    with pytest.raises(ValueError, match='identity|vector'):
        capture(b)


def test_conflicting_duplicate_attempt_ids_are_rejected_before_deduplication(tmp_path):
    a, ma = build(tmp_path, 'a')
    b, mb = build(tmp_path, 'b')
    # Distinct real producer manifests now make conflicting claims to one ID.
    reseal(b, lambda m: m['completion'].update(attempt_id=ma['completion']['attempt_id']))
    ledger = Path(mb['completion']['attempt_ledger'])
    row = list(read_jsonl(ledger))[0]
    row.update(attempt_id=ma['completion']['attempt_id'], manifest_hash=content_hash(json.loads((b/'manifest.json').read_text())))
    ledger.write_text(json.dumps(row) + '\n')
    d, _ = build(tmp_path, 'd', [a, b])
    with pytest.raises(ValueError, match='conflict'):
        capture(d)


def test_cycles_fail_closed_even_before_bad_reference_digest_is_followed(tmp_path):
    a, ma = build(tmp_path, 'a')
    reference = {'path': str(a), 'manifest_hash': content_hash(ma),
                 'attempt_id': ma['completion']['attempt_id'], 'vector_sha256': ma['files']['vectors.f32']['sha256']}
    reseal(a, lambda m: m['offline'].update(reuse_sources=[reference]))
    with pytest.raises(ValueError, match='cycle'):
        capture(a)


def test_duplicate_ledger_ids_and_nonfinite_costs_fail_closed(tmp_path):
    a, ma = build(tmp_path, 'a')
    ledger = Path(ma['completion']['attempt_ledger'])
    append_jsonl(ledger, {'attempt_id': 'other', 'status': 'failed', 'elapsed_seconds': 1.0})
    append_jsonl(ledger, {'attempt_id': 'other', 'status': 'failed', 'elapsed_seconds': 2.0})
    with pytest.raises(ValueError, match='duplicate|conflict'):
        capture(a)


def test_required_payload_cannot_be_omitted_from_resealed_manifest(tmp_path):
    a, _ = build(tmp_path,'a')
    reseal(a,lambda m:m['files'].pop('metadata.sqlite3'))
    (a/'metadata.sqlite3').unlink()
    with pytest.raises(ValueError,match='payload'):
        capture(a)


def test_shared_ancestor_validated_once_and_identity_race_rejected(tmp_path,monkeypatch):
    import outcome_poc.index_lineage as lineage
    a,_ = build(tmp_path,'a')
    b,_ = build(tmp_path,'b',[a])
    c,_ = build(tmp_path,'c',[a,b])
    d,_ = build(tmp_path,'d',[b,c])
    original = lineage._completed_manifest
    visits = []
    def observe(path):
        visits.append(path)
        return original(path)
    monkeypatch.setattr(lineage,'_completed_manifest',observe)
    capture(d)
    assert len(visits) == 4
    def race(path):
        result = original(path)
        (path/'vectors.f32').write_bytes(b'changed after validation')
        return result
    monkeypatch.setattr(lineage,'_completed_manifest',race)
    with pytest.raises(ValueError,match='changed|digest|identity'):
        capture(a)


def test_protected_and_transfer_use_same_recursive_inventory_and_reload(tmp_path):
    from outcome_poc import protected, transfer_runtime
    from test_protected_run import protected_fixture
    (tmp_path / 'protected').mkdir()
    frozen, runtime, _ = protected_fixture(tmp_path / 'protected')
    docs = retrieval.DocumentStore(runtime.document_path)
    a = tmp_path / 'source-a' / 'index'
    b = tmp_path / 'source-b' / 'index'
    retrieval.build_index((docs.get(i) for i in docs.offsets), Encoder(), a)
    retrieval.build_index((docs.get(i) for i in docs.offsets), Encoder(), b, reuse_indexes=[a])
    settings = frozen['methods']['retrieval']
    seal_path = Path(frozen['run_dir']) / 'index-realization.json'
    settings.update(index_dir=str(tmp_path/'protected-index'/'index'), reuse_indexes=[str(b)],
                    operational_realization_path=str(seal_path))
    protected.realize_index(frozen, docs, Encoder())
    seal = json.loads(seal_path.read_text())
    assert {n['attempt_id'] for n in seal['index_lineage']['nodes']} >= {
        json.loads((p/'manifest.json').read_text())['completion']['attempt_id'] for p in (a, b)}
    assert len(seal['reused_physical_sources']) == 2
    append_jsonl(a.parent/'index-attempts.jsonl', {'attempt_id':'later','status':'failed','elapsed_seconds':1.0})
    protected.realize_index(frozen, docs, Encoder())
    pooled_root = tmp_path / 'pooled'
    pooled_root.mkdir()
    m = {'root':str(pooled_root), 'manifest_hash':'authored', 'reuse_indexes':[str(b)],
         'corpus':{'document_ids':sorted(docs.offsets)}}
    index, manifest = transfer_runtime.build_pooled_index(m, docs, Encoder())
    pooled = json.loads((pooled_root/'index-realization.json').read_text())
    assert len(pooled['reused_physical_sources']) == 2
    assert transfer_runtime.build_pooled_index(m, docs, Encoder()) == (index, manifest)
    assert len(pooled['index_lineage']['nodes']) == 3


def test_transfer_missing_declared_source_is_not_silently_dropped(tmp_path):
    from outcome_poc.transfer_runtime import build_pooled_index
    doc = document('Authored', ['one'])
    docs = store(tmp_path, [doc])
    root = tmp_path / 'pooled'
    root.mkdir()
    m = {'root':str(root), 'manifest_hash':'authored','reuse_indexes':[str(tmp_path/'missing')],
         'corpus':{'document_ids':[doc.doc_id]}}
    with pytest.raises(ValueError, match='completion|lineage'):
        build_pooled_index(m, docs, Encoder())

import json
import numpy as np
import pytest
from outcome_poc import retrieval
from retrieval_helpers import Encoder, document, store


def test_max_window_score_and_hash_ties_are_invariant_to_candidate_order(tmp_path):
    a = document('A', [' '.join(['first'] * 477), 'best'])
    b = document('B', ['same'])
    c = document('C', ['irrelevant'])
    encoder = Encoder({'A\n' + a.sentences[0]: 1, 'C\nirrelevant': 1})
    retrieval.build_index([c, a, b], encoder, tmp_path / 'index')
    ranker = retrieval.Retrieval(tmp_path / 'index', store(tmp_path, [a, b, c]), encoder)
    expected = sorted([a.doc_id, b.doc_id]) + [c.doc_id]
    rows = ranker.rank('question', [c.doc_id, b.doc_id, a.doc_id])
    assert [r.doc_id for r in rows] == expected
    assert [r.score for r in rows] == [1., 1., 0.]
    assert [r.rank for r in rows] == [0, 1, 2]
    assert ranker.rank('question', [a.doc_id, c.doc_id, b.doc_id]) == rows
    assert encoder.texts[-1] == 'Represent this sentence for searching relevant passages: question'
    assert ranker.documents.get(a.doc_id).sentences == a.sentences
    assert set(ranker.last_timings) == {'query_encoding_seconds', 'vector_lookup_seconds', 'dots_seconds', 'aggregation_seconds', 'sort_seconds', 'evidence_reads_seconds'}
    assert all(v >= 0 for v in ranker.last_timings.values())


def test_long_query_logs_explicit_right_truncation_counts(tmp_path, caplog):
    doc = document('Title', ['body'])
    encoder = Encoder()
    retrieval.build_index([doc], encoder, tmp_path / 'index')
    ranker = retrieval.Retrieval(tmp_path / 'index', store(tmp_path, [doc]), encoder)
    ranker.rank(' '.join(['word'] * 600), [doc.doc_id])
    assert ranker.last_query['original_tokens'] == 609
    assert ranker.last_query['retained_tokens'] == 512
    assert ranker.last_query['truncated'] is True
    assert ranker.last_query['truncation_side'] == 'right'
    assert 'query truncation' in caplog.text


def test_rank_rejects_missing_or_duplicate_candidates_and_changed_encoder(tmp_path):
    doc = document('Title', ['body'])
    encoder = Encoder()
    retrieval.build_index([doc], encoder, tmp_path / 'index')
    documents = store(tmp_path, [doc])
    ranker = retrieval.Retrieval(tmp_path / 'index', documents, encoder)
    with pytest.raises(ValueError, match='candidate'):
        ranker.rank('question', [doc.doc_id, doc.doc_id])
    with pytest.raises(ValueError, match='candidate'):
        ranker.rank('question', ['missing'])
    encoder.identity = {'revision': 'changed', 'snapshot_hash': 'changed'}
    with pytest.raises(ValueError, match='encoder'):
        retrieval.Retrieval(tmp_path / 'index', documents, encoder)


def test_rank_refuses_mutated_index_files(tmp_path):
    doc = document('Title', ['body'])
    encoder = Encoder()
    retrieval.build_index([doc], encoder, tmp_path / 'index')
    path = tmp_path / 'index/vectors.f32'
    with path.open('r+b') as stream:
        stream.write(b'broken')
    with pytest.raises(ValueError, match='digest'):
        retrieval.Retrieval(tmp_path / 'index', store(tmp_path, [doc]), encoder)


def test_failed_rank_exposes_partial_costs_instead_of_previous_success_timings(tmp_path):
    doc = document('Title', ['body'])
    encoder = Encoder()
    retrieval.build_index([doc], encoder, tmp_path / 'index')
    ranker = retrieval.Retrieval(tmp_path / 'index', store(tmp_path, [doc]), encoder)
    ranker.rank('question', [doc.doc_id])
    with pytest.raises(ValueError, match='candidate'):
        ranker.rank('question', ['missing'])
    assert set(ranker.last_timings) == {'query_encoding_seconds'}

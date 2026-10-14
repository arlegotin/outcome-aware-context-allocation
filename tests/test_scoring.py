from dataclasses import replace

import pytest

from outcome_poc import scoring
from outcome_poc.schemas import GoldRecord, Prediction
from retrieval_helpers import document, store


@pytest.mark.parametrize('prediction,gold,want', [
    ('The, RED-blue!', 'redblue', (1, 1, 1, 1)),
    ('', 'the', (1, 0, 0, 0)), ('', 'red', (0, 0, 0, 0)), ('red', '', (0, 0, 0, 0)),
    (' YES! ', 'yes', (1, 1, 1, 1)),
    ('red red blue', 'red blue blue', (0, 2/3, 2/3, 2/3)),
    ('red red blue', 'red', (0, 1/2, 1/3, 1)),
])
def test_pinned_source_derived_answer_fixtures(prediction, gold, want):
    result = scoring.score_answer(prediction, gold)
    assert tuple(result[k] for k in ('em', 'f1', 'precision', 'recall')) == pytest.approx(want)


@pytest.mark.parametrize('special', ['yes', 'no', 'noanswer'])
@pytest.mark.parametrize('reverse', [False, True])
def test_special_answer_mismatch_is_symmetric(special, reverse):
    pair = [special, special + ' red']
    if reverse: pair.reverse()
    assert scoring.score_answer(*pair) == {'em': 0, 'f1': 0., 'precision': 0., 'recall': 0.}


@pytest.mark.parametrize('predicted,gold,want', [
    (set(), set(), (1, 0, 0, 0)), (set(), {('A', 0)}, (0, 0, 0, 0)),
    ({('A', 0)}, set(), (0, 0, 0, 0)),
    ({('A', 0)}, {('A', 0), ('B', 0)}, (0, 2/3, 1, 1/2)),
    ({('A', 0)}, {('a', 0)}, (0, 0, 0, 0)),
])
def test_pinned_source_derived_support_fixtures(predicted, gold, want):
    result = scoring.score_support(predicted, gold)
    assert tuple(result[k] for k in ('em', 'f1', 'precision', 'recall')) == pytest.approx(want)


def test_official_joint_f1_is_not_mean_of_f1s():
    answer = scoring.score_answer('red blue', 'red green')
    support = scoring.score_support({('A', 0)}, {('A', 0), ('B', 0)})
    assert scoring.joint_f1(answer, support) == pytest.approx(1/3)
    assert scoring.joint_f1(answer, support) != pytest.approx((answer['f1'] + support['f1']) / 2)


def test_scorer_maps_hashes_preserves_diagnostics_and_counts_one_success(tmp_path):
    doc = document('Original Title', ['A blue lamp.'])
    documents = store(tmp_path, [doc])
    gold = GoldRecord('task', 'blue', [('Original Title', 0)])
    prediction = Prediction('run', 'task', 'fixed-ten', 'protocol', 'job', 1, 0, [doc.doc_id],
                            'raw', 'blue', [(doc.doc_id, 0), (doc.doc_id, 0)], 'ok',
                            'revision', 'prompt', 'decoding', 1.5, 10, 10, 1, ['event'])
    correct = scoring.Scorer().score(prediction, gold, documents)
    wrong = scoring.Scorer().score(replace(prediction, answer='red'), gold, documents)
    assert correct.joint_em + wrong.joint_em == 1
    assert correct.support_f1 == 1 and correct.total_serving_seconds == 1.5
    for status in ('abstain', 'parse_error', 'invalid_citation', 'context_overflow',
                   'timeout', 'budget_exhausted', 'infra_error'):
        result = scoring.Scorer().score(replace(prediction, status=status), gold, documents)
        assert result.joint_em == 0 and result.joint_f1 == 0 and result.answer_em == 1
    for citations in ([('unknown', 0)], [(doc.doc_id, 1)]):
        result = scoring.Scorer().score(replace(prediction, citations=citations), gold, documents)
        assert result.joint_em == 0 and result.answer_em == 1
    empty = scoring.Scorer().score(replace(prediction, answer='', status='abstain'),
                                   replace(gold, answer='the'), documents)
    assert empty.answer_em == 1 and empty.joint_em == 0
    with pytest.raises(ValueError, match='task'):
        scoring.Scorer().score(prediction, replace(gold, task_id='other'), documents)

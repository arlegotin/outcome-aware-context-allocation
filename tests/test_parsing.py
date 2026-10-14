import json

import pytest

from outcome_poc import generation
from retrieval_helpers import document


@pytest.fixture
def packet():
    selected = document('Invented lamp', ['Blue lamp.', 'Lamp glows.'])
    unselected = document('Invented kite', ['Red kite.'])
    return [selected], {'D0': unselected.doc_id, 'D8': selected.doc_id}


@pytest.mark.parametrize('fence', ['', 'json', None])
def test_one_object_and_single_json_or_unlabeled_fence(packet, fence):
    evidence, aliases = packet
    raw = '{"answer":"blue","citations":[{"doc_id":"D8","sentence_index":1},{"doc_id":"D8","sentence_index":1}]}'
    if fence is not None: raw = f'```{fence}\n{raw}\n```'
    result = generation.parse_answer(' \n' + raw + '\n ', evidence, aliases)
    assert result.status == 'ok' and result.answer == 'blue'
    assert set(result.citations) == {(evidence[0].doc_id, 1)}


@pytest.mark.parametrize('raw', [
    '{} {}', 'Here: {"answer":"blue","citations":[]}',
    '{"answer":"blue","answer":"red","citations":[]}',
    '{"answer":"blue","citations":[],"confidence":1}',
    '{"answer":"blue","citations":[{"doc_id":"D8","doc_id":"D8","sentence_index":0}]}',
    '{"answer":"blue","citations":NaN}',
    '```python\n{"answer":"blue","citations":[]}\n```',
    '```json\n{"answer":"blue","citations":[]}\n```\n```\n{}\n```',
    '{"answer":true,"citations":[]}',
])
def test_malformed_objects_fail_without_repairs(packet, raw):
    assert generation.parse_answer(raw, *packet).status == 'parse_error'


@pytest.mark.parametrize('doc_id,index', [('D0', 0), ('missing', 0), ('D8', -1), ('D8', 2),
                                        ('D8', True), ('D8', 0.0)])
def test_invalid_citations_keep_answer_for_diagnostics(packet, doc_id, index):
    raw = json.dumps({'answer': 'blue', 'citations': [{'doc_id': doc_id, 'sentence_index': index}]})
    result = generation.parse_answer(raw, *packet)
    assert result.status == 'invalid_citation' and result.answer == 'blue'
    assert result.citations == []


def test_empty_answer_abstains_and_truncation_is_never_success(packet):
    assert generation.parse_answer('{"answer":"  ","citations":[]}', *packet).status == 'abstain'
    result = generation.parse_answer('{"answer":"blue","citations":[]}', *packet, truncated=True)
    assert result.status == 'budget_exhausted' and result.answer == 'blue'

"""Authored rendering fixtures: preserve evidence and the one-template boundary."""
import json
import pytest
from outcome_poc.generation import ANSWER_SYSTEM, render_prompt, prompt_identity

REMINDER = 'Include the supplied sentences that establish every link from the entities or conditions in the question to the answer, including intermediate entity links and the final answer relation.'


class Tokenizer:
    chat_template = 'authored-template-v1'

    def __init__(self):
        self.calls = []

    def apply_chat_template(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return json.dumps([messages, kwargs], ensure_ascii=False)


def test_baseline_rendering_is_byte_identical(documents10):
    from outcome_poc.citation_study.prompts import render_condition
    aliases = {f'D{i}': d.doc_id for i, d in enumerate(documents10)}
    original, adapted = Tokenizer(), Tokenizer()
    expected = render_prompt('Invented question?', documents10[:2], aliases, original)
    actual = render_condition('Invented question?', documents10[:2], aliases, adapted, 'baseline')
    assert actual.encode() == expected.encode()
    assert len(adapted.calls) == 1
    assert prompt_identity(actual, adapted) == prompt_identity(expected, original)


def test_chain_changes_only_system_once(documents10):
    from outcome_poc.citation_study.prompts import CONDITIONS, render_condition
    tokenizer = Tokenizer()
    aliases = {f'D{i}': d.doc_id for i, d in enumerate(documents10)}
    baseline = render_prompt('Invented café?', documents10[2:4], aliases, Tokenizer())
    chain = render_condition('Invented café?', documents10[2:4], aliases, tokenizer, 'chain')
    expected = json.loads(baseline)
    expected[0][0]['content'] = ANSWER_SYSTEM + '\n' + REMINDER
    assert json.loads(chain) == expected
    assert CONDITIONS['baseline'] == ANSWER_SYSTEM
    assert CONDITIONS['chain'] == ANSWER_SYSTEM + '\n' + REMINDER
    assert len(tokenizer.calls) == 1
    assert prompt_identity(chain, tokenizer) != prompt_identity(baseline, tokenizer)
    with pytest.raises(ValueError, match='condition'):
        render_condition('q', [], {}, tokenizer, 'unknown')
    with pytest.raises(TypeError):
        CONDITIONS['chain'] = 'changed'

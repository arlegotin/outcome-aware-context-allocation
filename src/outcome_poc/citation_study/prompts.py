"""Explicit immutable prompt conditions; preserve the reader's rendering semantics."""
from types import MappingProxyType

from ..generation import ANSWER_SYSTEM, render_prompt, prompt_identity
from ..storage import content_hash

CHAIN_SENTENCE = 'Include the supplied sentences that establish every link from the entities or conditions in the question to the answer, including intermediate entity links and the final answer relation.'
CONDITIONS = MappingProxyType({'baseline': ANSWER_SYSTEM, 'chain': ANSWER_SYSTEM + '\n' + CHAIN_SENTENCE})


def registry():
    return {condition: {'system': system, 'system_hash': content_hash(system)}
            for condition, system in CONDITIONS.items()}


def render_condition(question, evidence, aliases, tokenizer, condition):
    if condition not in CONDITIONS:
        raise ValueError(f'unknown prompt condition: {condition}')

    class MessageAdapter:
        def apply_chat_template(self, messages, **kwargs):
            if (len(messages) != 2 or messages[0] != {'role':'system','content':ANSWER_SYSTEM}
                    or messages[1]['role'] != 'user'):
                raise ValueError('unexpected original reader message contract')
            copied = [dict(message) for message in messages]
            copied[0]['content'] = CONDITIONS[condition]
            return tokenizer.apply_chat_template(copied, **kwargs)

    return render_prompt(question, evidence, aliases, MessageAdapter())

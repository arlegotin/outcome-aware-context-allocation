"""Original-index evidence views without shortening or reidentifying Documents."""
from dataclasses import replace

from ..generation import Reader, render_prompt


def validate_view(evidence, view):
    if type(view) is not dict or set(view) != {d.doc_id for d in evidence} or not evidence:
        raise ValueError('sentence view must cover exactly the nonempty allocated evidence')
    for doc in evidence:
        indices = view[doc.doc_id]
        if (type(indices) is not list or not indices or
                any(type(i) is not int or not 0 <= i < len(doc.sentences) for i in indices) or
                indices != sorted(set(indices))):
            raise ValueError('sentence view needs unique ordered original indices')


def render_view(question, evidence, aliases, tokenizer, view):
    validate_view(evidence, view)
    if all(view[d.doc_id] == list(range(len(d.sentences))) for d in evidence):
        return render_prompt(question,evidence,aliases,tokenizer)
    inverse = {doc_id:alias for alias,doc_id in aliases.items()}
    lines = [f'Question: {question}', 'Evidence:']
    for doc in evidence:
        if doc.doc_id not in inverse:
            raise ValueError('missing original ranking alias')
        lines.append(f'{inverse[doc.doc_id]} | {doc.title}')
        lines.extend(f'[{i}] {doc.sentences[i]}' for i in view[doc.doc_id])
    class ViewTemplate:
        def apply_chat_template(self, messages, **kwargs):
            copied = [dict(m) for m in messages]
            copied[1]['content'] = '\n'.join(lines)
            return tokenizer.apply_chat_template(copied,**kwargs)
    return render_prompt(question,evidence,aliases,ViewTemplate())


def parse_view(generated, evidence, aliases, view):
    validate_view(evidence,view)
    result = Reader.parse_generated(generated,evidence,aliases)
    if result.status == 'ok' and any(i not in view[d] for d,i in result.citations):
        return replace(result,status='invalid_citation',citations=[])
    return result

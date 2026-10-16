"""One authored citation-generation candidate; no historical prompt mutation."""
from ..generation import ANSWER_SYSTEM
from ..storage import content_hash
from .evidence import render_view

from ..reader_recipes import EVIDENCE_FIRST_SYSTEM



def registry():
    return {name:{'system':system,'system_hash':content_hash(system)} for name,system in
            (('baseline',ANSWER_SYSTEM),('evidence-first',EVIDENCE_FIRST_SYSTEM))}


def render_condition(question,evidence,aliases,tokenizer,view,condition):
    if condition not in registry():
        raise ValueError('unknown recovery reader condition')
    if condition=='baseline':
        return render_view(question,evidence,aliases,tokenizer,view)
    class Template:
        def apply_chat_template(self,messages,**kwargs):
            if len(messages)!=2 or messages[0]!={'role':'system','content':ANSWER_SYSTEM}:
                raise ValueError('unexpected baseline message contract')
            copied = [dict(m) for m in messages]
            copied[0]['content'] = EVIDENCE_FIRST_SYSTEM
            return tokenizer.apply_chat_template(copied,**kwargs)
    return render_view(question,evidence,aliases,Template(),view)

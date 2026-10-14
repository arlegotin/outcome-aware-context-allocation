from types import SimpleNamespace
import json

from outcome_poc.generation import Reader
from outcome_poc.schemas import ReaderResult, Task, RankedDocument
from outcome_poc.policies import FixedPolicy
from retrieval_helpers import document
from test_prompt import Tokenizer


class Clock:
    def __init__(self): self.value = 0
    def __call__(self): return self.value
    def advance(self, seconds): self.value += int(seconds * 1e9)


def fixture_runtime(tmp_path, outputs=None):
    from outcome_poc.runner import Runtime
    clock = Clock()
    docs = [document(f'Lamp {i}', [f'A blue lamp {i} glows.']) for i in range(10)]
    task = Task('task', 'pilot', 'Color?', [d.doc_id for d in docs])
    ranking = [RankedDocument(d.doc_id, 1-i/20, i, d.character_count, 1, d.title) for i,d in enumerate(docs)]
    class Retrieval:
        def rank(self, question, candidates):
            clock.advance(2)
            return ranking
    class Store:
        def get(self, identity):
            clock.advance(.5)
            return next(d for d in docs if d.doc_id == identity)
    class Backend:
        tokenizer = Tokenizer()
        calls = 0
        def generate(self, prompt, request, *, rendered=False):
            self.calls += 1
            clock.advance(5)
            raw = (outputs or ['{"answer":"blue","citations":[{"doc_id":"D0","sentence_index":0}]}'])[min(self.calls-1, len(outputs or [0])-1)]
            if raw == 'INFRA': raise RuntimeError('device lost')
            return ReaderResult(raw, None, [], 'ok', 12, 8, [1]*12, [2]*8, 'stop')
        def synchronize(self): pass
    backend = Backend()
    def serialize(value):
        from outcome_poc.storage import canonical_bytes
        clock.advance(3)
        return canonical_bytes(value)
    config = {'model_revision':'r', 'model_hash':'m', 'decoding_hash':'d', 'max_context_tokens':8192,
              'max_new_tokens':256, 'timeout_seconds':1., 'prompt_version':'v1', 'backend':'fixture'}
    runtime = Runtime(Retrieval(), Store(), Reader(backend), config, clock=clock, serialize=serialize)
    job = {'run_id':'run','task':task,'policy':FixedPolicy(2),'protocol_hash':'development-unfrozen',
           'job_id':'job','mode':'direct','repetition_id':0,'cache_mode':'none'}
    return runtime, job, clock

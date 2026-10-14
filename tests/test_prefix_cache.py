import pytest
from outcome_poc import generation, runner
from serving_helpers import fixture_runtime


@pytest.mark.parametrize('a,b,want', [([],[],0),([1],[2],0),([1,2],[1,3],1),([1,2],[1,2,3],2),([1,2],[1,2],2)])
def test_exact_token_prefix(a,b,want):
    assert hasattr(generation,'common_prefix_length'), 'common prefix missing'
    assert generation.common_prefix_length(a,b) == want


def test_optimistic_bound_removes_only_full_clean_prefill_and_retains_shared_draft(tmp_path):
    assert hasattr(runner,'optimistic_post_cost'), 'optimistic cost bound missing'
    from outcome_poc.schemas import Decision
    class Post:
        requires_draft=True
        policy_id='POST-OUTCOME'
        def choose(self,*args,**kwargs): return Decision(self.policy_id,10,None,'always_ten',None,'always_ten','f',10,10)
    runtime,job,_=fixture_runtime(tmp_path)
    runner.execute_job({**job,'policy':Post()},runtime,tmp_path)
    events=runner.load_events(tmp_path)
    from dataclasses import replace
    events=[replace(e,clean_prefill_seconds=3.) if e.role == 'generation:answer' else e for e in events]
    bound=runner.optimistic_post_cost(events,3.)
    assert bound['observed_serving_seconds'] == 21.
    assert bound['optimistic_serving_seconds'] == 18.
    assert bound['removed_full_prefill_seconds'] == 3.
    with pytest.raises(ValueError): runner.optimistic_post_cost(events,6.)
    with pytest.raises(ValueError): runner.optimistic_post_cost(events,-1.)


def fake_native(monkeypatch):
    """Replace the unavailable GPU at its stream/cache boundary, retain adapter code."""
    import sys
    from types import ModuleType, SimpleNamespace
    class Cache:
        def __init__(self): self.offset=0; self.tokens=[]
        def trim(self,n): self.offset-=n; return n
    cachemod=ModuleType('mlx_lm.models.cache')
    cachemod.make_prompt_cache=lambda model: [Cache(),Cache()]
    cachemod.trim_prompt_cache=lambda caches,n: [c.trim(n) for c in caches][0]
    mlx=ModuleType('mlx_lm'); sample=ModuleType('mlx_lm.sample_utils')
    sample.make_sampler=lambda temp: None
    observed=[]
    def stream(model,tokenizer,prompt,**kw):
        caches=kw.get('prompt_cache') or [Cache(),Cache()]
        previous=list(caches[0].tokens[:caches[0].offset])
        observed.append(previous+list(prompt))
        cb=kw['prompt_progress_callback']; cb(0,len(prompt))
        for i,token in enumerate(prompt[:-1],1):
            for c in caches:
                c.tokens[c.offset:c.offset+1]=[token];c.offset+=1
            if i % 512 == 0 or i == len(prompt)-1: cb(i,len(prompt))
        for c in caches:
            c.tokens[c.offset:]=[prompt[-1],999];c.offset+=2
        cb(len(prompt),len(prompt))
        yield SimpleNamespace(text='{"answer":"x","citations":[]}',token=999,finish_reason='stop')
    mlx.stream_generate=stream
    for name,module in [('mlx_lm',mlx),('mlx_lm.sample_utils',sample),('mlx_lm.models.cache',cachemod)]:monkeypatch.setitem(sys.modules,name,module)
    backend=generation.ReaderBackend()
    backend.tokenizer=SimpleNamespace(encode=lambda s,add_special_tokens:list(map(int,s.split())), chat_template='template')
    backend.model=None;backend.identity={'revision':'r','snapshot_hash':'m'};backend.synchronize=lambda:None
    return backend,observed


@pytest.mark.parametrize('common', [0,1,255,256,257,511,512,513])
def test_cache_captured_before_draft_tokens_and_full_suffix_only(monkeypatch,common):
    assert hasattr(generation.Reader,'answer_with_prefix'), 'reader prefix API missing'
    from outcome_poc.schemas import GenerationRequest
    from outcome_poc.generation import prompt_identity
    backend,observed=fake_native(monkeypatch)
    a=list(range(1,common+1))+[700,701]
    b=list(range(1,common+1))+[800,801]
    draft=' '.join(map(str,a));full=' '.join(map(str,b))
    scope={'scope':'question/job','target_prompt':full,'source_prompt_hash':prompt_identity(draft,backend.tokenizer)}
    request=GenerationRequest('r','m',prompt_identity(draft,backend.tokenizer),'d','answer',8192,256,120.,'within_query_prefix')
    d=backend.generate(draft,request,rendered=True,prefix_cache={**scope,'operation':'capture'})
    from dataclasses import replace
    result=backend.generate(full,replace(request,prompt_hash=prompt_identity(full,backend.tokenizer)),rendered=True,prefix_cache={**scope,'operation':'reuse'})
    assert observed == [a,b]  # Mutation: passing full prompt to warm cache or retaining draft token breaks this.
    assert result.prompt_token_ids == b and result.telemetry['reused_prompt_tokens'] == common
    assert d.telemetry['captured_prefix_tokens'] == common
    assert result.telemetry['processed_prompt_tokens'] == 2
    assert result.generated_token_ids == [999]


def test_cache_identity_rejects_mutation_and_single_use(monkeypatch):
    assert hasattr(generation.Reader,'answer_with_prefix'), 'reader prefix API missing'
    from dataclasses import replace
    from outcome_poc.schemas import GenerationRequest
    from outcome_poc.generation import prompt_identity
    backend,observed=fake_native(monkeypatch)
    a,b='1 2 3','1 2 4'
    scope={'scope':'question/job','target_prompt':b,'source_prompt_hash':prompt_identity(a,backend.tokenizer)}
    request=GenerationRequest('r','m',prompt_identity(a,backend.tokenizer),'d','answer',8192,256,120.,'within_query_prefix')
    def capture(): backend.generate(a,request,rendered=True,prefix_cache={**scope,'operation':'capture'})
    for changes in ({'scope':'other question'},{'target_prompt':'1 2 5'},{'source_prompt_hash':'other draft'}):
        capture()
        with pytest.raises(ValueError,match='prefix'):
            backend.generate(b,replace(request,prompt_hash=prompt_identity(b,backend.tokenizer)),rendered=True,prefix_cache={**scope,**changes,'operation':'reuse'})
    capture()
    req=replace(request,prompt_hash=prompt_identity(b,backend.tokenizer))
    backend.generate(b,req,rendered=True,prefix_cache={**scope,'operation':'reuse'})
    with pytest.raises(ValueError,match='prefix'):
        backend.generate(b,req,rendered=True,prefix_cache={**scope,'operation':'reuse'})


def test_identical_prompt_keeps_last_token_for_logits(monkeypatch):
    from outcome_poc.schemas import GenerationRequest
    from outcome_poc.generation import prompt_identity
    backend,observed=fake_native(monkeypatch)
    text='1 2 3'
    scope={'scope':'q','target_prompt':text,'source_prompt_hash':prompt_identity(text,backend.tokenizer)}
    request=GenerationRequest('r','m',scope['source_prompt_hash'],'d','answer',8192,256,120.,'within_query_prefix')
    backend.generate(text,request,rendered=True,prefix_cache={**scope,'operation':'capture'})
    result=backend.generate(text,request,rendered=True,prefix_cache={**scope,'operation':'reuse'})
    assert observed == [[1,2,3],[1,2,3]]
    assert result.telemetry['reused_prompt_tokens'] == 2
    assert result.telemetry['processed_prompt_tokens'] == 1


def test_prefix_action_signature_stays_distinct_from_fresh(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    a=runner._bound_action_signature(job['task'],runtime,job['task'].candidate_ids,'none')
    b=runner._bound_action_signature(job['task'],runtime,job['task'].candidate_ids,'within_query_prefix')
    assert a != b


@pytest.mark.parametrize('mutation',['template','decoding','limit','model','evidence'])
def test_prefix_rejects_changed_inputs(monkeypatch,mutation):
    from dataclasses import replace
    from outcome_poc.schemas import GenerationRequest
    from outcome_poc.generation import prompt_identity
    backend,observed=fake_native(monkeypatch)
    a,b='1 2 3','1 2 4'
    scope={'scope':'q','target_prompt':b,'source_prompt_hash':prompt_identity(a,backend.tokenizer)}
    req=GenerationRequest('r','m',scope['source_prompt_hash'],'d','answer',8192,256,120.,'within_query_prefix')
    backend.generate(a,req,rendered=True,prefix_cache={**scope,'operation':'capture'})
    if mutation == 'template': backend.tokenizer.chat_template='changed'
    if mutation == 'decoding': req=replace(req,decoding_hash='changed')
    if mutation == 'limit': req=replace(req,max_new_tokens=128)
    if mutation == 'model': req=replace(req,model_hash='changed')
    if mutation == 'evidence': b='1 2 9'
    req=replace(req,prompt_hash=prompt_identity(b,backend.tokenizer))
    with pytest.raises(ValueError): backend.generate(b,req,rendered=True,prefix_cache={**scope,'operation':'reuse'})
    assert len(observed) == 1


def test_native_prefix_full_event_links_to_paid_source(tmp_path):
    """A cache continuation must preserve its source paid event in the durable ledger."""
    from dataclasses import replace
    from outcome_poc.policies import PostOutcomePolicy
    runtime,job,_=fixture_runtime(tmp_path)
    original=runtime.reader.backend.generate
    handles=[]
    def generate(prompt,request,*,rendered=False,prefix_cache=None):
        handles.append(prefix_cache)
        return original(prompt,replace(request,cache_mode='none'),rendered=rendered)
    runtime.reader.backend.generate=generate
    policy=PostOutcomePolicy(None,{'threshold_mode':'always_ten','threshold':None})
    runner.execute_job({**job,'policy':policy,'cache_mode':'within_query_prefix'},runtime,tmp_path)
    events=[e for e in runner.load_events(tmp_path) if e.role.startswith('generation:')]
    assert len(events) == 2
    assert events[1].source_event_id == events[0].event_id
    assert handles[0]['operation']=='capture' and handles[1]['operation']=='reuse'
    assert handles[0]['scope']==handles[1]['scope']


def test_timeout_discards_clean_handle_without_free_regeneration(monkeypatch):
    from dataclasses import replace
    from outcome_poc.schemas import GenerationRequest
    from outcome_poc.generation import prompt_identity
    import sys
    backend,observed=fake_native(monkeypatch)
    original=sys.modules['mlx_lm'].stream_generate
    def timed_out(*args,**kwargs):
        yield from original(*args,**kwargs)
        raise TimeoutError('after paid draft continuation')
    monkeypatch.setattr(sys.modules['mlx_lm'],'stream_generate',timed_out)
    a,b='1 2 3','1 2 4'
    scope={'scope':'q','target_prompt':b,'source_prompt_hash':prompt_identity(a,backend.tokenizer)}
    req=GenerationRequest('r','m',scope['source_prompt_hash'],'d','answer',8192,256,120.,'within_query_prefix')
    result=backend.generate(a,req,rendered=True,prefix_cache={**scope,'operation':'capture'})
    assert result.status == 'timeout' and result.generated_token_ids == [999]
    with pytest.raises(ValueError,match='prefix'):
        backend.generate(b,replace(req,prompt_hash=prompt_identity(b,backend.tokenizer)),rendered=True,prefix_cache={**scope,'operation':'reuse'})
    assert len(observed)==1

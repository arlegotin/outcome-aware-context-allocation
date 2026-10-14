"""Annotation-free serving, durable per-job attempts and a development harness.

Single-writer run directories. Nested events explain cost; only enclosing serving
intervals enter serving totals. No protected scheduler is enabled here.
"""
from dataclasses import dataclass, field, fields, replace
import hashlib
import json
from pathlib import Path
import random
import re
import time
from types import MappingProxyType

from .data_runtime import Task
from .generation import ANSWER_SYSTEM, Reader, render_prompt, prompt_identity, ranking_aliases
from .schemas import CostEvent, GenerationRequest, PaidDraft, Prediction, ReaderResult, validate_record
from .storage import append_jsonl, atomic_json, canonical_bytes, content_hash, read_jsonl
from .timing import TimingLedger


@dataclass
class Runtime:
    retrieval: object
    documents: object
    reader: object
    config: dict
    clock: object = time.perf_counter_ns
    serialize: object = canonical_bytes
    events: list = field(default_factory=list)
    decision_payload: dict | None = None
    payload: bytes | None = None

    def synchronize(self, *, allow_reload=True):
        backend=self.reader.backend
        if not allow_reload and hasattr(backend,'worker_pid') and backend.worker_pid is None:
            return
        backend.synchronize()


def action_signature(task: Task, config: dict, evidence_ids: list[str], role: str, cache_mode: str) -> str:
    validate_record(task)
    return content_hash({'task':task,'config':config,'evidence_ids':evidence_ids,
                         'role':role,'cache_mode':cache_mode})


def job_id(signature: str, mode: str, repetition_id: int) -> str:
    family,_,arm=mode.partition(':') if type(mode) is str else ('','','')
    if family not in {'direct','replay'} or (':' in mode and not arm) or type(repetition_id) is not int or repetition_id < 0:
        raise ValueError('invalid job mode/repetition')
    return content_hash({'action_signature':signature,'mode':mode,'repetition_id':repetition_id})


def job_rng(job: dict) -> random.Random:
    """Per-job random state is reproducible across interruption/reordering."""
    return random.Random(int(content_hash([271828,job['job_id']]),16))


def _result(raw):
    raw = dict(raw)
    raw['citations'] = [tuple(c) for c in raw['citations']]
    result = ReaderResult(**raw)
    validate_record(result)
    return result


def _prediction(raw):
    raw = dict(raw)
    raw['citations'] = [(c['doc_id'],c['sentence_index']) if isinstance(c,dict) else tuple(c)
                        for c in raw['citations']]
    result = Prediction(**raw)
    validate_record(result)
    return result


def _empty(status,reason):
    return ReaderResult('',None,[],status,0,0,[],[],reason)


def _policy_id(policy):
    identity = getattr(policy,'policy_id',None)
    if type(identity) is not str or not identity:
        raise ValueError('policy must expose policy_id')
    return identity


def serve(task: Task, policy: object, runtime: object, job: dict) -> Prediction:
    """Serve one attempt; every paid call has an explicit role and one event.

    POST policies opt in via requires_draft=True. The initial fixed-two draft is
    paid once; choose receives its event-backed PaidDraft. A two decision reuses
    this paid result inside the same query, while ten pays a second answer.
    """
    validate_record(task)
    if task.split not in {'pilot','fit','tune'}:
        raise ValueError('protected serving blocked until protocol/sample verification')
    if job.get('cache_mode','none') not in {'none','within_query_prefix','development_replay'}:
        raise ValueError('native serving supports fresh generation or explicit development replay only')
    if job.get('mode','direct') not in {'direct','replay'}:
        raise ValueError('unknown serving mode')
    if job.get('mode','direct') == 'direct' and (
            job.get('cache_mode','none') == 'development_replay' or 'replay_prediction' in job):
        raise ValueError('direct mode refuses answer-cache reuse')
    if job.get('cache_mode','none') == 'development_replay':
        return _replay(task,policy,runtime,job)
    pid = _policy_id(policy)
    if pid == 'NO-CONTEXT-DIAGNOSTIC' and not job.get('allow_no_context_diagnostic',False):
        raise ValueError('runtime must explicitly opt into no-context diagnostic')
    ledger = TimingLedger({**job,'task':task},pid,runtime.clock)
    runtime.events = ledger.events
    backend=runtime.reader.backend
    backend.job_owner=_worker_owner(job,pid)
    _check_pending_recovery(backend)
    runtime.synchronize()
    _consume_worker_lifecycle(runtime,job,ledger)
    start = runtime.clock()
    runtime.service_start_ns=start
    runtime.last_paid_result=None
    aliases, evidence, prompt_hash, decision = {},[],content_hash('no-prompt'),None
    generated, calls = _empty('budget_exhausted','budget_exhausted'),0
    config = runtime.config
    prefix = None
    if job.get('cache_mode') == 'within_query_prefix' and not getattr(policy,'requires_draft',False):
        raise ValueError('within-query prefix mode is POST only')
    def paid(budget, role):
        nonlocal calls,prompt_hash,evidence
        with ledger.component('evidence:'+role):
            evidence = [runtime.documents.get(row.doc_id) for row in ranked[:budget]]
        with ledger.component('prompt:'+role):
            prompt = render_prompt(task.question,evidence,aliases,runtime.reader.backend.tokenizer,
                                   'judge' if role == 'judge' else 'answer')
            prompt_hash = prompt_identity(prompt,runtime.reader.backend.tokenizer)
            request = GenerationRequest(config['model_revision'],config['model_hash'],prompt_hash,
                config['decoding_hash'],'judge' if role == 'judge' else 'answer',config['max_context_tokens'],
                16 if role == 'judge' else config['max_new_tokens'],config['timeout_seconds'],job.get('cache_mode','none'))
        generation_start = runtime.clock()
        active = job.get('_attempt_dir')
        if active:
            atomic_json(active / f'paid-{calls+1}.started.json',{
                'role':'generation:'+role,'start_ns':generation_start,'request':request})
        calls += 1
        last_partial={'text':'','prompt_ids':[],'token_ids':[]}
        backend=runtime.reader.backend
        previous_progress=getattr(backend,'progress_callback',None)
        def progress(text,prompt_ids,token_ids):
            last_partial.update(text=text,prompt_ids=list(prompt_ids),token_ids=list(token_ids))
            if active: atomic_json(active / f'paid-{calls}.partial.json',last_partial)
            if previous_progress: previous_progress(text,prompt_ids,token_ids)
        backend.progress_callback=progress
        try:
            cache_args = {}
            if prefix is not None:
                handle = {**prefix,'operation':'capture' if role == 'draft' else 'reuse'}
                if role == 'draft':
                    prefix['source_prompt_hash'] = prompt_hash
                    handle['source_prompt_hash'] = prompt_hash
                cache_args['prefix_cache'] = handle
            result = backend.generate(prompt,request,rendered=True,**cache_args)
            validate_record(result)
        except Exception as error:
            result = ReaderResult(last_partial['text'],None,[],'infra_error',
                len(last_partial['prompt_ids']),len(last_partial['token_ids']),last_partial['prompt_ids'],
                last_partial['token_ids'],f'{type(error).__name__}:{error}')
        finally:
            backend.progress_callback=previous_progress
        event = ledger.event('generation:'+role,generation_start,runtime.clock(),
                             status=result.status,result=result,resources=getattr(backend,'last_resources',None),
                             source=draft.generation_event_id if prefix is not None and role == 'answer' else None)
        runtime.last_paid_result=result
        if active:
            partial=active / f'paid-{calls}.partial.json'
            atomic_json(active / f'paid-{calls}.finished.json',{'event':event,'result':result,
                'started_receipt_sha256':_digest(active / f'paid-{calls}.started.json'),
                'partial_receipt_sha256':_digest(partial) if partial.exists() else None})
        _consume_worker_lifecycle(runtime,job,ledger,serving_window=(start,runtime.clock()))
        _record_pending_recovery(backend)
        with ledger.component('parse:'+role):
            if role == 'judge':
                status = result.status if result.status in {'timeout','infra_error','budget_exhausted','context_overflow'} else (
                    'ok' if result.stop_reason == 'stop' and result.raw_output.strip() in {'SUFFICIENT','INSUFFICIENT'} else 'parse_error')
                result = replace(result,status=status,answer=None,citations=[])
            else:
                result = Reader.parse_generated(result,evidence,aliases)
        return result,event
    try:
        with ledger.component('retrieval'):
            ranked = runtime.retrieval.rank(task.question,task.candidate_ids)
            aliases = ranking_aliases(ranked)
        if job.get('cache_mode') == 'within_query_prefix' and 0 < min(2,len(ranked)) <= job.get('caller_cap',10):
            with ledger.component('prefix_target'):
                full_evidence = [runtime.documents.get(row.doc_id) for row in ranked]
                prefix = {'scope':content_hash([task,job['job_id'],job.get('attempt',1)]),
                          'target_prompt':render_prompt(task.question,full_evidence,aliases,backend.tokenizer),
                          'source_prompt_hash':None}
        draft, judge = None, None
        if getattr(policy,'requires_judge',False):
            if 0 < min(2,len(ranked)) <= job.get('caller_cap',10):
                generated,event = paid(min(2,len(ranked)),'judge')
                judge = PaidDraft(event.event_id,generated)
        if getattr(policy,'requires_draft',False):
            if min(2,len(ranked)) == 0 or min(2,len(ranked)) > job.get('caller_cap',10):
                generated = _empty('budget_exhausted','budget_exhausted')
            else:
                generated,event = paid(min(2,len(ranked)),'draft')
                draft = PaidDraft(event.event_id,generated)
        eligible = ((not getattr(policy,'requires_draft',False) or draft is not None)
                    and (not getattr(policy,'requires_judge',False) or judge is not None))
        if eligible:
            with ledger.component('routing'):
                decision = policy.choose(task.question,ranked,draft,caller_cap=job.get('caller_cap',10),
                                         **({'paid_judge':judge} if judge is not None else {}))
                validate_record(decision)
                if decision.policy_id != pid:
                    raise ValueError('policy decision identity mismatch')
            budget = decision.effective_budget if decision.effective_budget is not None else min(decision.action_k,len(ranked))
            if pid != 'NO-CONTEXT-DIAGNOSTIC':
                expected=min(decision.action_k,len(ranked))
                if expected==0 or expected>job.get('caller_cap',10): expected=0
                if (decision.requested_budget not in {None,decision.action_k} or budget!=expected or
                        (budget==0 and decision.reason!='budget_exhausted')):
                    raise ValueError('decision requested/effective budget violates caller/packet limits')
            if budget == 0 and pid != 'NO-CONTEXT-DIAGNOSTIC':
                generated = _empty('budget_exhausted','budget_exhausted')
            elif (draft is not None or judge is not None) and generated.status in {'timeout','infra_error'}:
                pass  # An infrastructure/timeout draft cannot invisibly trigger another answer.
            elif draft is None or budget != min(2,len(ranked)):
                generated,_ = paid(budget,'answer')
    except Exception as error:
        generated = replace(runtime.last_paid_result or generated,status='infra_error',answer=None,citations=[],stop_reason=f'{type(error).__name__}:{error}')
    runtime.decision_payload = {'decision':decision,'aliases':aliases,'stop_reason':generated.stop_reason,
        'action_signature':_bound_action_signature(task,runtime,[d.doc_id for d in evidence],job.get('cache_mode','none'))}
    prediction = Prediction(job['run_id'],task.task_id,pid,job['protocol_hash'],job['job_id'],
        job.get('attempt',1),job.get('repetition_id',0),[d.doc_id for d in evidence],
        generated.raw_output,generated.answer,generated.citations,generated.status,
        config['model_revision'],prompt_hash,config['decoding_hash'],0.,
        generated.prompt_tokens,generated.generated_tokens,calls,
        [event.event_id for event in ledger.events if event.role.startswith('generation:')])
    runtime.last_prediction=prediction
    try:
        with ledger.component('payload'):
            # This bound artifact omits the enclosing interval, preventing self-reference.
            runtime.payload = runtime.serialize({'prediction':_answer_payload(prediction),'decision':runtime.decision_payload})
        sync_start=runtime.clock()
        try:
            runtime.synchronize(allow_reload=False)
        except Exception:
            ledger.event('synchronization_failure',sync_start,runtime.clock(),status='infra_error')
            raise
    except Exception as error:
        prediction=replace(prediction,status='infra_error',answer=None,citations=[])
        runtime.decision_payload['stop_reason']=f'{type(error).__name__}:{error}'
        with ledger.component('failure_payload'):
            runtime.payload=canonical_bytes({'prediction':_answer_payload(prediction),'decision':runtime.decision_payload})
    finally:
        _record_pending_recovery(backend)
    stop = runtime.clock()
    ledger.event('serving',start,stop,status=prediction.status,result=generated)
    return replace(prediction,elapsed_seconds=(stop-start)/1e9)


def _replay(task,policy,runtime,job):
    if job.get('mode') != 'replay' or task.split not in {'pilot','fit','tune'}:
        raise ValueError('replay is development only')
    source = job['replay_prediction']
    events = job['replay_events']
    validate_record(source)
    if source.task_id != task.task_id or source.policy_id != _policy_id(policy):
        raise ValueError('replay source identity mismatch')
    if job.get('replay_signature') != _bound_action_signature(task,runtime,source.evidence_ids):
        raise ValueError('replay original action signature mismatch')
    if source.model_revision != runtime.config['model_revision'] or source.decoding_hash != runtime.config['decoding_hash']:
        raise ValueError('replay model/decoding identity mismatch')
    _validate_events(source,events)
    copied=[]
    mapping={}
    for event in events:
        identity = content_hash([job['job_id'],job.get('attempt',1),event.event_id])
        mapping[event.event_id] = identity
        copied.append(replace(event,event_id=identity,run_id=job['run_id'],
            cache_mode='development_replay',source_event_id=event.event_id,attempt=job.get('attempt',1)))
    runtime.events=copied
    result=replace(source,run_id=job['run_id'],job_id=job['job_id'],attempt=job.get('attempt',1),
                   repetition_id=job.get('repetition_id',0),event_ids=[mapping[e] for e in source.event_ids])
    runtime.decision_payload={'replay_source_job_id':source.job_id}
    runtime.payload=canonical_bytes({'prediction':_answer_payload(result),'decision':runtime.decision_payload})
    return result


def _read(path):
    def reject(value): raise ValueError('nonfinite transaction JSON')
    row=json.loads(path.read_bytes(),parse_constant=reject)
    canonical_bytes(row)
    return row


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_events(prediction,events):
    ids=[e.event_id for e in events]
    if len(ids) != len(set(ids)): raise ValueError('duplicate cost event')
    generation=[e for e in events if e.role.startswith('generation:')]
    if len(generation) != prediction.generation_calls or set(prediction.event_ids) != {e.event_id for e in generation}:
        raise ValueError('missing/unbound paid generation event')
    boundaries=[e for e in events if e.role == 'serving']
    if len(boundaries) != 1 or boundaries[0].elapsed_seconds != prediction.elapsed_seconds:
        raise ValueError('missing/mismatched enclosing serving event')
    for e in events:
        validate_record(e)
        if e.elapsed_seconds != (e.stop_ns-e.start_ns)/1e9:
            raise ValueError('cost event duration does not bind timestamps')
        if (e.run_id,e.task_id,e.policy_id,e.attempt) != (prediction.run_id,prediction.task_id,prediction.policy_id,prediction.attempt):
            raise ValueError('cost event identity mismatch')


def load_events(run_dir: Path) -> list[CostEvent]:
    events=[]
    for attempt_dir in sorted(Path(run_dir).glob('jobs/*/attempt-*')):
        if (attempt_dir/'observed-failure.closed.json').exists():
            _,observed=_observed_failure(attempt_dir)
            events+=observed
        elif (attempt_dir/'events.jsonl').exists():
            events+=[CostEvent(**row) for row in read_jsonl(attempt_dir/'events.jsonl')]
        events+=_owned_reloads(attempt_dir)
    return events


def _complete(directory,expected_job=None):
    marker=_read(directory / 'completion.json')
    prediction_path=directory / marker['prediction_path']
    if _digest(prediction_path) != marker['prediction_sha256']:
        raise ValueError('completion prediction checksum mismatch')
    if _digest(prediction_path.parent / 'events.jsonl') != marker['events_sha256']:
        raise ValueError('completion event checksum mismatch')
    ready=_read(prediction_path.parent / 'ready.json')
    if any(_digest(prediction_path.parent / name) != digest for name,digest in ready['hashes'].items()):
        raise ValueError('completion artifact checksum mismatch')
    prediction=_prediction(_read(prediction_path))
    events=[CostEvent(**row) for row in read_jsonl(prediction_path.parent / 'events.jsonl')]
    _validate_events(prediction,events)
    if expected_job and (prediction.job_id != expected_job['job_id'] or
            prediction.task_id != expected_job['task'].task_id or prediction.policy_id != _policy_id(expected_job['policy'])):
        raise ValueError('completion assigned identity mismatch')
    return prediction


def _commit(directory,attempt_dir,prediction):
    atomic_json(directory / 'completion.json',{'prediction_path':str((attempt_dir / 'prediction.json').relative_to(directory)),
        'prediction_sha256':_digest(attempt_dir / 'prediction.json'),'events_sha256':_digest(attempt_dir / 'events.jsonl')})


def _job_identity(job,runtime):
    policy=job['policy']
    return content_hash({'task':job['task'],'config':runtime.config,'policy_id':_policy_id(policy),
        'installed_chat_template_hash':content_hash(runtime.reader.backend.tokenizer.chat_template),
        'policy_config':getattr(policy,'config',None),'k':getattr(policy,'k',None),
        'buffer':getattr(policy,'buffer',None),'requires_draft':getattr(policy,'requires_draft',False),'requires_judge':getattr(policy,'requires_judge',False),
        'protocol_hash':job['protocol_hash'],'mode':job.get('mode','direct'),
        'cache_mode':job.get('cache_mode','none'),'caller_cap':job.get('caller_cap',10),
        'arm':job.get('arm'),'repetition_id':job.get('repetition_id',0),'allow_no_context_diagnostic':job.get('allow_no_context_diagnostic',False)})


def execute_job(job: dict, runtime: object, run_dir: Path) -> Prediction:
    """Resume a verified commit, recover a finished transaction, or rerun infra explicitly."""
    if type(job['job_id'])!=str or not job['job_id'] or Path(job['job_id']).name!=job['job_id'] or job['job_id'] in {'.','..'}:
        raise ValueError('job identity must be a safe path component')
    directory=Path(run_dir) / 'jobs' / job['job_id']
    closed=Path(run_dir) / 'predictions.closed.json'
    if closed.exists() and (job['job_id'] not in _read(closed)['assigned_job_ids'] or not (directory / 'completion.json').exists()):
        raise ValueError('closed run cannot execute an unassigned/new job')
    directory.mkdir(parents=True,exist_ok=True)
    identity=_job_identity(job,runtime)
    identity_path=directory / 'identity.json'
    if identity_path.exists():
        if _read(identity_path)['identity'] != identity: raise ValueError('resume job identity changed')
    else: atomic_json(identity_path,{'identity':identity})
    previous=None
    attempts=sorted(directory.glob('attempt-*'),key=lambda p:int(p.name.split('-')[-1]))
    if (directory / 'completion.json').exists():
        committed=_complete(directory,job)
        if committed.attempt==int(attempts[-1].name.split('-')[-1]):
            previous=committed
            if previous.status!='infra_error' or not job.get('retry_infrastructure',False): return previous
    if attempts and previous is None:
        last=attempts[-1]
        if (last / 'observed-failure.closed.json').exists():
            previous,_=_observed_failure(last)
            if not job.get('retry_infrastructure',False): return previous
        elif (last / 'ready.json').exists():
            ready=_read(last / 'ready.json')
            if any(_digest(last / name) != digest for name,digest in ready['hashes'].items()):
                raise ValueError('interrupted transaction checksum mismatch')
            previous=_prediction(_read(last / 'prediction.json'))
            _validate_events(previous,[CostEvent(**row) for row in read_jsonl(last / 'events.jsonl')])
            _commit(directory,last,previous)
            if previous.status!='infra_error' or not job.get('retry_infrastructure',False): return previous
        else:
            _recover_interrupted(last,job,runtime,Path(run_dir))
    attempt=(int(attempts[-1].name.split('-')[-1])+1) if attempts else 1
    attempt_dir=directory / f'attempt-{attempt}'
    attempt_dir.mkdir()
    attempt_job={**job,'attempt':attempt,'_attempt_dir':attempt_dir,'_run_dir':Path(run_dir).resolve()}
    atomic_json(attempt_dir / 'started.json',{'start_ns':runtime.clock(),'job_id':job['job_id'],
                                            'attempt':attempt,'clock_kind':'monotonic'})
    append_jsonl(Path(run_dir) / 'attempts.jsonl',{'job_id':job['job_id'],'attempt':attempt,
        'previous_attempt':attempt-1 if attempt>1 else None,'status':'started'})
    runtime.service_start_ns=None
    runtime.last_prediction=None
    runtime.events=[]
    runtime.decision_payload={}
    runtime.payload=None
    try:
        prediction=serve(job['task'],job['policy'],runtime,attempt_job)
    except Exception as error:
        if runtime.service_start_ns is None and isinstance(error,ValueError): raise
        prediction=_certify_observed_serving_failure(attempt_job,runtime,attempt_dir,error)
    telemetry_start=runtime.clock()
    try:
        for event in runtime.events: append_jsonl(attempt_dir / 'events.jsonl',event)
        # Persist the serialized artifact verbatim via atomic_json after decoding canonical JSON.
        atomic_json(attempt_dir / 'payload.json',json.loads(runtime.payload))
        atomic_json(attempt_dir / 'prediction.json',prediction)
        telemetry_stop=runtime.clock()
        ledger=TimingLedger(attempt_job,prediction.policy_id,runtime.clock)
        ledger.events=list(runtime.events)
        overhead=ledger.event('telemetry',telemetry_start,telemetry_stop)
        append_jsonl(attempt_dir / 'events.jsonl',overhead)
        atomic_json(attempt_dir / 'decision.json',runtime.decision_payload)
        atomic_json(attempt_dir / 'ready.json',{'hashes':{name:_digest(attempt_dir / name)
            for name in ('prediction.json','payload.json','events.jsonl','decision.json')}})
        append_jsonl(Path(run_dir) / 'attempts.jsonl',{'job_id':job['job_id'],'attempt':attempt,
            'previous_attempt':attempt-1 if attempt>1 else None,'status':prediction.status})
        if prediction.status in {'infra_error','timeout','parse_error','invalid_citation','context_overflow','budget_exhausted'}:
            append_jsonl(Path(run_dir) / 'errors.jsonl',{'job_id':job['job_id'],'attempt':attempt,
                'status':prediction.status,'reason':runtime.decision_payload.get('stop_reason')})
        _commit(directory,attempt_dir,prediction)
        return prediction
    except Exception as error:
        # A post-commit exception must not mutate an already durable transaction.
        if (directory/'completion.json').exists():
            committed=_complete(directory,job)
            if committed.attempt==attempt: return committed
        failed=replace(prediction,status='infra_error',answer=None,citations=[])
        ledger=TimingLedger(attempt_job,failed.policy_id,runtime.clock)
        ledger.events=[replace(event,status='infra_error') if event.role=='serving' else event
                       for event in runtime.events]
        ledger.event('telemetry',telemetry_start,runtime.clock(),status='infra_error')
        row={'prediction':failed,'events':ledger.events,'payload':json.loads(runtime.payload),
             'decision':runtime.decision_payload,'error':f'{type(error).__name__}:{error}',
             'paid_receipt_hashes':{path.name:_digest(path) for path in sorted(attempt_dir.glob('paid-*.json'))}}
        # If certification writes fail too, leave the original attempt untouched;
        # a later observer must use conservative unobserved recovery and block closure.
        digest=atomic_json(attempt_dir/'observed-failure.json',row)
        atomic_json(attempt_dir/'observed-failure.closed.json',{'receipt_sha256':digest})
        append_jsonl(Path(run_dir)/'attempts.jsonl',{'job_id':job['job_id'],'attempt':attempt,
            'previous_attempt':attempt-1 if attempt>1 else None,'status':'infra_error','observed':True})
        append_jsonl(Path(run_dir)/'errors.jsonl',{'job_id':job['job_id'],'attempt':attempt,
            'status':'infra_error','reason':row['error'],'observed':True})
        return failed


def _recover_interrupted(attempt_dir,job,runtime,run_dir):
    if (attempt_dir / 'interrupted.json').exists(): return
    start=_read(attempt_dir / 'started.json')['start_ns']
    stop=runtime.clock()
    if stop < start: raise ValueError('interrupted clock epoch changed')
    attempt=int(attempt_dir.name.split('-')[-1])
    ledger=TimingLedger({**job,'attempt':attempt},_policy_id(job['policy']),runtime.clock)
    # Recovery uses a conservative full interval through observation, including downtime.
    # It cannot certify an exact interrupted latency; closure stays invalid.
    for path in sorted(attempt_dir.glob('paid-*.finished.json')):
        ledger.events.append(CostEvent(**_read(path)['event']))
    for path in sorted(attempt_dir.glob('paid-*.started.json')):
        if not path.with_name(path.name.replace('.started.','.finished.')).exists():
            row=_read(path)
            ledger.event(row['role'],row['start_ns'],stop,status='infra_error')
    ledger.event('serving',start,stop,status='infra_error')
    recovery_path=attempt_dir / 'recovered-events.jsonl'
    for event in ledger.events: append_jsonl(recovery_path,event)
    atomic_json(attempt_dir / 'interrupted.json',{'status':'infra_error','cost_certified':False,
        'reason':'unobserved_process_termination','elapsed_upper_bound_seconds':(stop-start)/1e9})
    append_jsonl(run_dir / 'attempts.jsonl',{'job_id':job['job_id'],'attempt':attempt,
        'status':'interrupted','previous_attempt':attempt-1 if attempt>1 else None})


def accounting(run_dir: Path, prediction: Prediction) -> dict:
    """All warm attempts enter serving; experiment additionally includes telemetry/setup.

    Offline/shared setup charges must be allocated explicitly by a later scheduler.
    Never infer them from missing counters or from prediction's diagnostic interval.
    """
    directory=Path(run_dir) / 'jobs' / prediction.job_id
    closed=Path(run_dir)/'predictions.closed.json'
    if closed.exists() and _supplement_hashes(run_dir)!=_read(closed).get('supplement_hashes',{}):
        raise ValueError('closed accounting supplement checksum mismatch')
    shared=Path(run_dir) / 'shared-costs.jsonl'
    rows=list(read_jsonl(shared)) if shared.exists() else []
    _validate_shared_costs(rows)
    return _accounting_local(run_dir,prediction,_shared_allocations(rows).get(prediction.job_id,()))


def _shared_allocations(rows):
    index={}
    for row in rows:
        amount=row['elapsed_seconds']/len(row['assigned_job_ids'])
        for identity in row['assigned_job_ids']:
            index.setdefault(identity,[]).append(amount)
    return index


def _accounting_local(run_dir, prediction, shared_amounts):
    directory=Path(run_dir) / 'jobs' / prediction.job_id
    if _complete(directory) != prediction: raise ValueError('final prediction completion mismatch')
    serving,experiment=0.,0.
    final_seen=False
    for attempt_dir in directory.glob('attempt-*'):
        path=attempt_dir / 'events.jsonl'
        if (attempt_dir / 'interrupted.json').exists():
            raise ValueError('uncertified interrupted infrastructure cost')
        if (attempt_dir/'observed-failure.closed.json').exists():
            record,events=_observed_failure(attempt_dir)
        else:
            if not path.exists(): raise ValueError('missing attempt event ledger')
            events=[CostEvent(**row) for row in read_jsonl(path)]
            ready=_read(attempt_dir / 'ready.json')
            if any(_digest(attempt_dir / name) != digest for name,digest in ready['hashes'].items()):
                raise ValueError('attempt event/artifact checksum mismatch')
            record=_prediction(_read(attempt_dir / 'prediction.json'))
            _validate_events(record,events)
        if record.attempt == prediction.attempt:
            final_seen=True
            if record != prediction: raise ValueError('prediction ledger mismatch')
        reloads=_owned_reloads(attempt_dir)
        events+=reloads
        _validate_events(record,events)
        boundary=sum(e.elapsed_seconds for e in events if e.role == 'serving')
        transfer=sum(e.elapsed_seconds for e in events if e.role=='worker_reload_transfer')
        serving+=boundary-transfer+sum(e.elapsed_seconds for e in events if e.role=='worker_reload')
        experiment+=boundary-transfer+sum(e.elapsed_seconds for e in events if e.role in {'telemetry','setup','warmup','worker_reload','offline'})
    if not final_seen: raise ValueError('missing final attempt event ledger')
    for amount in shared_amounts:
        experiment+=amount
    return {'total_serving_seconds':serving,'total_experiment_seconds':experiment}


def close_run(run_dir: Path, expected_jobs: list[dict]) -> dict:
    run_dir=Path(run_dir)
    ids=[job['job_id'] for job in expected_jobs]
    if not ids or len(ids) != len(set(ids)): raise ValueError('assigned jobs must be nonempty and unique')
    actual={path.name for path in (run_dir / 'jobs').iterdir() if path.is_dir()}
    if actual != set(ids): raise ValueError('assigned job set is incomplete or contains extras')
    predictions=[]
    for job in expected_jobs:
        directory=run_dir / 'jobs' / job['job_id']
        if not (directory / 'completion.json').exists(): raise ValueError('assigned terminal record missing')
        result=_complete(directory,job)
        if result.status == 'infra_error': raise ValueError('unresolved infrastructure failure')
        for attempt_dir in directory.glob('attempt-*'):
            _check_recovery_settled(attempt_dir)
        accounting(run_dir,result)
        predictions.append(result)
    closed=run_dir/'predictions.closed.json'
    if closed.exists():
        # Re-closing is validation, never a new attestation of changed bytes.
        validate_closed_accounting(run_dir,predictions)
        return _read(closed)
    _validate_forward_paid_receipts(run_dir,predictions)
    # Hash-bound files for downstream scoring, with exactly one terminal row per job.
    path=run_dir / 'predictions.jsonl'
    if path.exists():
        if path.read_bytes() != b''.join(canonical_bytes(p)+b'\n' for p in predictions):
            raise ValueError('closed predictions differ')
    else:
        for prediction in predictions: append_jsonl(path,prediction)
    shared=run_dir / 'shared-costs.jsonl'
    if shared.exists():
        rows=list(read_jsonl(shared));_validate_shared_costs(rows)
        if any(not set(row['assigned_job_ids'])<=set(ids) for row in rows):
            raise ValueError('shared cost allocation includes unassigned job')
    marker={'closure_version':2,'paid_receipt_hashes':_paid_receipt_hashes(run_dir),
            'prediction_sha256':_digest(path),'record_count':len(predictions),
            'shared_costs_sha256':_digest(shared) if shared.exists() else None,
            'supplement_hashes':_supplement_hashes(run_dir),
            'assigned_job_ids':ids,'completion_hashes':{identity:_digest(run_dir / 'jobs' / identity / 'completion.json') for identity in ids}}
    atomic_json(path.with_suffix('.closed.json'),marker)
    return marker


def validate_harness() -> dict:
    """CPU fixture gate only. Native gate is added by CLI orchestration below.

    The analysis/scoring fixture checks execute in a separate subprocess to keep
    the serving import closure annotation-free, even after this function runs.
    """
    import subprocess
    import sys
    script = '''
import json, numpy as np
from outcome_poc.generation import parse_answer
from outcome_poc.schemas import Document, RankedDocument
from outcome_poc.scoring import score_answer, score_support
from outcome_poc.statistics import efficiency, paired_quality_bounds
from outcome_poc.policies import FixedPolicy, ThresholdPolicy
from outcome_poc.storage import content_hash
from types import SimpleNamespace
sentence=['A blue lamp.']; doc=Document(content_hash(['Lamp',sentence]),'Lamp',sentence,12)
a={'D0':doc.doc_id}
raw='{"answer":"blue","citations":[{"doc_id":"D0","sentence_index":0}]}'
x=parse_answer(raw,[doc],a); y=parse_answer(raw,[doc],a)
checks={'aa':x==y,'correct_wrong':score_answer('blue','blue')['em']==1 and score_answer('red','blue')['em']==0,
 'malformed_citation':parse_answer('{"answer":"blue","citations":[{"doc_id":"D9","sentence_index":0}]}',[doc],a).status=='invalid_citation',
 'timeout':parse_answer('partial',[doc],a).status=='parse_error'}
ranked=[RankedDocument(str(i),1-i*.01,i,12,1,'Lamp'+str(i)) for i in range(10)]
p=ThresholdPolicy(None,{'threshold_mode':'always_two','threshold':None})
checks['threshold_alias']=p.choose('Color?',ranked).effective_budget==FixedPolicy(2).choose('Color?',ranked).effective_budget
checks['statistics']=efficiency(np.array([[2.],[4.]]),np.array([0,0]))['reason']=='zero_successes' and paired_quality_bounds(np.array([1,0]),np.array([1,0]),2,.05)['ci']==[0.,0.]
print(json.dumps(checks))
'''
    completed=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,check=True)
    checks=json.loads(completed.stdout)
    # Real serving/recovery fixture runs the same public API used by schedulers.
    from tempfile import TemporaryDirectory
    from types import SimpleNamespace
    from .schemas import Document, RankedDocument
    from .policies import FixedPolicy
    sentences=['A blue lamp.']
    doc=Document(content_hash(['Lamp',sentences]),'Lamp',sentences,sum(map(len,sentences)))
    class Tokenizer:
        chat_template='fixture'
        def apply_chat_template(self,messages,**kwargs): return canonical_bytes(messages).decode()
    class Backend:
        tokenizer=Tokenizer()
        def synchronize(self): pass
        def generate(self,*args,**kwargs):
            return ReaderResult('{"answer":"blue","citations":[{"doc_id":"D0","sentence_index":0}]}',None,[],'ok',1,1,[1],[2],'stop')
    task=Task('fixture','pilot','Color?',[doc.doc_id])
    backend=Backend()
    runtime=Runtime(SimpleNamespace(rank=lambda *args:[RankedDocument(doc.doc_id,1.,0,doc.character_count,1,doc.title)]),
        SimpleNamespace(get=lambda identity:doc),Reader(backend),
        {'model_revision':'fixture','model_hash':'fixture','decoding_hash':'fixture',
         'max_context_tokens':8192,'max_new_tokens':256,'timeout_seconds':1.})
    job={'job_id':'fixture','run_id':'fixture','task':task,'policy':FixedPolicy(2),
         'protocol_hash':'development-unfrozen','mode':'direct','cache_mode':'none','repetition_id':0}
    with TemporaryDirectory() as root:
        result=execute_job(job,runtime,Path(root))
        events=load_events(Path(root))
        checks['cost_ledger']=len([e for e in events if e.role.startswith('generation:')])==1 and accounting(Path(root),result)['total_serving_seconds']>0
        checks['resume']=execute_job(job,runtime,Path(root))==result and close_run(Path(root),[job])['record_count']==1
    from .generation import SupervisedBackend
    request=GenerationRequest('fixture','fixture','fixture','fixture','answer',8192,256,.1,'none')
    with SupervisedBackend(_timeout_factory,startup_timeout=5) as supervisor:
        timeout=supervisor.generate('stall',request,rendered=True)
        checks['timeout']=timeout.status=='timeout' and timeout.stop_reason=='forced_timeout' and supervisor.worker_pid is None and timeout.generated_token_ids==[2]
    return {'passed':all(checks.values()),'checks':checks,'native_calls':0,
            'timeout_record':{'status':timeout.status,'stop_reason':timeout.stop_reason,'partial_tokens':timeout.generated_tokens}}


def main(args) -> int:
    if args.command != 'validate-harness':
        import sys
        print(f"stage unavailable: '{args.command}' blocked until protocol/sample verification",file=sys.stderr)
        return 2
    result=validate_harness()
    config=json.loads(Path(args.config).read_text())
    return _native_harness(config,result)


def _native_harness(config,result):
    return _run_native_gate(config,result)


class _TimeoutBackend:
    tokenizer=None
    def generate(self,prompt,request,*,rendered=False):
        self.progress_callback('partial',[1],[2])
        time.sleep(30)
    def synchronize(self): pass


def _timeout_factory(): return _TimeoutBackend()


def _ledger_bindings(run_dir):
    paths=[Path(run_dir)/name for name in ('predictions.jsonl','predictions.closed.json','shared-costs.jsonl','paid-receipts.sealed.json')]
    paths += list((Path(run_dir)/'jobs').rglob('*'))
    return {str(p.relative_to(run_dir)):_digest(p) if p.is_file() else 'directory' for p in paths if p.exists()}


@dataclass(frozen=True)
class ClosedAccounting:
    """Immutable exact costs from fully validated closed inputs, bound by hashes."""
    run_dir: Path
    bindings: tuple
    index: object
    receipt_coverage: str = 'legacy_unsealed'

    def costs(self, prediction):
        key=content_hash(prediction)
        values=self.index.get(key)
        if values is None: raise ValueError('prediction does not match validated snapshot')
        return dict(zip(('total_serving_seconds','total_experiment_seconds'),values))

    def verify_unchanged(self):
        if _ledger_bindings(self.run_dir) != dict(self.bindings):
            raise ValueError('closed accounting input changed after validation')



def validate_closed_accounting(run_dir: Path,predictions: list[Prediction]) -> ClosedAccounting:
    """Validate the entire assigned closure before a scoring process opens gold."""
    run_dir=Path(run_dir)
    bindings=_ledger_bindings(run_dir)
    marker=_read(run_dir / 'predictions.closed.json')
    coverage=_paid_receipt_coverage(run_dir,marker,predictions)
    if _digest(run_dir / 'predictions.jsonl') != marker['prediction_sha256']:
        raise ValueError('closed accounting prediction checksum mismatch')
    if _supplement_hashes(run_dir)!=marker.get('supplement_hashes',{}):
        raise ValueError('closed accounting supplement checksum mismatch')
    shared=run_dir / 'shared-costs.jsonl'
    if (_digest(shared) if shared.exists() else None)!=marker.get('shared_costs_sha256'):
        raise ValueError('closed accounting shared cost checksum mismatch')
    rows=list(read_jsonl(shared)) if shared.exists() else []
    _validate_shared_costs(rows)
    ids=[p.job_id for p in predictions]
    if len(ids)!=len(set(ids)) or ids!=marker['assigned_job_ids'] or len(ids)!=marker['record_count']:
        raise ValueError('closed accounting assigned denominator mismatch')
    actual={p.name for p in (run_dir / 'jobs').iterdir() if p.is_dir()}
    if actual!=set(ids): raise ValueError('closed accounting assigned job set changed')
    if any(not set(row['assigned_job_ids']) <= set(ids) for row in rows):
        raise ValueError('shared cost allocation includes unassigned job')
    costs={}
    allocated=_shared_allocations(rows)
    for prediction in predictions:
        completion=run_dir / 'jobs' / prediction.job_id / 'completion.json'
        if _digest(completion)!=marker['completion_hashes'][prediction.job_id]:
            raise ValueError('closed accounting completion checksum mismatch')
        if prediction.status=='infra_error': raise ValueError('unresolved infrastructure failure')
        for attempt_dir in completion.parent.glob('attempt-*'):
            _check_recovery_settled(attempt_dir)
        costs[content_hash(prediction)]=tuple(_accounting_local(run_dir,prediction,allocated.get(prediction.job_id,())).values())
    snapshot=ClosedAccounting(run_dir,tuple(sorted(bindings.items())),MappingProxyType(costs),coverage)
    snapshot.verify_unchanged()
    return snapshot


def _validate_shared_costs(rows):
    if len({row['event_id'] for row in rows})!=len(rows):
        raise ValueError('duplicate shared cost event')
    for row in rows:
        ids=row['assigned_job_ids']
        if (row['role'] not in {'cold_setup','warmup','offline'} or not ids or
            len(ids)!=len(set(ids)) or any(type(identity)!=str or not identity for identity in ids) or
            type(row['start_ns'])!=int or type(row['stop_ns'])!=int or
            row['start_ns']<0 or row['stop_ns']<row['start_ns'] or
            row['elapsed_seconds']!=(row['stop_ns']-row['start_ns'])/1e9):
            raise ValueError('invalid shared cost record/allocation')


def record_shared_cost(run_dir: Path,role: str,start_ns: int,stop_ns: int,
                       assigned_job_ids: list[str],source_id: str | None = None) -> str:
    """Record an explicitly measured cold/warmup/offline boundary, equally allocated.

    Source offline elapsed must be its complete attempt boundary, including failed
    attempts. Do not also charge its nested component records or reader load already
    charged as a setup event. Scheduling owns the frozen allocation denominator.
    """
    if (Path(run_dir) / 'predictions.closed.json').exists(): raise ValueError('run is closed')
    row={'role':role,'start_ns':start_ns,'stop_ns':stop_ns,
         'elapsed_seconds':(stop_ns-start_ns)/1e9,'assigned_job_ids':assigned_job_ids,'source_id':source_id}
    row['event_id']=content_hash(row)
    _validate_shared_costs([row])
    path=Path(run_dir) / 'shared-costs.jsonl'
    rows=list(read_jsonl(path)) if path.exists() else []
    _validate_shared_costs(rows+[row])
    append_jsonl(path,row)
    return row['event_id']


def _run_native_gate(config,result):
    """Three development reader calls: synthetic A/A and one pilot pipeline probe."""
    from datetime import datetime,timezone
    import subprocess
    import sys
    import threading
    from types import SimpleNamespace
    from .assets import verify_configured_assets
    from .data_runtime import DocumentStore,load_tasks
    from .environment import discover,resource_gate
    from .generation import NativeReaderFactory,SupervisedBackend,offline_network
    from .policies import FixedPolicy
    from .retrieval import EncoderBackend,Retrieval
    from .schemas import Document,RankedDocument
    import psutil
    root=Path('artifacts/runs') / ('task8-harness-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    root.mkdir(parents=True)
    result.update(private_run_dir=str(root),native_calls=0,errors=[])
    # Independent fresh Python proves OS denials, without the Python socket guard.
    probe='''
import errno,json,socket,sys
checks={}
for index,path in enumerate(sys.argv[1:]):
 try:
  with open(path,'rb') as stream: stream.read(1)
 except PermissionError: checks['file_'+str(index)]=True
 except Exception: checks['file_'+str(index)]=False
 else: checks['file_'+str(index)]=False
sock=socket.socket();sock.settimeout(.1)
try: sock.connect(('1.1.1.1',443))
except OSError as error: checks['network']=error.errno in (errno.EPERM,errno.EACCES)
else: checks['network']=False
finally: sock.close()
print(json.dumps(checks))
'''
    blocked=[Path(config['preparation']['output_dir'])/'gold/gold.jsonl',
             Path(config['preparation']['train_path']),Path(config['preparation']['dev_path'])]
    denial=subprocess.run([sys.executable,'-c',probe,*map(str,blocked)],capture_output=True,text=True,check=True)
    result['os_denials']=json.loads(denial.stdout)
    if not all(result['os_denials'].values()):
        result['passed']=False
        result['errors'].append('native gate requires OS network/gold/raw denials before generation')
        atomic_json(root/'gate.json',result)
        print(json.dumps(result),flush=True)
        return 1
    environment=discover(root/'environment')
    result['native_environment_passed']=environment['native_supported'] and environment['resource_gate']['passed']
    if not result['native_environment_passed']: raise ValueError('native prerequisite gate failed')
    manifest=_read(Path(config['preparation']['asset_manifest']))
    verify_configured_assets({role:config[role] for role in ('reader','encoder','original_reader')},
        {'required':['reader','encoder','original_reader'],'assets':manifest['assets']})
    asset=manifest['assets']['reader']
    settings={'model_revision':asset['revision'],'model_hash':asset['snapshot_hash'],
        'decoding_hash':content_hash({**config['reader'],'temperature':0,'cache_mode':'none',
            'draft_model':None,'max_kv_size':None,'kv_bits':None}),
        'max_context_tokens':config['reader']['max_context_tokens'],
        'max_new_tokens':config['reader']['max_new_tokens'],
        'timeout_seconds':config['reader']['timeout_seconds'],
        'backend':'persistent-supervised-native-mlx','prompt_version':1}
    monitor_stop=threading.Event()
    backend=None
    rss_peak=[psutil.Process().memory_info().rss]
    def monitor():
        while not monitor_stop.wait(.02):
            current=psutil.Process().memory_info().rss
            if backend and backend.worker_pid:
                try: current+=psutil.Process(backend.worker_pid).memory_info().rss
                except psutil.Error: pass
            rss_peak[0]=max(rss_peak[0],current)
    observer=threading.Thread(target=monitor,daemon=True);observer.start()
    jobs=[]
    try:
        with offline_network() as network_attempts:
            print(json.dumps({'stage':'native-reader-load','development_only':True}),flush=True)
            with SupervisedBackend(NativeReaderFactory(Path(asset['local_path']),{**config['reader'],'asset':asset})) as backend:
                sentence=['A blue lamp.']
                doc=Document(content_hash(['Invented lamp',sentence]),'Invented lamp',sentence,sum(map(len,sentence)))
                task=Task('synthetic-aa','pilot','What color is the lamp?',[doc.doc_id])
                ranking=[RankedDocument(doc.doc_id,1.,0,doc.character_count,1,doc.title)]
                runtime=Runtime(SimpleNamespace(rank=lambda *args:ranking),SimpleNamespace(get=lambda identity:doc),Reader(backend),settings)
                outputs=[]
                for repetition in range(2):
                    signature=action_signature(task,settings,[doc.doc_id],'answer','none')
                    job={'run_id':'task8-development-harness','task':task,'policy':FixedPolicy(2),
                        'protocol_hash':'development-unfrozen','job_id':job_id(signature,'direct:AA',repetition),
                        'arm':'AA','mode':'direct','cache_mode':'none','repetition_id':repetition}
                    jobs.append(job)
                    prediction=execute_job(job,runtime,root)
                    result['native_calls']+=prediction.generation_calls
                    outputs.append(prediction)
                    print(json.dumps({'stage':'native-aa','repetition':repetition,'status':prediction.status}),flush=True)
                checks=result['checks']
                checks['native_aa']=outputs[0].raw_output==outputs[1].raw_output
                checks['native_correct']=all(p.status=='ok' and (p.answer or '').strip().lower()=='blue' and p.citations==[(doc.doc_id,0)] for p in outputs)
                # The benchmark packet validates runtime wiring, never claims headroom.
                setup_start=time.perf_counter_ns()
                prepared=Path(config['preparation']['output_dir'])
                tasks=load_tasks(prepared/'tasks.jsonl','pilot')
                documents=DocumentStore(prepared/'documents.jsonl')
                encoder=EncoderBackend(Path(manifest['assets']['encoder']['local_path']))
                retrieval=Retrieval(Path(config['retrieval']['output_dir'])/'pilot',documents,encoder)
                setup_stop=time.perf_counter_ns()
                pilot=tasks[0]
                settings={**settings,'index_manifest_hash':content_hash(retrieval.manifest)}
                runtime.retrieval,runtime.documents,runtime.config=retrieval,documents,settings
                signature=action_signature(pilot,settings,pilot.candidate_ids,'answer','none')
                job={'run_id':'task8-development-harness','task':pilot,'policy':FixedPolicy(2),
                    'protocol_hash':'development-unfrozen','job_id':job_id(signature,'direct:pilot',0),
                    'arm':'pilot','mode':'direct','cache_mode':'none','repetition_id':0}
                jobs.append(job)
                record_shared_cost(root,'cold_setup',setup_start,setup_stop,[job['job_id']])
                prediction=execute_job(job,runtime,root)
                result['native_calls']+=prediction.generation_calls
                checks['native_pilot_pipeline']=prediction.generation_calls==1 and prediction.status!='infra_error'
                result['pilot_status']=prediction.status
                result['native_generation_event_count']=sum(e.role.startswith('generation:') for e in load_events(root))
                checks['every_native_paid_call_has_event']=result['native_generation_event_count']==result['native_calls']==3
                result['closure']=close_run(root,jobs)
                checks['native_complete_assigned_set']=result['closure']['record_count']==3
                result['native_costs']=[accounting(root,_complete(root/'jobs'/job['job_id'])) for job in jobs]
                result['peak_mlx_bytes']=getattr(backend,'peak_mlx_bytes',None)
                result['worker_lifecycle']=[{**row,'elapsed_seconds':(row['stop_ns']-row['start_ns'])/1e9} for row in backend.lifecycle]
                result['network_attempt_count']=len(network_attempts)
                checks['no_python_network_attempts']=not network_attempts
    except Exception as error:
        result['errors'].append(f'{type(error).__name__}:{error}')
    finally:
        monitor_stop.set();observer.join()
        result['sampled_peak_parent_and_worker_rss_bytes']=rss_peak[0]
        result['resource_gate']=resource_gate(environment['physical_memory_bytes'],
            rss_peak[0]+result['peak_mlx_bytes'] if result.get('peak_mlx_bytes') is not None else None)
        result['passed']=all(result['checks'].values()) and not result['errors'] and result['resource_gate']['passed']
        result['interpretation']='inconclusive'
        result['scope']='development harness plumbing only; no benchmark headroom or efficiency claim'
        atomic_json(root/'gate.json',result)
        atomic_json(Path('artifacts/provenance/task8-harness.json'),result)
    print(json.dumps(result),flush=True)
    return 0 if result['passed'] else 1


def _bound_action_signature(task,runtime,evidence_ids,cache_mode='none'):
    config={**runtime.config,'installed_chat_template_hash':content_hash(runtime.reader.backend.tokenizer.chat_template),
            'prompt_system_hash':content_hash(ANSWER_SYSTEM)}
    return action_signature(task,config,evidence_ids,'answer',cache_mode)


def _answer_payload(prediction):
    return {item.name:getattr(prediction,item.name) for item in fields(prediction)
            if item.name!='elapsed_seconds'}


def _worker_owner(job,policy_id):
    if not job.get('_run_dir'): return None
    return {'run_dir':str(job['_run_dir']),'run_id':job['run_id'],'job_id':job['job_id'],
            'task_id':job['task'].task_id,'policy_id':policy_id,'attempt':job.get('attempt',1)}


def _owner_attempt(owner):
    return Path(owner['run_dir'])/'jobs'/owner['job_id']/f"attempt-{owner['attempt']}"


def _check_pending_recovery(backend):
    owner=getattr(backend,'pending_owner',None)
    if owner and (Path(owner['run_dir'])/'predictions.closed.json').exists():
        raise ValueError('closed origin run cannot receive worker recovery costs')


def _record_pending_recovery(backend):
    owner=getattr(backend,'pending_owner',None)
    if owner:
        path=_owner_attempt(owner)/'recovery-pending.json'
        record={'owner':owner,'recovery_id':content_hash(owner)}
        if not path.exists(): atomic_json(path,record)
        elif _read(path)!=record: raise ValueError('worker recovery origin changed')


def _consume_worker_lifecycle(runtime,job,ledger,*,serving_window=None):
    backend=runtime.reader.backend
    lifecycle=getattr(backend,'lifecycle',[])
    seen=getattr(runtime,'_lifecycle_seen',0)
    for index,record in enumerate(lifecycle[seen:],start=seen):
        if record['kind']!='load':
            runtime._lifecycle_seen=index+1
            continue
        owner=record.get('owner')
        if owner:
            if (Path(owner['run_dir'])/'predictions.closed.json').exists():
                raise ValueError('closed origin run cannot receive worker recovery costs')
            inline=serving_window is not None and serving_window[0]<=record['start_ns']<=record['stop_ns']<=serving_window[1]
            same_owner=owner==_worker_owner(job,ledger.policy_id)
            # Allocation is an observation of the original boundary, not a property
            # of whichever job eventually succeeds in publishing its receipt.
            # Retain it before fallible I/O, so an unadvanced cursor cannot relabel
            # an already-enclosed load when the next job consumes the record.
            if 'cost_role' not in record:
                record['cost_role']='worker_reload_in_serving' if inline and same_owner else 'worker_reload'
            role=record['cost_role']
            identity=content_hash({'owner':owner,'load':record})
            if inline and not same_owner:
                ledger.event('worker_reload_transfer',record['start_ns'],record['stop_ns'])
            event=CostEvent(identity,owner['run_id'],owner['task_id'],owner['policy_id'],
                role,record['start_ns'],record['stop_ns'],
                (record['stop_ns']-record['start_ns'])/1e9,0,0,'none',None,None,None,None,
                owner['attempt'],record.get('status','ok'))
            row={'job_id':owner['job_id'],'recovery_id':content_hash(owner),'event':event,
                 'resolved':record.get('status','ok')=='ok'}
            path=_owner_attempt(owner)/'reloads'/f'{identity}.json'
            if path.exists():
                if canonical_bytes(_read(path))!=canonical_bytes(row): raise ValueError('worker recovery receipt changed')
            else: atomic_json(path,row)
        elif index==0:
            inline=serving_window is not None and serving_window[0]<=record['start_ns']<=record['stop_ns']<=serving_window[1]
            ledger.event('setup_in_serving' if inline else 'setup',record['start_ns'],record['stop_ns'])
        else:
            raise ValueError('worker reload lacks causal job ownership')
        runtime._lifecycle_seen=index+1
    runtime._lifecycle_seen=len(lifecycle)


def _owned_reloads(attempt_dir):
    events=[]
    for path in sorted((attempt_dir/'reloads').glob('*.json')):
        row=_read(path);event=CostEvent(**row['event']);validate_record(event)
        if event.event_id!=path.stem or row['job_id']!=attempt_dir.parent.name or event.attempt!=int(attempt_dir.name.split('-')[-1]):
            raise ValueError('worker recovery receipt identity mismatch')
        if event.elapsed_seconds!=(event.stop_ns-event.start_ns)/1e9:
            raise ValueError('worker recovery duration mismatch')
        events.append(event)
    return events


def _check_recovery_settled(attempt_dir):
    pending=attempt_dir/'recovery-pending.json'
    if pending.exists():
        identity=_read(pending)['recovery_id']
        if not any(_read(path)['recovery_id']==identity and _read(path)['resolved']
                   for path in (attempt_dir/'reloads').glob('*.json')):
            raise ValueError('unresolved attributable worker recovery')


def _supplement_hashes(run_dir):
    names=('recovery-pending.json','observed-failure.json','observed-failure.closed.json')
    paths=[p for p in Path(run_dir).glob('jobs/*/attempt-*/*') if p.is_file() and p.name in names]
    paths+=list(Path(run_dir).glob('jobs/*/attempt-*/reloads/*.json'))
    return {str(p.relative_to(run_dir)):_digest(p) for p in sorted(paths)}


def _observed_failure(attempt_dir):
    marker=_read(attempt_dir/'observed-failure.closed.json')
    path=attempt_dir/'observed-failure.json'
    if _digest(path)!=marker['receipt_sha256']: raise ValueError('observed failure checksum mismatch')
    row=_read(path)
    if any(_digest(attempt_dir/name)!=digest for name,digest in row['paid_receipt_hashes'].items()):
        raise ValueError('observed paid receipt checksum mismatch')
    prediction=_prediction(row['prediction'])
    events=[CostEvent(**event) for event in row['events']]
    _validate_events(prediction,events)
    return prediction,events


def _certify_observed_serving_failure(job,runtime,attempt_dir,error):
    """Alive parent observes an exact failure stop; never label it as process death."""
    start=runtime.service_start_ns
    if start is None: start=_read(attempt_dir/'started.json')['start_ns']
    ledger=TimingLedger(job,_policy_id(job['policy']),runtime.clock)
    ledger.events=list(runtime.events)
    _consume_worker_lifecycle(runtime,job,ledger,serving_window=(start,runtime.clock()))
    _record_pending_recovery(runtime.reader.backend)
    prediction=runtime.last_prediction
    if prediction is None:
        prediction=Prediction(job['run_id'],job['task'].task_id,ledger.policy_id,job['protocol_hash'],
            job['job_id'],job['attempt'],job.get('repetition_id',0),[], '',None,[],'infra_error',
            runtime.config['model_revision'],content_hash('no-prompt'),runtime.config['decoding_hash'],
            0.,0,0,0,[])
    prediction=replace(prediction,status='infra_error',answer=None,citations=[])
    runtime.decision_payload={**(runtime.decision_payload or {}),'stop_reason':f'{type(error).__name__}:{error}'}
    with ledger.component('failure_payload'):
        runtime.payload=canonical_bytes({'prediction':_answer_payload(prediction),'decision':runtime.decision_payload})
    stop=runtime.clock()
    if not any(event.role=='serving' for event in ledger.events):
        ledger.event('serving',start,stop,status='infra_error')
    runtime.events=ledger.events
    return replace(prediction,elapsed_seconds=(stop-start)/1e9)


def optimistic_post_cost(events: list[CostEvent], reusable_prefill_seconds: float) -> dict:
    """Remove measured full-call prompt-only work; all draft/decode/other costs remain.

    Taking all full-call clean chunk prefill as reusable is deliberately optimistic:
    it includes noncommon full-prompt chunks. Backend prompt_tps is never used.
    """
    import math
    for event in events: validate_record(event)
    boundaries = [e for e in events if e.role == 'serving']
    if len(boundaries) != 1 or not any(e.role == 'generation:draft' for e in events):
        raise ValueError('one POST serving attempt required')
    full = [e for e in events if e.role == 'generation:answer']
    available = sum(e.clean_prefill_seconds for e in full)
    if (not math.isfinite(reusable_prefill_seconds) or reusable_prefill_seconds < 0
            or reusable_prefill_seconds > available or available > sum(e.elapsed_seconds for e in full)):
        raise ValueError('bound exceeds measured full clean prefill')
    total = boundaries[0].elapsed_seconds
    return {'observed_serving_seconds':total, 'optimistic_serving_seconds':total-reusable_prefill_seconds,
            'removed_full_prefill_seconds':reusable_prefill_seconds,
            'kind':'optimistic_all_measured_full_clean_prefill',
            'limitation':'last prompt token and sampling excluded; common-prefix partition unresolved'}


def _paid_receipt_hashes(run_dir):
    paths=sorted(Path(run_dir).glob('jobs/*/attempt-*/paid-*'))
    if any(not p.is_file() or not re.fullmatch(r'paid-[1-9][0-9]*\.(started|partial|finished)\.json',p.name) for p in paths):
        raise ValueError('unexpected paid receipt file')
    return {str(p.relative_to(run_dir)):_digest(p) for p in paths}


def _paid_receipt_coverage(run_dir, marker, predictions):
    version=marker.get('closure_version',1)
    if type(version) is not int or version not in (1,2): raise ValueError('unsupported ledger closure version')
    if version==2:
        if marker.get('paid_receipt_hashes')!=_paid_receipt_hashes(run_dir):
            raise ValueError('closed paid receipt checksum/set mismatch')
        _validate_forward_paid_receipts(run_dir,predictions)
        return 'forward_v2'
    seal_path=Path(run_dir)/'paid-receipts.sealed.json'
    if not seal_path.exists(): return 'legacy_unsealed'
    seal=_read(seal_path)
    if any(not p.protocol_hash.startswith('development') for p in predictions):
        raise ValueError('nondevelopment runs require forward paid receipt closure')
    if (seal.get('qualification')!='retrospective_not_historical_completion_attestation' or
            seal.get('original_prediction_closure_sha256')!=_digest(Path(run_dir)/'predictions.closed.json') or
            seal.get('paid_receipt_hashes')!=_paid_receipt_hashes(run_dir)):
        raise ValueError('legacy paid receipt seal checksum/set mismatch')
    return 'legacy_retrospective'


def _validate_forward_paid_receipts(run_dir, predictions):
    try:
        _check_paid_payloads(run_dir,predictions,None,strict=True,development_crosschecks=False)
    except (KeyError,TypeError,OSError) as error:
        raise ValueError('missing/malformed paid receipt') from error


def _check_paid_payloads(run_dir, predictions, documents, *, strict=False, development_crosschecks=True):
    """Check paid contents against core records; strict mode requires every call."""
    root=Path(run_dir);finished_by_job={}
    count=0
    for final in predictions:
        for attempt in sorted((root/'jobs'/final.job_id).glob('attempt-*')):
            if (attempt/'observed-failure.closed.json').exists(): record,events=_observed_failure(attempt)
            else:
                record=_prediction(_read(attempt/'prediction.json'))
                events=[CostEvent(**r) for r in read_jsonl(attempt/'events.jsonl')]
            generation=[e for e in events if e.role.startswith('generation:')]
            if strict:
                _validate_events(record,events)
                # A development replay copies source events, not new paid calls.
                if generation and all(e.cache_mode=='development_replay' for e in generation):
                    if list(attempt.glob('paid-*')): raise ValueError('replay has unexpected paid receipts')
                    continue
                expected={f'paid-{i}.{kind}.json' for i in range(1,len(generation)+1)
                          for kind in ('started','finished')}
                for number in range(1,len(generation)+1):
                    value=_read(attempt/f'paid-{number}.finished.json')
                    if value.get('started_receipt_sha256')!=_digest(attempt/f'paid-{number}.started.json'):
                        raise ValueError('paid started receipt checksum mismatch')
                    if 'partial_receipt_sha256' not in value:
                        raise ValueError('paid finished receipt lacks explicit partial coverage')
                    partial=attempt/f'paid-{number}.partial.json'
                    if value['partial_receipt_sha256']!=(_digest(partial) if partial.exists() else None):
                        raise ValueError('paid partial receipt checksum/absence mismatch')
                    if value['partial_receipt_sha256'] is not None: expected.add(partial.name)
                if {p.name for p in attempt.glob('paid-*')}!=expected:
                    raise ValueError('missing/extra paid call receipt')
            byid={e.event_id:e for e in events}
            finished=[]
            for path in sorted(attempt.glob('paid-*.finished.json'),key=lambda p:int(p.name.split('-')[1].split('.')[0])):
                number=int(path.name.split('-')[1].split('.')[0]);row=_read(path)
                event=CostEvent(**row['event']);result=_result(row['result']);validate_record(event)
                if byid.get(event.event_id)!=event or event.event_id not in record.event_ids or event.status!=result.status:
                    raise ValueError('paid finished event differs from bound core event')
                if strict and event!=generation[number-1]:
                    raise ValueError('paid call ordinal differs from bound generation event')
                started=_read(attempt/f'paid-{number}.started.json')
                request=GenerationRequest(**started['request']);validate_record(request)
                if (started['role']!=event.role or started['start_ns']!=event.start_ns or
                    request.model_revision!=record.model_revision or request.decoding_hash!=record.decoding_hash or
                    result.prompt_tokens!=event.prompt_tokens or result.generated_tokens!=event.output_tokens or
                    result.telemetry.get('clean_prefill_seconds',0.)!=event.clean_prefill_seconds):
                    raise ValueError('paid request/result differs from bound core event')
                partial=attempt/f'paid-{number}.partial.json'
                if partial.exists():
                    value=_read(partial)
                    if (value['text'],value['prompt_ids'],value['token_ids'])!=(result.raw_output,result.prompt_token_ids,result.generated_token_ids):
                        raise ValueError('paid partial differs from finished result')
                finished.append((event,result,request));count+=1
            if (strict or record.status!='infra_error') and len(finished)!=record.generation_calls:
                raise ValueError('missing paid terminal receipt')
            if finished and record.status!='infra_error':
                event,result,request=finished[-1]
                if (result.raw_output,result.prompt_tokens,result.generated_tokens,request.prompt_hash)!=(
                        record.raw_output,record.prompt_tokens,record.generated_tokens,record.prompt_hash):
                    raise ValueError('paid final result differs from bound prediction')
                if documents is not None and event.role!='generation:judge':
                    decision=_read(attempt/'decision.json')
                    parsed=Reader.parse_generated(result,[documents.get(i) for i in record.evidence_ids],decision['aliases'])
                    if (parsed.answer,parsed.citations,parsed.status)!=(record.answer,record.citations,record.status):
                        raise ValueError('paid parsed result differs from bound prediction')
            if record.attempt==final.attempt: finished_by_job[final.job_id]=finished
    schedule_path=root/'schedule.json';checks=[]
    if development_crosschecks and schedule_path.exists():
        schedule=_read(schedule_path)
        sources={(j['task_id'],j['arm']):j['job_id'] for j in schedule.get('jobs',[]) if 'arm' in j}
        byjob={p.job_id:p for p in predictions}
        for (task_id,arm),identity in sources.items():
            if arm=='post-full':
                small_id=sources.get((task_id,'k=2'))
                if small_id is None or not finished_by_job.get(identity) or not finished_by_job.get(small_id):
                    raise ValueError('POST draft requires a bound fixed-two observation')
                _,draft,request=finished_by_job[identity][0]
                _,small,small_request=finished_by_job[small_id][0]
                signature=lambda r:(r.raw_output,r.prompt_token_ids,r.generated_token_ids,r.status,r.stop_reason)
                if signature(draft)!=signature(small) or request!=small_request:
                    raise ValueError('POST paid draft raw/token/status differs from fixed-two observation')
                checks.append({'task_id':task_id,'kind':'post_draft_fixed_two_raw_token_status','passed':True})
            if arm=='judge':
                if not finished_by_job.get(identity): raise ValueError('missing paid judge observation')
                _,judge,_=finished_by_job[identity][0]
                sufficient=(judge.status not in {'timeout','infra_error','budget_exhausted','context_overflow'} and
                            judge.stop_reason=='stop' and judge.raw_output.strip()=='SUFFICIENT')
                prediction=byjob[identity]
                decision=_read(root/'jobs'/identity/f'attempt-{prediction.attempt}'/'decision.json')['decision']
                if decision['action_k']!=(2 if sufficient else 10):
                    raise ValueError('paid judge disagrees with bound final decision')
                checks.append({'task_id':task_id,'kind':'paid_judge_final_decision','passed':True})
    return {'finished_receipts_checked':count,'development_crosschecks':checks,
            'parsed_final_fields_checked':documents is not None}


def seal_legacy_paid_receipts(run_dir, predictions, *, documents=None, source_binding_hash=None):
    """Seal current legacy ancillary bytes before Gold; never rewrite old closure."""
    from datetime import datetime,timezone
    root=Path(run_dir);path=root/'paid-receipts.sealed.json'
    if path.exists(): raise ValueError('legacy paid receipt seal already exists')
    marker=_read(root/'predictions.closed.json')
    if marker.get('closure_version',1)!=1: raise ValueError('forward closure already binds paid receipts')
    if any(not p.protocol_hash.startswith('development') for p in predictions):
        raise ValueError('legacy sealing is restricted to historical development runs')
    context=validate_closed_accounting(root,predictions)
    hashes=_paid_receipt_hashes(root)
    checks=_check_paid_payloads(root,predictions,documents)
    context.verify_unchanged()
    result={'qualification':'retrospective_not_historical_completion_attestation',
            'sealed_utc':datetime.now(timezone.utc).isoformat(),
            'original_prediction_closure_sha256':_digest(root/'predictions.closed.json'),
            'paid_receipt_hashes':hashes,'source_binding_hash':source_binding_hash,**checks,
            'limitation':'Original v1 closure did not hash successful ancillary paid receipts. This seals extant bytes after core/content checks; it does not prove their historical completion-time bytes.'}
    atomic_json(path,result)
    return result

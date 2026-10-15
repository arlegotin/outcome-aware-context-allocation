"""A separate fixed-32 pooled diagnostic; frozen primary execution is untouched.

Serving functions import neither scorer nor gold readers. Annotation access is
confined to score_transfer, after independent complete closure validation.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import time

from .data_runtime import DocumentStore, load_tasks
from .protocol import _read, file_hash, materialize_policy
from .protected import immutable_json
from .schemas import Task, Prediction, ReaderResult, GenerationRequest, validate_record
from .storage import append_jsonl, atomic_json, canonical_bytes, content_hash, read_jsonl
from .robustness import pooled_corpus_manifest, pooled_top_ten

COUNT = 32
RULE = 'SHA256 canonical [271828,task_id,"task15-pooled-transfer"] ascending, task_id tie; first32 of original assigned sample'


def _digest(manifest):
    return content_hash({k:v for k,v in manifest.items() if k!='manifest_hash'})


def prospective_manifest(primary, development, protected, source, root, *, fixture=False):
    """Pure prospective fixed selection: no primary/transfer score input."""
    root=Path(root).resolve()
    if root.is_relative_to(Path(primary['run_dir']).resolve()):
        raise ValueError('diagnostic root must be outside primary run')
    population=[t.task_id for t in protected]
    if len(population)!=primary['sample']['N'] or len(set(population))!=len(population):
        raise ValueError('complete declared protected population required')
    if not fixture and len(population)!=7344: raise ValueError('declared population must be7344')
    tasks={t['task_id']:t for t in primary['sample']['tasks']}
    parent=primary['sample']['task_ids']
    if set(tasks)!=set(parent) or len(tasks)!=len(parent) or len(parent)<COUNT or not set(parent)<=set(population):
        raise ValueError('original complete assigned sample required')
    ids=sorted(parent,key=lambda tid:(content_hash([271828,tid,'task15-pooled-transfer']),tid))[:COUNT]
    methods=primary['methods']
    policies={'A':methods['selected']['A'],'B':methods['selected']['B'],'FIXED10':methods['anchor']}
    jobs=[]
    for tid in ids:
        for arm in sorted(policies,key=lambda a:content_hash([271828,tid,a,'task15-pooled-order'])):
            row={'task_id':tid,'arm':arm,'method':policies[arm],'mode':'direct','cache_mode':'none','repetition_id':0}
            row['job_id']=content_hash(['task15-pooled-transfer',row]);jobs.append(row)
    result={'kind':'task15-pooled-transfer','scope':'nested exploratory pooled transfer; not confirmation',
        'fixture':fixture,'root':str(root),'prepared_dir':str(Path(methods['retrieval']['prepared_dir']).resolve()),
        'primary_protocol_hash':primary['protocol_hash'],'primary_run_dir':str(Path(primary['run_dir']).resolve()),
        'frozen_methods':methods,'reader':methods['reader'],'encoder':methods['encoder'],'policies':policies,
        'models':methods['models'],'source':source,'artifact_sha256':primary.get('artifact_sha256',{}),
        'parent_task_ids':parent,'queries':[tasks[tid] for tid in ids],'jobs':jobs,
        'corpus':pooled_corpus_manifest(development,protected),'selection_rule':RULE,'selection_reads_scores':False,
        'deadline_utc':primary['deadline_utc'],'report_reserve_seconds':7200,'batch_rows':4096,
        'timing_domain':'perf_counter_ns; host suspension may be excluded; uninterrupted-awake/stationarity evidence remains unverified',
        'reuse_indexes':list(dict.fromkeys([*methods['retrieval'].get('reuse_indexes',[]),methods['retrieval']['index_dir']])),
        'new_index_cost':'all new build/load/query-pilot work charged; reused original adaptation sources identified separately'}
    result=json.loads(canonical_bytes(result))
    result['manifest_hash']=_digest(result)
    return result


def verify_manifest(m, *, verify_source=True):
    if m.get('manifest_hash')!=_digest(m) or m['kind']!='task15-pooled-transfer':
        raise ValueError('transfer manifest checksum/kind mismatch')
    ids=sorted(m['parent_task_ids'],key=lambda tid:(content_hash([271828,tid,'task15-pooled-transfer']),tid))[:COUNT]
    if len(set(m['parent_task_ids']))!=len(m['parent_task_ids']) or [t['task_id'] for t in m['queries']]!=ids or len(ids)!=COUNT:
        raise ValueError('fixed32 selection changed')
    if m['reader']!=m['frozen_methods']['reader'] or m['encoder']!=m['frozen_methods']['encoder'] or m['models']!=m['frozen_methods']['models']:
        raise ValueError('frozen reader/retriever/model settings changed')
    expected={'A':m['frozen_methods']['selected']['A'],'B':m['frozen_methods']['selected']['B'],'FIXED10':m['frozen_methods']['anchor']}
    if m['policies']!=expected or m['policies']['A']['family']!='PRE-OUTCOME-GBM' or m['policies']['B']['family']!='PROXY-LABEL' or m['policies']['FIXED10'].get('k')!=10:
        raise ValueError('frozen A/B/FIXED10 roster changed')
    if m['report_reserve_seconds']!=7200 or m['batch_rows']!=4096 or m['selection_rule']!=RULE or m['selection_reads_scores'] is not False:
        raise ValueError('diagnostic settings changed')
    expected_jobs=[]
    for tid in ids:
        for arm in sorted(expected,key=lambda a:content_hash([271828,tid,a,'task15-pooled-order'])):
            row={'task_id':tid,'arm':arm,'method':expected[arm],'mode':'direct','cache_mode':'none','repetition_id':0}
            row['job_id']=content_hash(['task15-pooled-transfer',row]);expected_jobs.append(row)
    if m['jobs']!=expected_jobs:raise ValueError('exact96-job independent schedule required')
    if not m['fixture'] and m['corpus']['protected_population_count']!=7344:raise ValueError('full7344 corpus required')
    if verify_source:
        for name,digest in m['source']['sha256'].items():
            if file_hash(name)!=digest:raise ValueError('transfer source checksum changed')
        for name,digest in m.get('input_sha256',{}).items():
            if file_hash(name)!=digest:raise ValueError('transfer input checksum changed')
        if not m['fixture']:
            for name,digest in m['artifact_sha256'].items():
                if file_hash(name)!=digest:raise ValueError('frozen asset/dependency checksum changed')
    return m


def _inventory(root,paths):
    return {str(p.relative_to(root)):file_hash(p) for p in sorted(set(paths)) if p.is_file()}


def _check_files(root, hashes):
    for name,digest in hashes.items():
        path=root/name
        if not path.resolve().is_relative_to(root.resolve()) or file_hash(path)!=digest:
            raise ValueError('transfer receipt checksum/path mismatch')


def build_pooled_index(m, documents, encoder):
    """Preserve every attempt; only a separately sealed successful index is usable."""
    from .retrieval import build_index, _completed_manifest
    root=Path(m['root'])
    if (root/'index-realization.json').exists():
        seal=_read(root/'index-realization.json');_check_files(root,seal['files'])
        for name,digest in seal['reuse_source_hashes'].items():
            if file_hash(name)!=digest:raise ValueError('reused source changed')
        if seal['manifest_hash']!=m['manifest_hash']:raise ValueError('index realization identity changed')
        return Path(seal['index_dir']),_completed_manifest(Path(seal['index_dir']))
    number=len(list((root/'index').glob('attempt-*')))+1
    index=root/'index'/f'attempt-{number}';started=time.perf_counter();status='failed'
    try:
        sources=[Path(p) for p in m['reuse_indexes'] if (Path(p)/'manifest.json').exists()]
        build_index((documents.get(d) for d in m['corpus']['document_ids']),encoder,index,reuse_indexes=sources)
        manifest=_completed_manifest(index)
        import sqlite3
        with sqlite3.connect(f'file:{index/"metadata.sqlite3"}?mode=ro',uri=True) as db:
            actual=sorted(row[0] for row in db.execute('SELECT doc_id FROM documents'))
        if actual!=m['corpus']['document_ids']:raise ValueError('pooled index document union mismatch')
        sources_by_id={};source_hashes={}
        def original_sources(parent):
            for source in parent.get('reuse_sources',[]):
                path=Path(source['path']);old=_completed_manifest(path)
                if content_hash(old)!=source['manifest_hash']:raise ValueError('reused source changed')
                ledger=Path(old['completion']['attempt_ledger'])
                rows=[r for r in read_jsonl(ledger) if r['attempt_id']==source['attempt_id']]
                if len(rows)!=1:raise ValueError('original physical indexing cost missing')
                identity='index-attempt:'+source['attempt_id']
                if identity in sources_by_id:continue
                sources_by_id[identity]={'source_id':identity,'path':str(path),'elapsed_seconds':rows[0]['elapsed_seconds'],
                    'scope':'existing adaptation, not charged again as new pooled indexing'}
                source_hashes[str(path/'manifest.json')]=file_hash(path/'manifest.json')
                source_hashes[str(ledger)]=file_hash(ledger);original_sources(old)
        original_sources(manifest)
        seal={'manifest_hash':m['manifest_hash'],'index_dir':str(index),'index_manifest':manifest,
            'files':_inventory(root,[index/'manifest.json',*(index/name for name in manifest['files']),Path(manifest['completion']['attempt_ledger'])]),
            'reuse_source_hashes':source_hashes,'reused_physical_sources':list(sources_by_id.values())}
        immutable_json(root/'index-realization.json',seal);status='ok'
        return index,manifest
    finally:
        append_jsonl(root/'index-attempts.jsonl',{'attempt':number,'index_dir':str(index),'status':status,
            'elapsed_seconds':time.perf_counter()-started,'partial_bytes':sum(p.stat().st_size for p in index.rglob('*') if p.is_file())})


class PooledRetrieval:
    def __init__(self,index_dir,documents,encoder,*,batch_rows=4096):
        import sqlite3
        from .retrieval import Retrieval
        base=Retrieval(Path(index_dir),documents,encoder)
        self.vectors,self.encoder,self.manifest=base.vectors,encoder,base.manifest
        with sqlite3.connect(f'file:{Path(index_dir)/"metadata.sqlite3"}?mode=ro',uri=True) as db:
            self.paragraphs=[dict(zip(('doc_id','title','character_count','sentence_count','vector_start','window_count'),row))
                for row in db.execute('SELECT doc_id,title,character_count,sentence_count,vector_start,window_count FROM documents ORDER BY doc_id')]
        self.batch_rows=batch_rows;self.last_timings={};self.last_query={}

    def rank(self,question,candidate_ids):
        from .retrieval import QUERY_PREFIX, QUERY_LIMIT, validate_vectors
        started=time.perf_counter();text=QUERY_PREFIX+question;tokenizer=self.encoder.tokenizer
        original=tokenizer(text,add_special_tokens=True,truncation=False)['input_ids']
        retained=tokenizer(text,add_special_tokens=True,truncation=True,max_length=QUERY_LIMIT)['input_ids']
        self.last_query={'original_tokens':len(original),'retained_tokens':len(retained),
            'truncated':len(original)>len(retained),'retained_ids_hash':content_hash(retained),'truncation_side':'right',
            'packet_restrictions_used':False}
        query=validate_vectors(self.encoder.encode([text]),1)[0];encoded=time.perf_counter()-started
        result=pooled_top_ten(self.vectors,self.paragraphs,query,batch_rows=self.batch_rows)
        self.last_timings={k:v for k,v in result.items() if k!='ranking'}
        self.last_timings['query_encoding_seconds']=encoded
        self.last_timings['full_retrieval_seconds']=time.perf_counter()-started
        return result['ranking']


def _job(m,job,retrieval,documents,backend,models):
    from .timing import TimingLedger
    from .generation import render_prompt,prompt_identity,ranking_aliases,Reader
    root=Path(m['root']);directory=root/'jobs'/job['job_id']/'attempt-1'
    if directory.exists():raise ValueError('diagnostic attempt already exists; no selective retry')
    directory.mkdir(parents=True);task=next(Task(**t) for t in m['queries'] if t['task_id']==job['task_id'])
    policy=materialize_policy(job['method'],models)
    timing_job={'run_id':'task15-pooled-transfer','job_id':job['job_id'],'task':task,'attempt':1,'cache_mode':'none'}
    ledger=TimingLedger(timing_job,policy.policy_id);backend.job_owner={**timing_job,'task':asdict(task)}
    start=time.perf_counter_ns();lifecycle_start=len(getattr(backend,'lifecycle',[]));calls=0
    atomic_json(directory/'started.json',{'manifest_hash':m['manifest_hash'],'job':job,'start_ns':start})
    generated=ReaderResult('',None,[],'infra_error',0,0,[],[],'unexecuted');evidence=[];request=None;decision=None
    prompt_hash=content_hash('no-prompt')
    try:
        with ledger.component('synchronization:before'):backend.synchronize()
        with ledger.component('retrieval'):
            ranked=retrieval.rank(task.question,task.candidate_ids)
            if len(ranked)!=10:raise ValueError('pooled diagnostic requires unrestricted top ten')
            aliases=ranking_aliases(ranked)
        with ledger.component('routing'):
            decision=policy.choose(task.question,ranked,caller_cap=10);validate_record(decision)
            if decision.action_k not in (2,10):raise ValueError('frozen diagnostic actions must be two/ten')
        with ledger.component('evidence:answer'):evidence=[documents.get(r.doc_id) for r in ranked[:decision.action_k]]
        with ledger.component('prompt:answer'):
            prompt=render_prompt(task.question,evidence,aliases,backend.tokenizer)
            prompt_hash=prompt_identity(prompt,backend.tokenizer)
            request=GenerationRequest(m['reader']['model_revision'],m['reader']['model_hash'],prompt_hash,m['reader']['decoding_hash'],
                'answer',m['reader']['max_context_tokens'],m['reader']['max_new_tokens'],m['reader']['timeout_seconds'],'none')
        generation_start=time.perf_counter_ns();atomic_json(directory/'paid-1.started.json',{'request':request,'start_ns':generation_start})
        partial={'text':'','prompt_ids':[],'token_ids':[]};previous=getattr(backend,'progress_callback',None)
        def progress(text,prompt_ids,token_ids):
            partial.update(text=text,prompt_ids=list(prompt_ids),token_ids=list(token_ids));atomic_json(directory/'paid-1.partial.json',partial)
            if previous:previous(text,prompt_ids,token_ids)
        backend.progress_callback=progress;calls=1
        try:generated=backend.generate(prompt,request,rendered=True);validate_record(generated)
        except Exception as error:
            generated=ReaderResult(partial['text'],None,[],'infra_error',len(partial['prompt_ids']),len(partial['token_ids']),
                partial['prompt_ids'],partial['token_ids'],str(error))
        finally:backend.progress_callback=previous
        paid=ledger.event('generation:answer',generation_start,time.perf_counter_ns(),result=generated,status=generated.status,
            resources=getattr(backend,'last_resources',{}))
        partial_path=directory/'paid-1.partial.json'
        atomic_json(directory/'paid-1.finished.json',{'event':paid,'result':generated,
            'started_receipt_sha256':file_hash(directory/'paid-1.started.json'),
            'partial_receipt_sha256':file_hash(partial_path) if partial_path.exists() else None})
        with ledger.component('parse:answer'):generated=Reader.parse_generated(generated,evidence,aliases)
        # A timeout's worker reload is paid/settled inside its own job, including the last job.
        with ledger.component('synchronization:after'):backend.synchronize()
    except Exception as error:
        generated=replace(generated,status='infra_error',answer=None,citations=[],stop_reason=str(error))
    prediction=Prediction('task15-pooled-transfer',task.task_id,policy.policy_id,m['manifest_hash'],job['job_id'],1,0,
        [d.doc_id for d in evidence],generated.raw_output,generated.answer,generated.citations,generated.status,
        m['reader']['model_revision'],prompt_hash,m['reader']['decoding_hash'],0.,generated.prompt_tokens,
        generated.generated_tokens,calls,[e.event_id for e in ledger.events if e.role.startswith('generation:')])
    with ledger.component('payload'):canonical_bytes(prediction)
    stop=time.perf_counter_ns();ledger.event('serving',start,stop,status=prediction.status)
    prediction=replace(prediction,elapsed_seconds=(stop-start)/1e9)
    atomic_json(directory/'prediction.json',prediction)
    for event in ledger.events:append_jsonl(directory/'events.jsonl',event)
    atomic_json(directory/'decision.json',{'decision':decision,'top_ten':ranked if 'ranked' in locals() else [],
        'query':getattr(retrieval,'last_query',{}),'retrieval_timings':getattr(retrieval,'last_timings',{}),
        'lifecycle':getattr(backend,'lifecycle',[])[lifecycle_start:]})
    immutable_json(directory.parent/'completion.json',{'job_id':job['job_id'],'prediction_hash':content_hash(prediction),
        'hashes':_inventory(root,directory.rglob('*')),'observed_attempt_seconds':(time.perf_counter_ns()-start)/1e9})
    return prediction


def run_diagnostic(m,retrieval,documents,backend,models,*,resource_check=None):
    verify_manifest(m);root=Path(m['root'])
    if (root/'transfer.closed.json').exists() or (root/'run.started.json').exists():
        raise ValueError('diagnostic run already attempted; no automatic retry or resizing')
    immutable_json(root/'run.started.json',{'manifest_hash':m['manifest_hash'],'assigned_jobs':len(m['jobs']),
        'utc':datetime.now(timezone.utc).isoformat()})
    predictions=[];started=time.perf_counter();status='incomplete'
    try:
        for job in m['jobs']:
            cutoff=datetime.fromisoformat(m['deadline_utc'])-timedelta(seconds=m['report_reserve_seconds'])
            if datetime.now(timezone.utc)>=cutoff:break
            p=_job(m,job,retrieval,documents,backend,models);predictions.append(p)
            if resource_check is not None:resource_check()
            if p.status=='infra_error':break
        if len(predictions)==len(m['jobs']) and all(p.status!='infra_error' for p in predictions):
            for p in predictions:append_jsonl(root/'predictions.jsonl',p)
            files=[root/'manifest.json',root/'corpus-documents.jsonl',root/'predictions.jsonl',root/'run.started.json',*(root/'jobs').rglob('*')]
            immutable_json(root/'transfer.closed.json',{'manifest_hash':m['manifest_hash'],'assigned_job_ids':[j['job_id'] for j in m['jobs']],
                'hashes':_inventory(root,files),'scope':'independent complete fixed32 diagnostic; no primary identity reuse'})
            status='closed'
    finally:
        result={'manifest_hash':m['manifest_hash'],'status':status,'assigned_jobs':len(m['jobs']),
            'completed_jobs':len(predictions),'observed_seconds':time.perf_counter()-started}
        atomic_json(root/'run.observed.json',result)
    return result


def validate_transfer(m):
    from .runner import _prediction
    verify_manifest(m);root=Path(m['root']);marker=_read(root/'transfer.closed.json')
    if marker['manifest_hash']!=m['manifest_hash'] or marker['assigned_job_ids']!=[j['job_id'] for j in m['jobs']]:
        raise ValueError('independent assigned denominator changed')
    _check_files(root,marker['hashes'])
    actual={str(p.relative_to(root)) for p in (root/'jobs').rglob('*') if p.is_file()}
    if actual!={p for p in marker['hashes'] if p.startswith('jobs/')}:raise ValueError('diagnostic job files changed')
    predictions=[_prediction(row) for row in read_jsonl(root/'predictions.jsonl')]
    if [p.job_id for p in predictions]!=marker['assigned_job_ids']:raise ValueError('missing/duplicate diagnostic prediction')
    costs={};bindings={**marker['hashes'],'transfer.closed.json':file_hash(root/'transfer.closed.json')}
    acquisition=sum(r['elapsed_seconds'] for r in read_jsonl(root/'stage-costs.jsonl')) if (root/'stage-costs.jsonl').exists() else None
    if not m['fixture']:
        launch=_read(root/'launch-run.completed.json');_check_files(root,launch['hashes'])
        if launch['returncode']!=0 or launch['manifest_hash']!=m['manifest_hash']:raise ValueError('native diagnostic not completed')
        bindings.update(launch['hashes']);bindings['launch-run.completed.json']=file_hash(root/'launch-run.completed.json')
    warm=sum(p.elapsed_seconds for p in predictions)
    if acquisition is None:
        if not m['fixture']:raise ValueError('complete measured acquisition costs required')
        acquisition=warm
    if acquisition<warm:raise ValueError('outer acquisition cost cannot exclude warm work')
    shared=(acquisition-warm)/len(predictions)
    for job,p in zip(m['jobs'],predictions):
        expected=job['method'].get('model_name','FIXED-10')
        if (p.protocol_hash,p.run_id,p.task_id,p.policy_id,p.attempt,p.repetition_id)!=(m['manifest_hash'],'task15-pooled-transfer',job['task_id'],expected,1,0) or p.status=='infra_error':
            raise ValueError('diagnostic prediction identity/infrastructure mismatch')
        directory=root/'jobs'/p.job_id/'attempt-1';events=list(read_jsonl(directory/'events.jsonl'))
        if any(e['elapsed_seconds']!=(e['stop_ns']-e['start_ns'])/1e9 for e in events):raise ValueError('diagnostic event duration changed')
        serving=[e for e in events if e['role']=='serving']
        if len(serving)!=1 or serving[0]['elapsed_seconds']!=p.elapsed_seconds:raise ValueError('diagnostic service boundary mismatch')
        paid=_read(directory/'paid-1.finished.json');partial=directory/'paid-1.partial.json'
        if paid['started_receipt_sha256']!=file_hash(directory/'paid-1.started.json') or paid['partial_receipt_sha256']!=(file_hash(partial) if partial.exists() else None):
            raise ValueError('diagnostic paid started/partial coverage mismatch')
        generations=[e for e in events if e['role']=='generation:answer']
        if len(generations)!=1 or p.generation_calls!=1 or p.event_ids!=[generations[0]['event_id']] or content_hash(paid['event'])!=content_hash(generations[0]):
            raise ValueError('diagnostic paid generation mismatch')
        request=_read(directory/'paid-1.started.json')['request']
        expected_request={k:m['reader'][k] for k in ('model_revision','model_hash','decoding_hash','max_context_tokens','max_new_tokens','timeout_seconds')}
        expected_request.update(prompt_hash=p.prompt_hash,role='answer',cache_mode='none')
        if request!=expected_request:raise ValueError('diagnostic request differs from frozen settings')
        required={'retrieval','routing','evidence:answer','prompt:answer','generation:answer','parse:answer','payload','synchronization:before','synchronization:after','serving'}
        if not required<={e['role'] for e in events}:raise ValueError('diagnostic cost component missing')
        costs[p.job_id]={'total_serving_seconds':p.elapsed_seconds,'total_experiment_seconds':p.elapsed_seconds+shared}
    return predictions,costs,bindings


def _score_transfer(m):
    """Separate scorer: complete independent closure admission precedes gold."""
    predictions,costs,bindings=validate_transfer(m);root=Path(m['root'])
    from .schemas import GoldRecord
    from .scoring import Scorer
    from types import SimpleNamespace
    gold_path=Path(m['prepared_dir'])/'gold/gold.jsonl'
    prepared=_read(Path(m['prepared_dir'])/'manifest.json')
    if file_hash(gold_path)!=prepared['files']['gold/gold.jsonl']['sha256']:raise ValueError('prepared gold source changed')
    assigned={t['task_id'] for t in m['queries']};gold={}
    for row in read_jsonl(gold_path):
        if row['task_id'] not in assigned:continue
        row['supporting_facts']=[tuple(p) for p in row['supporting_facts']];g=GoldRecord(**row);validate_record(g)
        if g.task_id in gold:raise ValueError('duplicate assigned diagnostic gold')
        gold[g.task_id]=g
    if set(gold)!=assigned:raise ValueError('assigned diagnostic gold incomplete')
    documents=DocumentStore(root/'corpus-documents.jsonl');context=SimpleNamespace(costs=lambda p:costs[p.job_id])
    scores=[Scorer().score(p,gold[p.task_id],documents,run_dir=root,accounting_context=context) for p in predictions]
    recalls=[];coverage=[]
    for p in predictions:
        row=_read(root/'jobs'/p.job_id/'attempt-1'/'decision.json')
        titles={d['title'] for d in row['top_ten']};facts=gold[p.task_id].supporting_facts;support={t for t,_ in facts}
        recalls.append(len(titles&support)/len(support) if support else 1.)
        coverage.append(sum(title in titles for title,_ in facts)/len(facts) if facts else 1.)
    families={}
    for arm in m['policies']:
        ids={j['job_id'] for j in m['jobs'] if j['arm']==arm};rows=[s for s in scores if s.job_id in ids]
        success=sum(s.joint_em for s in rows);seconds=sum(s.total_serving_seconds for s in rows)
        families[arm]={'assigned_tasks':COUNT,'joint_successes':success,'joint_em':success/COUNT,
            'answer_em':sum(s.answer_em for s in rows)/COUNT,'serving_seconds':seconds,
            'seconds_per_success':seconds/success if success else None,'reason':None if success else 'zero_successes'}
    _check_files(root,bindings)
    output=root/'scoring';output.mkdir(exist_ok=True)
    _publish_jsonl(output/'scores.gold.jsonl',[gold[t['task_id']] for t in m['queries']]);_publish_jsonl(output/'scores.jsonl',scores)
    result={'manifest_hash':m['manifest_hash'],'assigned_unique_tasks':COUNT,'assigned_jobs':len(scores),'families':families,
        'supporting_document_recall_at10':sum(recalls)/len(recalls),'supporting_fact_title_coverage_at10':sum(coverage)/len(coverage),
        'input_hashes':bindings,'gold_source_sha256':file_hash(gold_path),'scope':m['scope'],'outcome':'inconclusive'}
    immutable_json(output/'summary.json',result)
    immutable_json(output/'scores.closed.json',{'manifest_hash':m['manifest_hash'],
        'scorer_source_sha256':file_hash(Path(__file__)),
        'hashes':_inventory(root,[output/name for name in ('scores.jsonl','scores.gold.jsonl','summary.json')])})
    return result


def score_transfer(m):
    started=time.perf_counter();status='failed'
    try:
        result=_score_transfer(m);status='ok';return result
    finally:
        append_jsonl(Path(m['root'])/'scoring-attempts.jsonl',{'elapsed_seconds':time.perf_counter()-started,
            'status':status,'assigned_jobs':96,'cost_scope':'separate scorer admission/publication; not added again to acquisition ScoredTask totals'})


def diagnostic_profile(cwd,prepared):
    from .protected import sandbox_profile
    return sandbox_profile(Path(cwd),Path(prepared))+'(deny file-read* (subpath '+json.dumps(str((Path(cwd)/'data/raw').resolve()))+'))\n'


def capture_snapshot(m):
    import shutil
    root=Path(m['root']);snapshot=root/'execution-snapshot';snapshot.mkdir(parents=True,exist_ok=True)
    hashes={}
    for name,digest in m['source']['sha256'].items():
        path=Path(name)
        if path.is_absolute():
            if not m['fixture']:raise ValueError('native snapshot source must be repository-relative')
            target=snapshot/path.name
        else:
            if '..' in path.parts:raise ValueError('invalid source path')
            target=snapshot/path
        if not target.exists():
            if file_hash(path)!=digest:raise ValueError('source changed before snapshot')
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        if file_hash(target)!=digest:raise ValueError('snapshot checksum changed')
        hashes[str(target.relative_to(snapshot))]=digest
    immutable_json(snapshot/'snapshot.json',{'manifest_hash':m['manifest_hash'],'source':m['source'],'hashes':hashes})
    return snapshot


def authorize_execution(m,*,forecast_seconds):
    import math
    verify_manifest(m);root=Path(m['root']);pilot=_read(root/'pilot.closed.json')
    if pilot['manifest_hash']!=m['manifest_hash']:raise ValueError('measured pilot identity changed')
    _check_files(root,pilot['hashes'])
    available=(datetime.fromisoformat(m['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()
    if type(forecast_seconds) not in (int,float) or not math.isfinite(forecast_seconds) or forecast_seconds<=0 or forecast_seconds+m['report_reserve_seconds']>available:
        raise ValueError('complete diagnostic forecast does not fit deadline/report reserve')
    result={'manifest_hash':m['manifest_hash'],'queries':COUNT,'assigned_jobs':len(m['jobs']),
        'pilot_closure_hash':file_hash(root/'pilot.closed.json'),'forecast_seconds':forecast_seconds,
        'report_reserve_seconds':m['report_reserve_seconds'],'available_seconds':available,
        'utc':datetime.now(timezone.utc).isoformat(),'decision':'execute entire fixed32 or do not execute; no resizing'}
    immutable_json(root/'execution-authorization.json',result)
    return result


def _publish_jsonl(path,rows):
    import os,tempfile
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,prefix='transfer-staging-',delete=False) as stream:
        temporary=Path(stream.name)
        for row in rows:stream.write(canonical_bytes(row)+b'\n')
        stream.flush();os.fsync(stream.fileno())
    if path.exists():
        if file_hash(path)!=file_hash(temporary):raise ValueError('immutable diagnostic JSONL differs')
        temporary.unlink()
    else:os.replace(temporary,path)


def seal_manifest(primary_path,root):
    """Phase2 preparation: seal selection before reading any protected scores."""
    import subprocess
    from .protocol import verify_protocol,_capture_source
    started=time.perf_counter();root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True);status='failed'
    if (root/'manifest.json').exists():raise ValueError('prospective manifest already sealed; do not resample')
    try:
        primary=verify_protocol(Path(primary_path));prepared=Path(primary['methods']['retrieval']['prepared_dir'])
        meta=_read(prepared/'manifest.json');reservations=meta['reservations']
        dev=[t for split in ('pilot','pilot_reservation','fit','tune') for t in load_tasks(prepared/'tasks.jsonl',split)]
        protected=load_tasks(prepared/'tasks.jsonl','protected')
        if {t.task_id for t in dev}!=set(reservations['pilot'])|set(reservations['fit'])|set(reservations['tune']) or {t.task_id for t in protected}!=set(reservations['protected']):
            raise ValueError('selected development/full protected identities differ from prepared declaration')
        extra=['src/outcome_poc/robustness.py','src/outcome_poc/transfer_runtime.py','tools/task15_transfer_native.py']
        source=_capture_source(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),sorted(set(primary['source']['sha256'])|set(extra)))
        m=prospective_manifest(primary,dev,protected,source,root)
        inputs=[Path(primary_path),prepared/'manifest.json',prepared/'tasks.jsonl',prepared/'documents.jsonl']
        for index in m['reuse_indexes']:
            path=Path(index)/'manifest.json'
            if not path.exists():raise ValueError('prospective reuse source unavailable: '+str(path))
            inputs.append(path)
        m['input_sha256']={str(p.resolve()):file_hash(p) for p in inputs}
        m['sealed_utc']=datetime.now(timezone.utc).isoformat();m['manifest_hash']=_digest(m)
        immutable_json(root/'manifest.json',m);status='ok'
        return m
    finally:
        append_jsonl(root/'stage-costs.jsonl',{'stage':'prospective-preparation','status':status,
            'elapsed_seconds':time.perf_counter()-started,'source_id':'preparation-'+str(time.time_ns()),
            'boundary':'command preparation through prospective publication; excludes cost-receipt persistence'})


def _probe_denials(m,phase):
    import subprocess,sys
    root=Path(m['root'])
    paths=[Path(m['prepared_dir'])/'gold/gold.jsonl',Path('models/pinned/data/hotpot_dev_distractor_v1.json'),root/'denial-probe.gold.jsonl']
    script="import errno,json,socket,sys\nr={}\nfor i,p in enumerate(sys.argv[1:]):\n try:open(p,'rb').read(1)\n except PermissionError:r[str(i)]=True\n else:r[str(i)]=False\ns=socket.socket();s.settimeout(.1)\ntry:s.connect(('1.1.1.1',443))\nexcept OSError as e:r['network']=e.errno in (errno.EPERM,errno.EACCES)\nelse:r['network']=False\nprint(json.dumps(r))"
    result=json.loads(subprocess.run([sys.executable,'-c',script,*map(str,paths)],capture_output=True,text=True,check=True).stdout)
    atomic_json(root/f'os-denials-{phase}.json',result)
    if not all(result.values()):raise ValueError('independent raw/gold/projection/network denial failed')


def launch(m,phase):
    """Own immutable native snapshot and OS-denied process; no primary guard use."""
    import os,subprocess
    if m['fixture']:raise ValueError('fixture cannot launch native diagnostic')
    if phase not in ('pilot','run'):raise ValueError('unknown native diagnostic phase')
    verify_manifest(m);root=Path(m['root'])
    if _read(root/'manifest.json')!=m:raise ValueError('prospective manifest file changed')
    if (root/'launch-run.completed.json').exists() or (phase=='run' and (root/'run.started.json').exists()):
        raise ValueError('native diagnostic already attempted/closed')
    if phase=='pilot' and (root/'pilot.closed.json').exists():raise ValueError('measured pilot already closed')
    if phase=='run':_check_authorization(m)
    started=time.perf_counter();number=len(list(root.glob(f'launch-{phase}-*.started.json')))+1
    label=f'launch-{phase}-{number}';status='failed';returncode=None
    try:
        snapshot=capture_snapshot(m)
        profile=root/'native.sb';immutable_profile=diagnostic_profile(Path.cwd(),Path(m['prepared_dir']))
        if profile.exists() and profile.read_text()!=immutable_profile:raise ValueError('diagnostic OS profile changed')
        profile.write_text(immutable_profile)
        (root/'denial-probe.gold.jsonl').write_text('synthetic OS-denial probe\n')
        immutable_json(root/f'{label}.started.json',{'manifest_hash':m['manifest_hash'],'phase':phase,
            'utc':datetime.now(timezone.utc).isoformat(),'snapshot_hash':file_hash(snapshot/'snapshot.json'),
            'profile_hash':file_hash(profile)})
        env={**os.environ,'PYTHONPATH':str(snapshot/'src'),'TASK15_TRANSFER_SNAPSHOT':str(snapshot),
            'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'}
        cmd=['/usr/bin/sandbox-exec','-f',str(profile),str(Path('.venv/bin/python3.12').absolute()),
             str(snapshot/'tools/task15_transfer_native.py'),'--stage','worker-'+phase,'--manifest',str(root/'manifest.json')]
        with (root/f'{label}.log').open('w') as log:
            process=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
        returncode=process.returncode
        if returncode:raise RuntimeError('independent native diagnostic incomplete; receipts retained')
        status='ok'
    finally:
        elapsed=time.perf_counter()-started
        atomic_json(root/f'{label}.finished.json',{'manifest_hash':m['manifest_hash'],'returncode':returncode,
            'status':status,'elapsed_seconds':elapsed,'boundary':'parent command envelope; includes nested worker/setup/index/jobs, not additive'})
        append_jsonl(root/'stage-costs.jsonl',{'stage':phase,'status':status,'elapsed_seconds':elapsed,'source_id':label})
    if phase=='run':
        paths=[root/'transfer.closed.json',root/'stage-costs.jsonl',root/'pilot.closed.json',root/'execution-authorization.json',
            root/'native.sb',snapshot/'snapshot.json',*root.glob('launch-*.json'),*root.glob('worker-*.json'),*root.glob('os-denials-*.json')]
        immutable_json(root/'launch-run.completed.json',{'manifest_hash':m['manifest_hash'],'returncode':0,'hashes':_inventory(root,paths)})
    return 0


def _check_authorization(m):
    root=Path(m['root']);decision=_read(root/'execution-authorization.json')
    if (decision['manifest_hash']!=m['manifest_hash'] or decision['assigned_jobs']!=96 or decision['queries']!=COUNT or
            decision['pilot_closure_hash']!=file_hash(root/'pilot.closed.json')):raise ValueError('whole diagnostic authorization changed')
    pilot=_read(root/'pilot.closed.json');_check_files(root,pilot['hashes'])
    available=(datetime.fromisoformat(m['deadline_utc'])-datetime.now(timezone.utc)).total_seconds()
    if decision['forecast_seconds']+m['report_reserve_seconds']>available:raise ValueError('diagnostic no longer fits deadline/report reserve')


def native_main(manifest_path,phase):
    """No scorer import, gold argument, primary serving identity or model substitution."""
    import os,threading,psutil
    from .environment import discover,resource_gate
    from .generation import NativeReaderFactory,SupervisedBackend,offline_network
    from .retrieval import EncoderBackend,_completed_manifest
    from .train import load_gate
    from .assets import verify_assets
    m=_read(Path(manifest_path));root=Path(m['root']);started=time.perf_counter()
    if m['fixture']:raise ValueError('fixture cannot initialize native assets')
    snapshot=Path(os.environ.get('TASK15_TRANSFER_SNAPSHOT','/nonexistent')).resolve()
    if not Path(__file__).resolve().is_relative_to(snapshot):raise ValueError('diagnostic worker requires immutable snapshot imports')
    for name,digest in m['source']['sha256'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts or file_hash(snapshot/name)!=digest:
            raise ValueError('native diagnostic snapshot source changed')
    verify_manifest(m)
    entries=list(root.glob(f'launch-{phase}-*.started.json'))
    latest=max(entries,key=lambda p:int(p.name.split('-')[-1].split('.')[0]));launch_plan=_read(latest)
    if launch_plan['manifest_hash']!=m['manifest_hash'] or launch_plan['profile_hash']!=file_hash(root/'native.sb') or launch_plan['snapshot_hash']!=file_hash(snapshot/'snapshot.json'):
        raise ValueError('native diagnostic launch identity changed')
    label=latest.name.removesuffix('.started.json')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(m['deadline_utc'])-timedelta(seconds=m['report_reserve_seconds']):
        raise ValueError('native diagnostic would consume report reserve')
    if phase=='run':_check_authorization(m)
    _probe_denials(m,label)
    return _native_work(m,phase,label)


def _native_work(m,phase,label):
    """Orchestration below mandatory native_main source/OS admission."""
    import os,threading,psutil
    from .environment import discover,resource_gate
    from .generation import NativeReaderFactory,SupervisedBackend,offline_network
    from .retrieval import EncoderBackend,_completed_manifest
    from .train import load_gate
    from .assets import verify_assets
    root=Path(m['root']);started=time.perf_counter()
    environment=discover(root/f'environment-{label}')
    if not environment['native_supported'] or not environment['resource_gate']['passed']:raise ValueError('native diagnostic prerequisites failed')
    process=psutil.Process();peak=[process.memory_info().rss];backend_ref=[None];stop=threading.Event()
    resource_path=root/f'worker-{label}-resources.jsonl'
    def measure():
        rss=process.memory_info().rss+sum(p.memory_info().rss for p in process.children(recursive=True) if p.is_running())
        peak[0]=max(peak[0],rss)
        backend=backend_ref[0];mlx=getattr(backend,'peak_mlx_bytes',None) if backend is not None else None
        return {'utc':datetime.now(timezone.utc).isoformat(),'process_tree_rss_bytes':rss,'peak_process_tree_rss_bytes':peak[0],
            'peak_mlx_bytes':mlx,'swap_used_bytes':psutil.swap_memory().used,
            'resource_gate':resource_gate(environment['physical_memory_bytes'],peak[0]+(mlx or 0)),
            'bound_kind':'recursive RSS plus overlapping MLX conservative bound; CPU-only during pilot'}
    def observe():
        while not stop.wait(.5):
            try:append_jsonl(resource_path,measure())
            except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    observer=threading.Thread(target=observe,daemon=True);observer.start();summary=None
    def guard():
        state=measure()
        if not state['resource_gate']['passed']:raise ValueError('native diagnostic memory reserve failed')
        return state
    try:
        manifests=[Path(p) for p in m['artifact_sha256'] if p.endswith('asset-manifest.json')]
        if len(manifests)!=1:raise ValueError('one original bound asset manifest required')
        assets=_read(manifests[0])['assets']
        if file_hash(manifests[0])!=m['artifact_sha256'][str(manifests[0])]:raise ValueError('bound asset manifest changed')
        verify_assets({'required':['encoder','reader'],'assets':{role:assets[role] for role in ('encoder','reader')}})
        with offline_network() as network_attempts:
            if phase=='pilot':
                source=DocumentStore(Path(m['prepared_dir'])/'documents.jsonl')
                _publish_jsonl(root/'corpus-documents.jsonl',(source.get(d) for d in m['corpus']['document_ids']))
            documents=DocumentStore(root/'corpus-documents.jsonl')
            if set(documents.offsets)!=set(m['corpus']['document_ids']):raise ValueError('corpus projection identity changed')
            encoder=EncoderBackend(Path(assets['encoder']['local_path']));guard()
            if encoder.identity!={'revision':assets['encoder']['revision'],'snapshot_hash':assets['encoder']['snapshot_hash']}:
                raise ValueError('frozen encoder asset identity changed')
            if phase=='pilot':index,index_manifest=build_pooled_index(m,documents,encoder)
            else:
                seal=_read(root/'index-realization.json');_check_files(root,seal['files'])
                for path,digest in seal['reuse_source_hashes'].items():
                    if file_hash(path)!=digest:raise ValueError('reused original source changed')
                index=Path(seal['index_dir']);index_manifest=_completed_manifest(index)
            retrieval=PooledRetrieval(index,documents,encoder,batch_rows=m['batch_rows']);guard()
            if phase=='pilot':
                probe_path=root/f'pilot-queries-{label}.jsonl'
                for task in m['queries']:
                    retrieval.rank(task['question'],task['candidate_ids']);guard()
                    append_jsonl(probe_path,{'task_id':task['task_id'],'query':retrieval.last_query,'timings':retrieval.last_timings})
                state=guard()
                if network_attempts:raise ValueError('diagnostic offline network attempt')
                summary={'manifest_hash':m['manifest_hash'],'phase':phase,'status':'complete','queries':COUNT,
                    'document_count':index_manifest['document_count'],'window_count':index_manifest['window_count'],
                    'new_index_seconds':index_manifest['offline']['seconds'],'resource_state':state,
                    'elapsed_seconds':time.perf_counter()-started,'generation_calls':0}
            else:
                names={m['policies'][a]['model_name'] for a in ('A','B')}
                models={name:load_gate(m['models'][name]) for name in names}
                asset=assets['reader']
                with SupervisedBackend(NativeReaderFactory(Path(asset['local_path']),{**m['reader'],'asset':asset})) as backend:
                    backend_ref[0]=backend;backend.synchronize();guard()
                    result=run_diagnostic(m,retrieval,documents,backend,models,resource_check=guard)
                    state=guard()
                    if result['status']!='closed' or state['peak_mlx_bytes'] is None or network_attempts:
                        raise ValueError('diagnostic completeness/native-resource/network validity failed')
                summary={'manifest_hash':m['manifest_hash'],'phase':phase,'status':'complete','result':result,
                    'resource_state':state,'elapsed_seconds':time.perf_counter()-started}
    except BaseException as error:
        atomic_json(root/f'worker-{label}.failure.json',{'manifest_hash':m['manifest_hash'],
            'elapsed_seconds':time.perf_counter()-started,'error':str(error),'status':'incomplete','assigned_jobs':96})
        raise
    finally:
        stop.set();observer.join(timeout=5)
    immutable_json(root/f'worker-{label}.json',summary)
    if phase=='pilot':
        index_seal=_read(root/'index-realization.json')
        paths=[root/'manifest.json',root/'corpus-documents.jsonl',root/'index-realization.json',root/'index-attempts.jsonl',
            root/f'pilot-queries-{label}.jsonl',root/f'worker-{label}.json',root/f'os-denials-{label}.json',resource_path]
        hashes={**index_seal['files'],**_inventory(root,paths)}
        immutable_json(root/'pilot.closed.json',{'manifest_hash':m['manifest_hash'],'hashes':hashes,
            'document_count':summary['document_count'],'window_count':summary['window_count'],'query_count':COUNT,'generation_calls':0})
    return summary


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description='Independent fixed32 pooled diagnostic; Phase2 release required for real data')
    parser.add_argument('--stage',required=True,choices=['seal','pilot','authorize','run','score','worker-pilot','worker-run'])
    parser.add_argument('--primary-protocol');parser.add_argument('--root');parser.add_argument('--manifest')
    parser.add_argument('--forecast-seconds',type=float)
    args=parser.parse_args(argv)
    if args.stage=='seal':
        if not args.primary_protocol or not args.root:parser.error('seal requires primary protocol and independent root')
        result=seal_manifest(Path(args.primary_protocol),Path(args.root))
        print(json.dumps({'status':'prospective-selection-sealed','manifest_hash':result['manifest_hash'],'queries':COUNT}))
        return 0
    if not args.manifest:parser.error('stage requires prospective --manifest')
    m=_read(Path(args.manifest))
    if args.stage.startswith('worker-'):native_main(Path(args.manifest),args.stage.removeprefix('worker-'))
    elif args.stage=='authorize':authorize_execution(m,forecast_seconds=args.forecast_seconds)
    elif args.stage=='score':score_transfer(m)
    else:return launch(m,args.stage)
    return 0

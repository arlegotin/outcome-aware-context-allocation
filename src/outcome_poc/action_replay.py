"""A03-only explanatory fixed-action replay. No fitting, reader calls or Gold parsing.

Native execution requires a separately recorded root release after collection has
stopped. The original registry supplies settings only; its run is never consumed.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import time

from .features import build_features, feature_schema
from .protocol import FAMILIES, _read, file_hash, materialize_policy, verify_protocol
from .robustness import _close, _compatible, _events, _policy_id, _unique
from .schemas import ScoredTask, Task, validate_record
from .storage import content_hash, read_jsonl

REPLAY_FAMILIES = frozenset(('PRE-LINEAR', 'PRE-RF', 'QUERY-ONLY',
                            'SHUFFLED-LABEL-GBM', 'PRE-OUTCOME-GBM', 'PROXY-LABEL'))
SCORE_FILES = frozenset(('scores.jsonl', 'scores.gold.jsonl', 'job-evidence.json',
                         'predictions.closed.json', 'protected-run.closed.json'))


def _sources():
    # Include the separately introduced helper and launcher, plus unchanged helpers
    # that are outside the execution seal (notably robustness).
    root = Path(__file__).resolve().parents[2]
    paths = [Path(__file__), Path(__file__).with_name('robustness.py'),
             root/'tools'/'task18_action_replay.py']
    return {str(p.resolve()):file_hash(p) for p in paths}


def _registry(p):
    replication = p.get('replication', {})
    if replication.get('amendment_id') != 'A03' or p['methods']['representatives'] != []:
        raise ValueError('distinct empty-representatives A03 protocol required')
    ref = replication['parent']; path = Path(ref['protocol_path'])
    parent = verify_protocol(path)
    expected = {'protocol_hash':parent['protocol_hash'], 'protocol_file_sha256':file_hash(path),
                'sample_file_sha256':file_hash(path.with_name('sample.json')),
                'scientific_digests':parent['digests'], 'source':parent['source'],
                'output_dir':parent['output_dir'], 'run_dir':parent['run_dir']}
    if any(ref.get(k) != v for k,v in expected.items()):
        raise ValueError('A03 parent registry provenance mismatch')
    if path.resolve() != Path(parent['output_dir']).resolve()/'protocol.json':
        raise ValueError('parent protocol root mismatch')
    run_roots = [Path(item['run_dir']).resolve() for item in (p,parent)]
    if (run_roots[0].is_relative_to(run_roots[1]) or run_roots[1].is_relative_to(run_roots[0]) or
        Path(p['output_dir']).resolve() == Path(parent['output_dir']).resolve() or
        any(Path(item['output_dir']).resolve().is_relative_to(root) for item in (p,parent) for root in run_roots)):
        raise ValueError('protocol and run roots must be distinct')
    if p['sample'] != parent['sample'] or file_hash(Path(p['output_dir'])/'sample.json') != ref['sample_file_sha256']:
        raise ValueError('exact same-sample parent required')
    for name in ('protocol.json','methods.json','sample.json','schedule.json'):
        bound = str(path.with_name(name))
        if p['artifact_sha256'].get(bound) != file_hash(bound):
            raise ValueError('original configuration registry must be artifact-bound')
    expected_methods = deepcopy(parent['methods'])
    expected_methods['representatives'] = []
    expected_methods['deadline_utc'] = p['methods']['deadline_utc']
    expected_methods['retrieval']['operational_realization_path'] = str(Path(p['run_dir'])/'index-realization.json')
    if p['methods'] != expected_methods or p['methods']['repetitions'] != 2:
        raise ValueError('A03 settings differ from frozen parent registry')
    reps = parent['methods']['representatives']
    if len(reps) != len(FAMILIES) or {r['family'] for r in reps} != FAMILIES:
        raise ValueError('original configuration registry incomplete')
    if any(value not in reps for value in p['methods']['selected'].values()):
        raise ValueError('selected configuration differs from original representative')
    if any(p['source']['sha256'].get(k) != v for k,v in parent['source']['sha256'].items()):
        raise ValueError('original frozen execution source differs')
    if p['fixture'] != parent['fixture']:
        raise ValueError('parent/A03 fixture identity differs')
    if not p['fixture']: _amendment_metadata(p,parent)
    if not p['fixture'] and (p['sample']['n'],p['sample']['N'],p['sample']['seed']) != (480,7344,271828):
        raise ValueError('A03 population/assignment mismatch')
    if (p['methods']['oracle_source']['family'],p['methods']['oracle_source']['k'],
        p['methods']['anchor']['family'],p['methods']['anchor']['k']) != ('FIXED',2,'FIXED',10):
        raise ValueError('fixed-two/fixed-ten sources required')
    if len(p['schedule']['jobs']) != 7*p['sample']['n']:
        raise ValueError('complete seven-job assignment required')
    return parent


def admit(protocol_path):
    """Admit complete A03 only, without reading original predictions or Gold records."""
    from .protected import validate_run, job_evidence
    from .runner import load_events
    started = time.perf_counter()
    p = verify_protocol(Path(protocol_path)); parent = _registry(p)
    root = Path(p['run_dir'])
    base = {'protocol':p, 'parent':parent, 'assigned_tasks':p['sample']['n'],
            'assigned_jobs':len(p['schedule']['jobs']), 'scores':None}
    required = ('protected-run.closed.json','predictions.closed.json',
                'scores.jsonl.closed.json','analysis.json')
    missing = [name for name in required if not (root/name).is_file()]
    if missing:
        return {**base,'status':'unavailable','reason':'complete separately scored closure required',
                'missing':missing,'admission_seconds':time.perf_counter()-started}
    predictions, context = validate_run(p,root)
    marker = _read(root/'scores.jsonl.closed.json')
    if (marker.get('kind') != 'protected_complete_schedule_scorer' or
        marker.get('protocol_hash') != p['protocol_hash'] or
        marker.get('paid_receipt_coverage') != 'forward_v2' or set(marker['hashes']) != SCORE_FILES):
        raise ValueError('complete native score closure required')
    if marker.get('scorer_source_sha256') != file_hash(Path(__file__).with_name('scoring.py')):
        raise ValueError('closed scorer source identity mismatch')
    for name,digest in marker['hashes'].items():
        # Gold is opaque bytes for closure validation, never decoded or scored.
        if file_hash(root/name) != digest:
            raise ValueError('score closure checksum mismatch: '+name)
    scores = [ScoredTask(**r) for r in read_jsonl(root/'scores.jsonl')]
    jobs = p['schedule']['jobs']; ids = [j['job_id'] for j in jobs]
    if (len(set(ids)) != len(ids) or [s.job_id for s in scores] != ids or
        marker['record_count'] != len(ids) or marker['assigned_unique_tasks'] != p['sample']['n']):
        raise ValueError('full ordered assigned score denominator required')
    for score,pred,j in zip(scores,predictions,jobs):
        validate_record(score)
        if (score.run_id,score.task_id,score.policy_id,score.repetition_id) != (
                'confirmation',j['task_id'],_policy_id(j['method']),j['repetition_id']):
            raise ValueError('score assignment identity mismatch')
        for key,value in context.costs(pred).items(): _close(getattr(score,key),value)
        if pred.status != 'ok' and (score.joint_em or score.joint_f1):
            raise ValueError('failed semantic action cannot become success')
    evidence = _read(root/'job-evidence.json')
    if evidence != job_evidence(p,root,predictions,scores):
        raise ValueError('closed job evidence differs from actual receipts/scores')
    analysis = _read(root/'analysis.json')
    if (analysis['protocol_hash'] != p['protocol_hash'] or analysis['assigned_unique_tasks'] != p['sample']['n']
            or analysis['population'] != p['sample']['N']):
        raise ValueError('primary analysis identity/denominator mismatch')
    receipts = {}
    for pred in predictions:
        row = next(r for r in evidence['jobs'] if r['job_id'] == pred.job_id)
        all_paid = []; paid = []
        for attempt in row['attempts']:
            directory = root/'jobs'/pred.job_id/f'attempt-{attempt["attempt"]}'
            for path in sorted(directory.glob('paid-*.finished.json'),key=lambda x:int(x.name.split('-')[1].split('.')[0])):
                value = _read(path)
                value['request'] = _read(path.with_name(path.name.replace('.finished.','.started.')))['request']
                all_paid.append({'attempt':attempt['attempt'],**value})
                if attempt['attempt'] == pred.attempt: paid.append(value)
        directory = root/'jobs'/pred.job_id/f'attempt-{pred.attempt}'
        receipts[pred.job_id] = {'decision':_read(directory/'decision.json'),'paid':paid,'all_paid':all_paid}
    names = {*SCORE_FILES,*required,'job-evidence.json','scores.jsonl'}
    hashes = {str(root/name):file_hash(root/name) for name in names}
    for item in (p,parent):
        hashes.update(item['source']['sha256']);hashes.update(item['artifact_sha256'])
        hashes.update({str(Path(item['output_dir'])/(n+'.json')):file_hash(Path(item['output_dir'])/(n+'.json'))
                       for n in ('protocol','methods','sample','schedule')})
    # Bind every attempt, paid call and shared-cost allocation consumed by context.
    hashes.update({str(root/name):digest for name,digest in context.bindings if digest != 'directory'})
    context.verify_unchanged()
    return {**base,'status':'available','scores':scores,'predictions':predictions,
            'events':load_events(root),'evidence':evidence,'receipts':receipts,
            'context':context,'input_hashes':hashes,'source_hashes':_sources(),
            'primary_analysis_sha256':hashes[str(root/'analysis.json')],
            'admission_seconds':time.perf_counter()-started}


def _same_action(source,target,pred,receipts):
    left,right = receipts[source],receipts[target]
    return (_compatible(pred[source],pred[target],left['paid'],right['paid']) and
            left['decision']['aliases'] == right['decision']['aliases'] and
            left['decision']['action_signature'] == right['decision']['action_signature'])


def _accounting(a, jobs, pred, scores, info, receipts, selected_checks):
    indexed = _events(a['events']); result = []
    checks = {r['job_id']:r for r in selected_checks}
    for job in jobs:
        if job['scope'] != 'primary': continue
        jid = job['job_id']; check = checks[jid]; source = check['source_job_id']
        unavailable = []; own = replaced = None
        def components(identity):
            current = [indexed[i] for i in info[identity]['event_ids'] if indexed[i].attempt == pred[identity].attempt]
            chosen = [e for e in current if e.role in ('routing','payload')]
            enclosing = [e for e in current if e.role == 'serving']
            if Counter(e.role for e in chosen) != Counter(('routing','payload')) or len(enclosing) != 1:
                raise ValueError('final routing/payload/serving components unavailable')
            if any(e.start_ns < enclosing[0].start_ns or e.stop_ns > enclosing[0].stop_ns for e in chosen):
                raise ValueError('routing/payload outside serving enclosure')
            ordered = sorted(chosen,key=lambda e:e.start_ns)
            if ordered[0].stop_ns > ordered[1].start_ns:
                raise ValueError('routing/payload overlap')
            return {e.role:e.elapsed_seconds for e in chosen}
        if check['status'] == 'compatible':
            try: own,replaced = components(jid),components(source)
            except ValueError as error: unavailable.append(str(error))
        else: unavailable.append(check['reason'])
        surrogate = (scores[source].total_serving_seconds-sum(replaced.values())+sum(own.values())
                     if own is not None and replaced is not None else None)
        result.append({'job_id':jid,'task_id':job['task_id'],'arm':job['arm'],
            'repetition_id':job['repetition_id'],'source_job_id':source,
            'direct_serving_seconds':scores[jid].total_serving_seconds,
            'direct_experiment_seconds':scores[jid].total_experiment_seconds,
            'own_final_routing_payload_seconds':own,'source_final_routing_payload_seconds':replaced,
            'source_cost_surrogate_seconds':surrogate,
            'cost_scope':'fixed source all-attempt serving cost minus its final routing/payload plus selected direct final routing/payload; not hypothetical full runtime',
            'shared_allocations':info[jid]['shared_allocations'],
            'source_shared_allocations':info[source]['shared_allocations'] if source else None,
            'paid_attempts':receipts[jid]['all_paid'],
            'source_paid_attempts':receipts[source]['all_paid'] if source else None,
            'attempts':info[jid]['attempts'],'source_attempts':info[source]['attempts'] if source else None,
            'events':[asdict(indexed[i]) for i in info[jid]['event_ids']],
            'source_events':[asdict(indexed[i]) for i in info[source]['event_ids']] if source else None,
            'unavailable_components':unavailable,
            'full_representative_runtime_seconds':None})
    return result


def reconstruct(a, retrieval, models):
    """Reconstruct observables with frozen helpers; retain every assigned task.

    Production callers use analyze() to load bound local gates/index. Injection is
    limited to deterministic synthetic tests; this function never loads a reader.
    """
    from .generation import ranking_aliases
    started = time.perf_counter()
    if a['status'] != 'available': raise ValueError('complete A03 admission required')
    p,parent = a['protocol'],a['parent']; jobs = p['schedule']['jobs']
    pred = _unique(a['predictions'],lambda r:r.job_id,'prediction')
    scores = _unique(a['scores'],lambda r:r.job_id,'score')
    info = _unique(a['evidence']['jobs'],lambda r:r['job_id'],'job evidence')
    receipts = a['receipts']
    descriptors = [r for r in parent['methods']['representatives'] if r['family'] in REPLAY_FAMILIES]
    for spec in p['methods']['selected'].values():
        if spec not in descriptors and spec['family'] not in ('POST-OUTCOME','LLM-SUFFICIENCY'):descriptors.append(spec)
    policies = {r['config_id']:{'config':deepcopy(r),'family':r['family'],'rows':[],
                'full_direct_runtime_seconds':None} for r in descriptors}
    traces = []; selected_checks = []
    for task_row in p['sample']['tasks']:
        task = Task(**task_row); assigned = [j for j in jobs if j['task_id'] == task.task_id]
        source_ids = {2:next(j['job_id'] for j in assigned if j['scope']=='oracle-source'),
                      10:next(j['job_id'] for j in assigned if j['scope']=='anchor')}
        trace = {'task_id':task.task_id,'task_hash':content_hash(task),'rankings':None,
                 'features':None,'feature_schema_hash':feature_schema()['hash'],'decisions':{}}
        tick = time.perf_counter(); error = None
        try:
            ranked = retrieval.rank(task.question,task.candidate_ids)
            features = build_features(task.question,ranked)
            if set(r.doc_id for r in ranked) != set(task.candidate_ids):
                raise ValueError('reconstructed candidate projection mismatch')
            trace.update(rankings=[asdict(r) for r in ranked],features=features.tolist(),
                         query=deepcopy(getattr(retrieval,'last_query',{})))
        except Exception as exc: error = f'{type(exc).__name__}: {exc}'
        trace['retrieval_feature_seconds'] = time.perf_counter()-tick
        trace['error'] = error
        for spec in descriptors:
            key = spec['config_id']; row = {'task_id':task.task_id,'config_id':key,
                'status':'unavailable','reason':error,'decision':None,'source':None,
                'observed_same_action_checks':[]}
            selected = [j for j in assigned if j['scope']=='primary' and j['method']==spec]
            source = None
            if error is None:
                tick = time.perf_counter()
                try:
                    decision = materialize_policy(spec,models).choose(task.question,ranked,caller_cap=10)
                    row['decision'] = asdict(decision); source = source_ids.get(decision.effective_budget)
                    if source is None: raise ValueError('chosen effective action has no A03 fixed source')
                    source_pred = pred[source]; source_receipt = receipts[source]
                    row['source'] = {'job_id':source,'protocol_hash':p['protocol_hash'],'run_dir':p['run_dir'],
                        'score':asdict(scores[source]),'prediction':asdict(source_pred),
                        'score_hash':content_hash(scores[source]),'prediction_hash':content_hash(source_pred),
                        'receipt':deepcopy(source_receipt),'evidence':deepcopy(info[source])}
                    reasons = []
                    frozen_reader = p['methods']['reader']
                    request_fields = ('model_revision','model_hash','decoding_hash',
                                      'max_context_tokens','max_new_tokens','timeout_seconds')
                    if any(any(paid['request'].get(field) != frozen_reader.get(field) for field in request_fields)
                           or paid['request'].get('cache_mode') != 'none' or paid['request'].get('role') != 'answer'
                           for paid in source_receipt['paid']):
                        reasons.append('source request differs from frozen reader settings')
                    if source_pred.evidence_ids != [r.doc_id for r in ranked[:decision.effective_budget]]:
                        reasons.append('fixed source evidence differs from reconstruction')
                    if source_receipt['decision']['aliases'] != ranking_aliases(ranked):
                        reasons.append('fixed source alias order differs from reconstruction')
                    if (source_receipt['decision'].get('decision') or {}).get('effective_budget') != decision.effective_budget:
                        reasons.append('fixed source effective action differs')
                    # Compare all actually observed same-action jobs, including random and
                    # both selected repetitions. Missing representatives remain unobserved.
                    for other in assigned:
                        oid = other['job_id']
                        observed = (receipts[oid]['decision'].get('decision') or {}).get('effective_budget')
                        if observed != decision.effective_budget: continue
                        compatible = _same_action(source,oid,pred,receipts)
                        row['observed_same_action_checks'].append({'job_id':oid,'compatible':compatible})
                        if not compatible: reasons.append('same-action request/result/token mismatch: '+oid)
                    for j in selected:
                        direct = receipts[j['job_id']]['decision'].get('decision')
                        if direct != asdict(decision): reasons.append('selected direct decision mismatch: '+j['job_id'])
                    if not source_receipt['paid']: reasons.append('source has no paid fixed-action outcome')
                    row['status'] = 'incompatible' if reasons else 'compatible'
                    row['reason'] = '; '.join(reasons) if reasons else None
                except Exception as exc:
                    row['reason'] = f'{type(exc).__name__}: {exc}'
                row['analysis_gate_seconds'] = time.perf_counter()-tick
            trace['decisions'][key] = {'decision':row['decision'],'status':row['status'],'reason':row['reason'],
                                       'analysis_gate_seconds':row.get('analysis_gate_seconds')}
            policies[key]['rows'].append(row)
            for j in selected:
                selected_checks.append({'job_id':j['job_id'],'task_id':task.task_id,'arm':j['arm'],
                    'source_job_id':source,'status':row['status'],'reason':row['reason']})
        # POST/LLM selected comparators have no reconstruction without paid inputs.
        for j in assigned:
            if j['scope']=='primary' and not any(r['job_id']==j['job_id'] for r in selected_checks):
                selected_checks.append({'job_id':j['job_id'],'task_id':task.task_id,'arm':j['arm'],
                    'source_job_id':None,'status':'unavailable','reason':'selected policy requires unavailable paid reconstruction inputs'})
        trace['trace_hash'] = content_hash(trace); traces.append(trace)
    for policy in policies.values():
        rows = policy['rows']; complete = all(row['status']=='compatible' for row in rows)
        policy['action_counts'] = dict(Counter(str(row['decision']['effective_budget']) if row['decision'] else 'unavailable' for row in rows))
        policy['quality'] = ({'n':p['sample']['n'],
            'joint_successes':sum(row['source']['score']['joint_em'] for row in rows),
            'joint_quality':sum(row['source']['score']['joint_em'] for row in rows)/len(rows),
            'answer_quality':sum(row['source']['score']['answer_em'] for row in rows)/len(rows)} if complete else None)
        policy['unavailable_tasks'] = sum(row['status']!='compatible' for row in rows)
    result = {'protocol_hash':p['protocol_hash'],'run_dir':p['run_dir'],
        'parent_registry':{'protocol_hash':parent['protocol_hash'],'methods_hash':parent['digests']['methods'],
                           'source':parent['source'],'role':'settings only; no original run outcomes consumed'},
        'assigned_tasks':p['sample']['n'],'assigned_jobs':len(jobs),'policies':list(policies.values()),
        'traces':traces,'selected_checks':selected_checks,
        'accounting':_accounting(a,jobs,pred,scores,info,receipts,selected_checks),
        'conditional_on_compatible_fixed_action_outputs':True,
        'missing_representative_direct_parity':'unobserved','determinism_guaranteed':False,
        'original_full_roster_analysis':'unexecuted','selection_performed':False,
        'primary_analysis_sha256':a['primary_analysis_sha256'],
        'scope':'explanatory conditional action-quality replay; no independent sample or confirmation',
        'post_llm_reconstruction':'unavailable without paid observations',
        'primary_superiority_claim':False,'analysis_seconds':time.perf_counter()-started}
    a['context'].verify_unchanged()
    return result


def seal(a, result, output):
    """Publish separate immutable report and digest without modifying either run."""
    from .protected import immutable_json
    output = Path(output).resolve()
    _check_output(a['protocol'],a['parent'],output)
    a['context'].verify_unchanged()
    for name,digest in {**a['input_hashes'],**a['source_hashes']}.items():
        if file_hash(name) != digest: raise ValueError('analysis input/source changed: '+name)
    immutable_json(output,result)
    immutable_json(output.with_suffix('.closed.json'),{
        'kind':'A03_explanatory_action_replay','protocol_hash':a['protocol']['protocol_hash'],
        'report_sha256':file_hash(output),'input_hashes':a['input_hashes'],
        'source_hashes':a['source_hashes'],'primary_analysis_sha256':a['primary_analysis_sha256'],
        'assignment_hash':a['protocol']['digests']['schedule'],
        'original_registry_hash':a['parent']['digests']['methods']})


def _load_observables(a):
    """Read-only existing projection/index and local gates; never builds an index."""
    from .data_runtime import DocumentStore
    from .retrieval import EncoderBackend, Retrieval
    from .train import load_gate
    p = a['protocol']; root = Path(p['run_dir']); settings = p['methods']['retrieval']
    seal_path = Path(settings['operational_realization_path'])
    index_seal = _read(seal_path)
    if (index_seal['protocol_hash'] != p['protocol_hash'] or index_seal['scientific_digests'] != p['digests'] or
        index_seal['algorithm'] != settings or index_seal['document_ids_hash'] != p['sample']['document_ids_hash']):
        raise ValueError('frozen index realization identity mismatch')
    for name,digest in index_seal['files'].items():
        if file_hash(name) != digest: raise ValueError('frozen index realization checksum mismatch')
    document_path = root/'selected-documents.jsonl'; index = Path(settings['index_dir'])
    bound = {Path(name).resolve():digest for name,digest in index_seal['files'].items()}
    if document_path.resolve() not in bound or (index/'manifest.json').resolve() not in bound:
        raise ValueError('projection/index manifest not bound to realization')
    documents = DocumentStore(document_path)
    if set(documents.offsets) != {d for t in p['sample']['tasks'] for d in t['candidate_ids']}:
        raise ValueError('document projection differs from assigned sample')
    manifests = [Path(name) for name in p['artifact_sha256'] if name.endswith('asset-manifest.json')]
    if len(manifests) != 1: raise ValueError('unique frozen asset manifest required')
    asset = _read(manifests[0])['assets']['encoder']
    encoder = EncoderBackend(Path(asset['local_path']))
    if encoder.identity != {'revision':asset['revision'],'snapshot_hash':asset['snapshot_hash']}:
        raise ValueError('frozen encoder identity mismatch')
    retrieval = Retrieval(index,documents,encoder)
    if content_hash(retrieval.manifest) != index_seal['manifest_hash']:
        raise ValueError('frozen index manifest identity mismatch')
    for name,identity in retrieval.manifest['files'].items():
        if bound.get((index/name).resolve()) != identity['sha256']:
            raise ValueError('index payload not bound to realization')
    descriptors = [r for r in a['parent']['methods']['representatives'] if r['family'] in REPLAY_FAMILIES]
    for spec in p['methods']['selected'].values():
        if spec not in descriptors and spec['family'] not in ('POST-OUTCOME','LLM-SUFFICIENCY'):descriptors.append(spec)
    models = {}
    for spec in descriptors:
        if 'model_name' not in spec: continue
        name = spec['model_name']; manifest = p['methods']['models'][name]
        if manifest['artifact_sha256'] != spec['model_artifact_sha256']:
            raise ValueError('representative gate artifact identity mismatch')
        models[name] = load_gate(manifest)
    a['input_hashes'].update(index_seal['files'])
    a['input_hashes'][str(seal_path)] = file_hash(seal_path)
    identity = {'index_manifest_hash':content_hash(retrieval.manifest),'encoder':encoder.identity,
                'document_projection_sha256':file_hash(document_path),
                'models':{name:p['methods']['models'][name] for name in models},
                'physical_index_source_id':index_seal['new_physical_source_id']}
    return retrieval,models,identity


def analyze(protocol_path, output, release_path):
    """Execute only after source approval and explicit root collection release.

    A release is an operational attestation, not proof of deterministic outcomes
    or a repair of the original incomplete collection.
    """
    from .generation import offline_network
    if release_path is None: raise ValueError('explicit root analysis release required')
    p = _read(Path(protocol_path)); release = _read(Path(release_path))
    if (release.get('authorization') != 'Task18 analysis only' or not release.get('authorized_by') or
        release.get('source_review_approved') is not True or release.get('source_hashes') != _sources() or
        release.get('protocol_hash') != p['protocol_hash'] or
        release.get('parent_protocol_hash') != p.get('replication',{}).get('parent',{}).get('protocol_hash') or
        release.get('original_collection_state') not in ('closed','stopped_incomplete') or
        release.get('a03_collection_state') != 'closed'):
        raise ValueError('root release does not bind source/collection identities')
    _check_output(p,p['replication']['parent'],output)
    a = admit(protocol_path)
    if a['status'] != 'available':
        return {key:a[key] for key in ('status','reason','missing','assigned_tasks','assigned_jobs')}
    a['input_hashes'][str(Path(release_path).resolve())] = file_hash(release_path)
    with offline_network() as network_attempts:
        tick = time.perf_counter()
        retrieval,models,identity = _load_observables(a)
        setup_seconds = time.perf_counter()-tick
        result = reconstruct(a,retrieval,models)
        if network_attempts: raise ValueError('analysis attempted network access')
    result.update(analysis_setup_seconds=setup_seconds,analysis_admission_seconds=a['admission_seconds'],
                  analysis_runtime_identity=identity,root_release=release,
                  analysis_cost_scope='new offline admission/setup/reconstruction only; not representative serving runtime',
                  unmeasured_intervals=['process startup/imports','report serialization/publication','attempt receipt persistence','console'])
    seal(a,result,output)
    return {'status':'complete','output':str(output),'report_sha256':file_hash(output)}


def main(argv=None):
    import argparse
    import json
    from datetime import datetime, timezone
    from .storage import append_jsonl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--release',type=Path,required=True)
    args = parser.parse_args(argv)
    # Reject output overlap before writing even a failure receipt.
    p = _read(args.protocol)
    parent = p.get('replication',{}).get('parent',{})
    _check_output(p,parent,args.output)
    started = time.perf_counter(); status = 'failed'; error = None
    started_utc = datetime.now(timezone.utc).isoformat()
    try:
        result = analyze(args.protocol,args.output,args.release)
        status = result['status']
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        append_jsonl(args.output.with_suffix('.attempts.jsonl'),{
            'started_utc':started_utc,'protocol_hash':p['protocol_hash'],'source_hashes':_sources(),
            'status':status,'error':error,'elapsed_seconds':time.perf_counter()-started,
            'scope':'new analysis attempt only; excludes process startup, receipt persistence and console'})
    print(json.dumps(result,sort_keys=True))
    return 0 if status == 'complete' else 2


def _check_output(p, parent, output):
    paths = [Path(output).resolve(), Path(output).with_suffix('.closed.json').resolve(),
             Path(output).with_suffix('.attempts.jsonl').resolve()]
    for path in paths:
        if path.is_relative_to(Path(p['output_dir']).resolve()):
            raise ValueError('output must be outside A03 protocol root')
        for item in (p,parent):
            if path.is_relative_to(Path(item['run_dir']).resolve()):
                raise ValueError('output must be outside both runs')
            if any(path == Path(item['output_dir']).resolve()/(name+'.json')
                   for name in ('protocol','methods','sample','schedule')):
                raise ValueError('output overlaps frozen manifest')
        protected = {*p['source']['sha256'],*p['artifact_sha256']}
        if path in {Path(name).resolve() for name in protected}:
            raise ValueError('output overlaps bound source/artifact')
        if path.is_relative_to(Path(p['methods']['retrieval']['index_dir']).resolve()):
            raise ValueError('output overlaps frozen index')


def _amendment_metadata(p, parent):
    """Bind the existing native A03 amendment; no schedule or method rewriting."""
    rep = p['replication']; path = Path(rep['amendment_path'])
    if rep['amendment_sha256'] != p['source']['sha256'].get(str(path)) or file_hash(path) != rep['amendment_sha256']:
        raise ValueError('A03 amendment source checksum mismatch')
    amendment = _read(path)
    deadlines = rep['deadlines']
    if (amendment['amendment_id'] != 'A03' or amendment['parent_protocol_hash'] != parent['protocol_hash'] or
        amendment['operational_gate']['maximum_conditional_replications'] != 1 or
        any(amendment['operational_gate'].get(k) != v for k,v in deadlines.items()) or
        p['methods']['deadline_utc'] != deadlines['collection_deadline_utc'] or
        parent['methods']['deadline_utc'] != deadlines['original_project_deadline_utc']):
        raise ValueError('A03 amendment/deadline identity mismatch')
    changes = {'representatives':{'previous':parent['methods']['representatives'],'new':[]},
        'deadline_utc':{'previous':parent['methods']['deadline_utc'],'new':p['methods']['deadline_utc']},
        'retrieval.operational_realization_path':{
            'previous':parent['methods']['retrieval']['operational_realization_path'],
            'new':p['methods']['retrieval']['operational_realization_path']}}
    if rep['methods_changes'] != changes:
        raise ValueError('A03 amendment method-change provenance mismatch')

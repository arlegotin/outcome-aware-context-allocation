"""Exploratory held-out prefix diagnostic; no new reader/encoder calls or gold reads."""
from dataclasses import replace
import json
from pathlib import Path
import time

from outcome_poc.data_runtime import load_tasks
from outcome_poc.policies import ThresholdPolicy
from outcome_poc.runner import (_prediction,_read,_digest,_answer_payload,validate_closed_accounting)
from outcome_poc.schemas import PairedActionRow,RankedDocument,ScoredTask
from outcome_poc.select import reconstructed_seconds,configuration_metrics,select_configuration
from outcome_poc.storage import content_hash,atomic_json,append_jsonl,read_jsonl,canonical_bytes
from outcome_poc.timing import TimingLedger
from outcome_poc.train import fit_candidate_diagnostic,load_gate


def main():
    started=time.perf_counter()
    config=_read(Path('configs/development.json'))
    root=Path(config['tuning']['run_dir']);output=Path('artifacts/runs/task12-learning-curve')
    output.mkdir(parents=True,exist_ok=False)
    primary_path=root/'selection.json';primary_hash=_digest(primary_path);primary=_read(primary_path)
    training=Path(config['training']['output_dir']);origin=_read(training/'fit-origin.json')
    raw_rows=_read(training/'paired-rows.json')
    if content_hash(raw_rows)!=origin['rows_hash'] or [r['task_id'] for r in raw_rows]!=origin['fit_ids']:
        raise ValueError('immutable original paired rows mismatch')
    rows=[]
    for raw in raw_rows:
        raw={**raw,'ranked_documents':[RankedDocument(**r) for r in raw['ranked_documents']]}
        rows.append(PairedActionRow(**raw))
    if len(rows)!=256 or set(origin['fit_ids'])&set(primary['A*']['task_ids']):
        raise ValueError('disjoint fit256 and fixed tune128 required')
    originals={name:_digest(Path(m['artifact_root'])/m['artifact_file']) for name,m in origin['models'].items()}
    original_origin_hash=_digest(training/'fit-origin.json')
    post_origin=Path(config['tuning']['post_training_dir'])/'fit-origin.json';post_hash=_digest(post_origin)
    diagnostic=fit_candidate_diagnostic(rows[:128],output/'fit128')
    manifest=diagnostic['models']['PRE-OUTCOME-GBM'];model=load_gate(manifest)
    predictions=[_prediction(r) for r in read_jsonl(root/'predictions.jsonl')]
    context=validate_closed_accounting(root,predictions)
    if any(p.attempt!=1 for p in predictions):
        raise ValueError('diagnostic requires single-attempt saved sources; no retry costs may be omitted')
    schedule=_read(root/'schedule.json')
    byjob={p.job_id:p for p in predictions};sources={(j['task_id'],j['arm']):j['job_id'] for j in schedule['jobs']}
    scored={r['job_id']:ScoredTask(**r) for r in read_jsonl(root/'scores.jsonl')}
    if _digest(root/'scores.jsonl')!=primary['scorer_receipt']['scores_sha256']:
        raise ValueError('closed tuning scores changed')
    closure=_read(root/'tuning-acquisition.closed.json')
    if any(_digest(root/name)!=digest for name,digest in closure['hashes'].items()):
        raise ValueError('closed tuning observable sources changed')
    observables={r['task_id']:r for r in read_jsonl(root/'observables.jsonl')}
    ids=primary['A*']['task_ids']
    tasks={t.task_id:t for t in load_tasks(Path(config['inputs']['prepared_dir'])/'tasks.jsonl','tune')}
    if set(tasks)!=set(ids): raise ValueError('exact unchanged tune128 tasks required')
    all_rows=[]
    for number,threshold in enumerate(manifest['thresholds']):
        identity=f'EXPLORATORY-FIT128-GBM:{number:02d}:{threshold["threshold_mode"]}'
        policy=ThresholdPolicy(model,{**threshold,'policy_id':'PRE-OUTCOME-GBM',
                                     'feature_schema_hash':manifest['feature_schema_hash']})
        selected=[];scores=[];events=[];details=[]
        for task_id in ids:
            task=tasks[task_id];ranking=[RankedDocument(**r) for r in observables[task_id]['ranking']]
            jobid=content_hash([identity,task_id]);ledger=TimingLedger({'job_id':jobid,'run_id':output.name,'task':task},policy.policy_id)
            with ledger.component('routing'): decision=policy.choose(task.question,ranking)
            source=byjob[sources[(task_id,f'k={decision.action_k}')]];score=scored[source.job_id]
            if context.costs(source)!={'total_serving_seconds':score.total_serving_seconds,'total_experiment_seconds':score.total_experiment_seconds}:
                raise ValueError('source cost no longer matches closed score')
            source_events=[]
            for attempt in sorted((root/'jobs'/source.job_id).glob('attempt-*')):
                from outcome_poc.schemas import CostEvent
                source_events.extend(CostEvent(**r) for r in read_jsonl(attempt/'events.jsonl'))
            source_decision=_read(root/'jobs'/source.job_id/f'attempt-{source.attempt}'/'decision.json')
            payload_prediction=replace(source,policy_id=policy.policy_id,job_id=jobid,elapsed_seconds=0.)
            with ledger.component('payload'):
                canonical_bytes({'prediction':_answer_payload(payload_prediction),
                    'decision':{**source_decision,'decision':decision}})
            seconds=reconstructed_seconds('PRE-OUTCOME-GBM',threshold['threshold_mode'],score.total_serving_seconds,
                [e for e in source_events if e.attempt==source.attempt],ledger.events[0].elapsed_seconds,ledger.events[1].elapsed_seconds)
            selected.append(replace(source,policy_id=identity,job_id=jobid,elapsed_seconds=seconds))
            scores.append(replace(score,policy_id=identity,job_id=jobid,total_serving_seconds=seconds,
                total_experiment_seconds=score.total_experiment_seconds+seconds-score.total_serving_seconds))
            events.extend(source_events+ledger.events)
            for event in ledger.events: append_jsonl(output/'routing-events.jsonl',event)
            details.append({'task_id':task_id,'action_k':decision.action_k,'source_prediction_id':source.job_id,
                            'routing_seconds':ledger.events[0].elapsed_seconds,'payload_seconds':ledger.events[1].elapsed_seconds})
        all_rows.append({'config_id':identity,'family':'PRE-OUTCOME-GBM',**threshold,
            **configuration_metrics(selected,scores,events),'split':'tune','task_ids':ids,'per_task':details,
            'ten_rate':sum(r['action_k']==10 for r in details)/len(details)})
    selection=select_configuration([primary['fixed_ten_anchor'],*all_rows],primary['fixed_ten_anchor'])
    if _digest(primary_path)!=primary_hash or _digest(training/'fit-origin.json')!=original_origin_hash or _digest(post_origin)!=post_hash:
        raise ValueError('original selection/model origins changed')
    if any(_digest(Path(origin['models'][name]['artifact_root'])/origin['models'][name]['artifact_file'])!=digest for name,digest in originals.items()):
        raise ValueError('original model artifact changed')
    kept=['config_id','threshold_mode','threshold','joint_successes','answer_successes','Q','answer_em','mean_time','R','per_task']
    point128={k:selection['A*'][k] for k in kept};point256={k:primary['A*'][k] for k in kept}
    result={'scope':'exploratory held-out tune128 after primary fit256 selection; no additional inference/labels',
        'subset_rule':'first128 of original ordered fit256 acquisition; nested prefix, no outcome-based choice',
        'fit128_origin_sha256':_digest(output/'fit128/fit-origin.json'),'original_fit256_origin_sha256':original_origin_hash,
        'original_primary_selection_sha256':primary_hash,'original_models_and_selection_unchanged':True,
        'source_bindings':{'native':primary['source_binding_hash'],'primary_analysis':primary['analysis_source_binding_hash']},
        'points':[{'fit_n':128,**point128},{'fit_n':256,**point256}],
        'fit128_training_seconds':diagnostic['training_seconds'],'analysis_seconds':time.perf_counter()-started,
        'fit128_all_configurations':selection['configurations'],'additional_generation_calls':0,'additional_labels':0,
        'caution':'Two sparse held-out points with thresholds selected on the same tune128 are descriptive and not a stable learning trend, confidence interval or justification to acquire more labels. Gate CPU timing sessions differ; paid reader action costs are identical sources. Primary A*/B* remain the original fit256 selection.'}
    atomic_json(output/'heldout-curve.json',result)
    public={k:v for k,v in result.items() if k!='fit128_all_configurations'}
    public['points']=[{k:v for k,v in point.items() if k!='per_task'} for point in result['points']]
    atomic_json(Path('artifacts/provenance/task12-heldout-learning-curve.json'),public)
    print(json.dumps(public))


if __name__=='__main__':main()

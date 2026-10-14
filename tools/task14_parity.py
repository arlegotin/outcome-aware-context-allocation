"""Separate development-only scorer equivalence check; no generation or fitting."""
from pathlib import Path
import json
import subprocess
import time

from outcome_poc.data_runtime import DocumentStore
from outcome_poc.runner import _prediction, validate_closed_accounting
from outcome_poc.schemas import GoldRecord
from outcome_poc.scoring import Scorer
from outcome_poc.storage import read_jsonl, atomic_json, append_jsonl, content_hash
from outcome_poc.protocol import file_hash


def rescore_development_run(root, gold_path, documents_path, output):
    root,output=Path(root),Path(output)
    predictions=[_prediction(r) for r in read_jsonl(root/'predictions.jsonl')]
    if any(not p.protocol_hash.startswith('development') for p in predictions):
        raise ValueError('parity operation accepts saved development predictions only')
    context=validate_closed_accounting(root,predictions)
    assigned={p.task_id for p in predictions};gold={}
    for row in read_jsonl(gold_path):
        if row['task_id'] in assigned:
            row['supporting_facts']=[tuple(x) for x in row['supporting_facts']]
            if row['task_id'] in gold: raise ValueError('duplicate assigned development gold')
            gold[row['task_id']]=GoldRecord(**row)
    if set(gold)!=assigned: raise ValueError('development gold incomplete')
    documents=DocumentStore(documents_path)
    rescored=[Scorer().score(p,gold[p.task_id],documents,run_dir=root,accounting_context=context) for p in predictions]
    old=list(read_jsonl(root/'scores.jsonl'))
    if [content_hash(s) for s in rescored]!=[content_hash(s) for s in old]:
        raise ValueError('development score parity failed: '+str(root))
    context.verify_unchanged()
    output.mkdir(parents=True,exist_ok=False)
    for row in rescored: append_jsonl(output/'scores.jsonl',row)
    result={'run_dir':str(root),'count':len(rescored),'exact_score_parity':True,
        'old_scores_sha256':file_hash(root/'scores.jsonl'),'new_scores_sha256':file_hash(output/'scores.jsonl'),
        'prediction_closure_sha256':file_hash(root/'predictions.closed.json'),
        'historical_receipt_coverage':context.receipt_coverage,
        'qualification':'mathematical/accounting rescore equivalence; historical receipts and acquisition attestations are not rewritten',
        'scorer_source_sha256':file_hash(Path('src/outcome_poc/scoring.py'))}
    atomic_json(output/'parity.json',result)
    return result


def main():
    start=time.perf_counter();output=Path('artifacts/runs/task14-development-parity')
    if output.exists(): raise ValueError('preserve existing parity outputs')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    for name in ('src/outcome_poc/scoring.py','src/outcome_poc/runner.py','tools/task14_parity.py'):
        import hashlib
        if hashlib.sha256(subprocess.check_output(['git','show',f'{commit}:{name}'])).hexdigest()!=file_hash(name):
            raise ValueError('commit final scorer/parity source before execution')
    prepared=Path('data/prepared');runs=['task9-pilot32','task9-pilot64-extension','task10-fit256',
        'task11-native','task11-native-repeat','task12-tune128-retry']
    immutable=[Path('artifacts/provenance/task12-selection.json'),Path('artifacts/runs/task12-tune128-retry/selection.json')]
    for dirname in ('task10-fit256/training','task11-post-training'):
        origin=Path('artifacts/runs')/dirname/'fit-origin.json';immutable.append(origin)
        immutable.extend(Path(m['artifact_root'])/m['artifact_file'] for m in json.loads(origin.read_text())['models'].values())
    before={str(p):file_hash(p) for p in immutable}
    output.mkdir(parents=True)
    atomic_json(output/'input-binding.json',{'source_commit':commit,'immutable_inputs':before,
        'source_hashes':{name:file_hash(name) for name in ('src/outcome_poc/scoring.py','src/outcome_poc/runner.py','tools/task14_parity.py')}})
    results=[]
    for name in runs:
        root=Path('artifacts/runs')/name
        gold=root/'scores.gold.jsonl'
        if not gold.exists(): gold=prepared/'gold/gold.jsonl'
        results.append(rescore_development_run(root,gold,prepared/'documents.jsonl',output/name))
    paired=json.loads(Path('artifacts/runs/task10-fit256/training/paired-rows.json').read_text())
    new_scores={r['job_id']:r for r in read_jsonl(output/'task10-fit256/scores.jsonl')}
    for row in paired:
        small,full=new_scores[row['small_prediction_id']],new_scores[row['full_prediction_id']]
        if (row['small_joint_em'],row['full_joint_em'],row['small_answer_em'],row['full_answer_em'])!=(small['joint_em'],full['joint_em'],small['answer_em'],full['answer_em']):
            raise ValueError('fit paired target parity failed')
    from outcome_poc.select import analyze_tuning
    tune=Path('artifacts/runs/task12-tune128-retry')
    original=json.loads((tune/'selection.json').read_text())
    selected=analyze_tuning(tune,original['A*']['task_ids'])
    fields=('config_id','family','threshold_mode','threshold','Q','answer_em','mean_time','R','eligible')
    project=lambda r:{k:r[k] for k in fields if k in r}
    if any(project(selected[k])!=project(original[k]) for k in ('A*','B*','fixed_ten_anchor')):
        raise ValueError('selected A/B/anchor parity failed')
    if [project(r) for r in selected['configurations']]!=[project(r) for r in original['configurations']]:
        raise ValueError('all tuning configuration metric parity failed')
    if any(file_hash(name)!=digest for name,digest in before.items()): raise ValueError('original immutable input changed')
    result={'source_commit':commit,'runs':results,'fit_target_rows_unchanged':len(paired),
        'tuning_configuration_count':len(selected['configurations']),'selected':{k:project(selected[k]) for k in ('A*','B*')},
        'all_exact_scores_targets_selection_unchanged':True,'original_models_origins_selection_unchanged':True,
        'cache_disposition':'new source-bound equivalent score copies; original frozen score/cache records retained unchanged',
        'scorer_source_sha256':file_hash('src/outcome_poc/scoring.py'),'elapsed_seconds':time.perf_counter()-start}
    atomic_json(output/'summary.json',result)
    atomic_json(Path('artifacts/provenance/task14-development-parity.json'),result)
    print(json.dumps({'exact_parity':True,'runs':len(results),'predictions':sum(r['count'] for r in results),
        'fit_targets':len(paired),'tuning_configurations':len(selected['configurations']),'source_commit':commit}))


if __name__=='__main__': main()

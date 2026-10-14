"""Paid-call receipts must be bound before a complete-ledger scorer opens gold."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from outcome_poc import runner, scoring
from outcome_poc.storage import atomic_json, append_jsonl
from outcome_poc.schemas import GoldRecord
from serving_helpers import fixture_runtime


def closed(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    backend=runtime.reader.backend;original=backend.generate
    def generate(*args,**kwargs):
        result=original(*args,**kwargs)
        backend.progress_callback(result.raw_output,result.prompt_token_ids,result.generated_token_ids)
        return result
    backend.generate=generate
    p=runner.execute_job(job,runtime,tmp_path)
    runner.close_run(tmp_path,[job])
    return runtime,job,p


def legacy(tmp_path):
    runtime,job,p=closed(tmp_path)
    path=tmp_path/'predictions.closed.json';marker=json.loads(path.read_text())
    marker.pop('closure_version',None);marker.pop('paid_receipt_hashes',None)
    atomic_json(path,marker)
    return runtime,job,p


def test_forward_closure_covers_every_paid_receipt(tmp_path):
    _,_,p=closed(tmp_path)
    marker=json.loads((tmp_path/'predictions.closed.json').read_text())
    assert marker.get('closure_version')==2
    assert set(marker['paid_receipt_hashes'])=={
        'jobs/job/attempt-1/paid-1.started.json','jobs/job/attempt-1/paid-1.partial.json',
        'jobs/job/attempt-1/paid-1.finished.json'}
    assert runner.validate_closed_accounting(tmp_path,[p]).receipt_coverage=='forward_v2'


@pytest.mark.parametrize('name',['started','partial','finished'])
@pytest.mark.parametrize('change',['mutate','missing'])
def test_paid_receipt_changes_block_before_gold(tmp_path,monkeypatch,name,change):
    closed(tmp_path)
    path=tmp_path/f'jobs/job/attempt-1/paid-1.{name}.json'
    if change=='mutate': path.write_bytes(path.read_bytes()+b'\n')
    else: path.unlink()
    accessed=[];original=scoring.read_jsonl
    def read(path):
        if path.name=='gold.jsonl': accessed.append(path)
        return original(path)
    monkeypatch.setattr(scoring,'read_jsonl',read)
    with pytest.raises(ValueError):
        scoring.main(SimpleNamespace(predictions=str(tmp_path/'predictions.jsonl'),run_dir=str(tmp_path),
                                    gold=str(tmp_path/'gold.jsonl'),documents='unused',output='unused'))
    assert accessed==[]


def test_extra_paid_receipt_rejects_closed_coverage(tmp_path):
    _,_,p=closed(tmp_path)
    (tmp_path/'jobs/job/attempt-1/paid-99.finished.json').write_text('{}')
    with pytest.raises(ValueError): runner.validate_closed_accounting(tmp_path,[p])


def test_legacy_seal_is_retrospective_preserves_original_and_all_costs(tmp_path):
    runtime,_,p=legacy(tmp_path)
    before=(tmp_path/'predictions.closed.json').read_bytes()
    original=runner.accounting(tmp_path,p)
    seal=getattr(runner,'seal_legacy_paid_receipts',None)
    assert callable(seal), 'explicit legacy receipt sealing is missing'
    result=seal(tmp_path,[p],documents=runtime.documents,source_binding_hash='analysis-binding')
    assert result['qualification']=='retrospective_not_historical_completion_attestation'
    assert result['source_binding_hash']=='analysis-binding'
    assert (tmp_path/'predictions.closed.json').read_bytes()==before
    context=runner.validate_closed_accounting(tmp_path,[p])
    assert context.receipt_coverage=='legacy_retrospective'
    assert context.costs(p)==original=={'total_serving_seconds':11.,'total_experiment_seconds':11.}
    with pytest.raises(ValueError): seal(tmp_path,[p],documents=runtime.documents)
    path=tmp_path/'jobs/job/attempt-1/paid-1.finished.json';path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError): runner.validate_closed_accounting(tmp_path,[p])


def test_unsealed_legacy_cannot_open_gold_for_new_scoring(tmp_path,monkeypatch):
    legacy(tmp_path)
    accessed=[];original=scoring.read_jsonl
    def read(path):
        if path.name=='gold.jsonl': accessed.append(path)
        return original(path)
    monkeypatch.setattr(scoring,'read_jsonl',read)
    with pytest.raises(ValueError,match='receipt'):
        scoring.main(SimpleNamespace(predictions=str(tmp_path/'predictions.jsonl'),run_dir=str(tmp_path),
                                    gold=str(tmp_path/'gold.jsonl'),documents='unused',output='unused'))
    assert accessed==[]


def test_legacy_seal_rejects_inconsistent_paid_payload_instead_of_certifying(tmp_path):
    runtime,_,p=legacy(tmp_path)
    path=tmp_path/'jobs/job/attempt-1/paid-1.finished.json'
    value=json.loads(path.read_text());value['result']['raw_output']='changed'
    atomic_json(path,value)
    seal=getattr(runner,'seal_legacy_paid_receipts',None)
    assert callable(seal), 'explicit legacy receipt sealing is missing'
    with pytest.raises(ValueError): seal(tmp_path,[p],documents=runtime.documents)
    assert not (tmp_path/'paid-receipts.sealed.json').exists()


def paid_controls(tmp_path):
    from outcome_poc.policies import PostOutcomePolicy,SufficiencyPolicy
    blue='{"answer":"blue","citations":[{"doc_id":"D0","sentence_index":0}]}'
    runtime,job,_=fixture_runtime(tmp_path,[blue,blue,blue,'SUFFICIENT',blue])
    small=runner.execute_job(job,runtime,tmp_path)
    post_job={**job,'job_id':'post','policy':PostOutcomePolicy(None,{'threshold_mode':'always_ten','threshold':None})}
    post=runner.execute_job(post_job,runtime,tmp_path)
    judge_job={**job,'job_id':'judge','policy':SufficiencyPolicy()}
    judge=runner.execute_job(judge_job,runtime,tmp_path)
    atomic_json(tmp_path/'schedule.json',{'jobs':[{'task_id':'task','arm':arm,'job_id':identity}
        for arm,identity in [('k=2','job'),('post-full','post'),('judge','judge')]]})
    runner.close_run(tmp_path,[job,post_job,judge_job])
    marker=json.loads((tmp_path/'predictions.closed.json').read_text())
    marker.pop('closure_version');marker.pop('paid_receipt_hashes')
    atomic_json(tmp_path/'predictions.closed.json',marker)
    return runtime,[small,post,judge]


def test_legacy_paid_controls_crosscheck_bound_small_and_judge_decision(tmp_path):
    runtime,predictions=paid_controls(tmp_path)
    seal=runner.seal_legacy_paid_receipts(tmp_path,predictions,documents=runtime.documents)
    assert seal['finished_receipts_checked']==5
    assert {c['kind'] for c in seal['development_crosschecks']}=={
        'post_draft_fixed_two_raw_token_status','paid_judge_final_decision'}
    assert all(c['passed'] for c in seal['development_crosschecks'])


@pytest.mark.parametrize('corruption',['draft_raw','draft_tokens','draft_status','judge_label'])
def test_legacy_controls_content_inconsistency_blocks_seal(tmp_path,corruption):
    runtime,predictions=paid_controls(tmp_path)
    name='judge' if corruption=='judge_label' else 'post'
    path=tmp_path/f'jobs/{name}/attempt-1/paid-1.finished.json'
    value=json.loads(path.read_text())
    if corruption=='draft_raw': value['result']['raw_output']=value['result']['raw_output'].replace('blue','red')
    if corruption=='draft_tokens': value['result']['generated_token_ids'][0]=3
    if corruption=='draft_status': value['result']['status']='parse_error'
    if corruption=='judge_label': value['result']['raw_output']='INSUFFICIENT'
    atomic_json(path,value)
    with pytest.raises(ValueError): runner.seal_legacy_paid_receipts(tmp_path,predictions,documents=runtime.documents)
    assert not (tmp_path/'paid-receipts.sealed.json').exists()


def test_non_development_runs_cannot_use_retrospective_receipt_seal(tmp_path):
    runtime,job,_=fixture_runtime(tmp_path)
    job['protocol_hash']='f'*64
    p=runner.execute_job(job,runtime,tmp_path)
    runner.close_run(tmp_path,[job])
    marker=json.loads((tmp_path/'predictions.closed.json').read_text())
    marker.pop('closure_version');marker.pop('paid_receipt_hashes')
    atomic_json(tmp_path/'predictions.closed.json',marker)
    with pytest.raises(ValueError,match='development'):
        runner.seal_legacy_paid_receipts(tmp_path,[p],documents=runtime.documents)

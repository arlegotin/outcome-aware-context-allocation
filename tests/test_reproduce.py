"""Reproduction admission and fresh scorer checks; no model/generation calls."""
import importlib
from pathlib import Path
import pytest


def api():
    assert importlib.util.find_spec('outcome_poc.report'), 'report implementation missing'
    return importlib.import_module('outcome_poc.report')


def test_incomplete_reproduction_does_not_open_gold_or_predictions(tmp_path,monkeypatch):
    p={'protocol_hash':'fixture','run_dir':str(tmp_path),'sample':{'task_ids':[str(i) for i in range(480)]},
       'schedule':{'jobs':[{}]*8640}}
    original=Path.open
    def guarded(path,*args,**kwargs):
        assert 'gold' not in str(path) and path.name!='predictions.jsonl'
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guarded)
    result=api().reproduce(p,tmp_path)
    assert result['status']=='unavailable' and result['reason']=='incomplete_run'
    assert result['assigned_questions']==480 and result['assigned_jobs']==8640
    assert result['gold_opened'] is False


def test_reproduction_absent_protocol_is_explicit():
    assert api().reproduce(None,None)['reason']=='no_frozen_protocol'


def test_complete_marker_cannot_skip_actual_closed_admission(tmp_path,monkeypatch):
    from outcome_poc import protocol,protected
    (tmp_path/'protected-run.closed.json').write_text('{}')
    p={'protocol_hash':'fixture','run_dir':str(tmp_path),'output_dir':str(tmp_path),
       'sample':{'task_ids':['q']},'schedule':{'jobs':[{}]}}
    monkeypatch.setattr(protocol,'verify_protocol',lambda path:p)
    def reject(*args):raise ValueError('paid receipt incomplete')
    monkeypatch.setattr(protected,'validate_run',reject)
    with pytest.raises(ValueError,match='paid receipt'):api().reproduce(p,tmp_path)


def test_fresh_scoring_uses_real_scorer_and_retains_failures(tmp_path):
    from outcome_poc.schemas import GoldRecord,Prediction,Document
    from outcome_poc.storage import append_jsonl,content_hash
    from outcome_poc.data_runtime import DocumentStore
    from dataclasses import replace
    doc=Document(content_hash(['Title',['Evidence.']]),'Title',['Evidence.'],9)
    path=tmp_path/'docs.jsonl';append_jsonl(path,doc)
    prediction=Prediction('confirmation','q','FIXED-2','p','j',1,0,[doc.doc_id],'fixture','yes',[(doc.doc_id,0)],'ok','r','p','d',2.,2,1,1,['g'])
    failed=replace(prediction,job_id='j2',task_id='q2',status='timeout')
    class Accounting:
        checked=False
        def costs(self,p):return {'total_serving_seconds':7.,'total_experiment_seconds':9.}
        def verify_unchanged(self):self.checked=True
    context=Accounting()
    rows=api().rescore_predictions([prediction,failed],{
        'q':GoldRecord('q','yes',[('Title',0)]),'q2':GoldRecord('q2','yes',[('Title',0)])},
        DocumentStore(path),tmp_path,context)
    assert [r.joint_em for r in rows]==[1,0]
    assert all(r.total_serving_seconds==7. and r.total_experiment_seconds==9. for r in rows)
    assert context.checked


def synthetic_scored_files(tmp_path,monkeypatch):
    """Invented persisted scorer inputs; frozen admission is injected separately.

    Real protocol/ledger validation is tested by its owning suite. This fixture
    avoids executing even a synthetic reader while testing fresh scoring and
    actual statistical recomputation, hashes and unchanged output bytes.
    """
    from test_ablations import synthetic
    from dataclasses import replace
    from outcome_poc import protocol as protocol_module,protected,statistics,runner,scoring
    from outcome_poc.schemas import Document,GoldRecord
    from outcome_poc.storage import append_jsonl,atomic_json,content_hash
    from outcome_poc.data_runtime import DocumentStore
    import hashlib
    p,old,e,pred,mapping,_=synthetic(tmp_path)
    root=Path(p['run_dir']);root.mkdir()
    prepared=tmp_path/'prepared';(prepared/'gold').mkdir(parents=True)
    p['methods']['retrieval']['prepared_dir']=str(prepared)
    p['output_dir']=str(tmp_path/'frozen');p['digests']={'methods':'fixture'}
    docs=[Document(content_hash([f'Title{i}',['Evidence.']]),f'Title{i}',['Evidence.'],9) for i in range(10)]
    for d in docs:append_jsonl(root/'selected-documents.jsonl',d)
    gold={q:GoldRecord(q,'yes',[('Title0',0)]) for q in p['sample']['task_ids']}
    for q in p['sample']['task_ids']:
        append_jsonl(prepared/'gold/gold.jsonl',gold[q]);append_jsonl(root/'scores.gold.jsonl',gold[q])
    digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    atomic_json(prepared/'manifest.json',{'files':{'gold/gold.jsonl':{'sha256':digest(prepared/'gold/gold.jsonl')}}})
    p['sample']['tasks']=[{'task_id':q,'candidate_ids':[d.doc_id for d in docs]} for q in gold]
    pred=[replace(x,evidence_ids=[d.doc_id for d in docs[:len(x.evidence_ids)]],answer='yes',citations=[(docs[0].doc_id,0)],
                  status='parse_error' if x.task_id=='q1' else 'ok') for x in pred]
    oldby={s.job_id:s for s in old}
    class Accounting:
        receipt_coverage='forward_v2'
        def costs(self,prediction):
            s=oldby[prediction.job_id]
            return {'total_serving_seconds':s.total_serving_seconds,'total_experiment_seconds':s.total_experiment_seconds}
        def verify_unchanged(self):pass
    context=Accounting()
    monkeypatch.setattr(protocol_module,'verify_protocol',lambda path:p)
    monkeypatch.setattr(protected,'validate_run',lambda protocol,root:(pred,context))
    scores=[scoring.Scorer().score(x,gold[x.task_id],DocumentStore(root/'selected-documents.jsonl'),run_dir=root,accounting_context=context) for x in pred]
    for x in scores:append_jsonl(root/'scores.jsonl',x)
    for x in pred:append_jsonl(root/'predictions.jsonl',x)
    byevent={x.event_id:x for x in e};by_score={x.job_id:x for x in scores};by_pred={x.job_id:x for x in pred}
    for row in mapping['jobs']:
        row['score_hash']=content_hash(by_score[row['job_id']]);row['prediction_hash']=content_hash(by_pred[row['job_id']])
        for event_id in row['event_ids']:
            append_jsonl(root/'jobs'/row['job_id']/'attempt-1/events.jsonl',byevent[event_id])
    atomic_json(root/'job-evidence.json',mapping)
    atomic_json(root/'predictions.closed.json',{'fixture':True})
    atomic_json(root/'protected-run.closed.json',{'fixture':True})
    names=['scores.jsonl','scores.gold.jsonl','job-evidence.json','predictions.closed.json','protected-run.closed.json']
    atomic_json(root/'scores.jsonl.closed.json',{'protocol_hash':p['protocol_hash'],'paid_receipt_coverage':'forward_v2',
        'record_count':len(scores),'assigned_unique_tasks':2,'hashes':{name:digest(root/name) for name in names}})
    atomic_json(root/'analysis.json',statistics.analyze_run(p,scores,runner.load_events(root)))
    return p,root


def test_reproduce_recomputes_all_scores_and_statistics_without_cached_scorer(tmp_path,monkeypatch):
    from outcome_poc import scoring
    import hashlib
    p,root=synthetic_scored_files(tmp_path,monkeypatch)
    before={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file()}
    calls=[];old=scoring.Scorer.score
    def counted(self,prediction,*args,**kwargs):
        calls.append(prediction.job_id);return old(self,prediction,*args,**kwargs)
    def cached_forbidden(*args,**kwargs):raise AssertionError('idempotent score_run cannot reproduce')
    monkeypatch.setattr(scoring.Scorer,'score',counted)
    monkeypatch.setattr(scoring,'score_run',cached_forbidden)
    result=api().reproduce(p,root)
    assert result['status']=='reproduced' and result['assigned_questions']==2 and result['assigned_jobs']==36
    assert calls==[j['job_id'] for j in p['schedule']['jobs']]
    assert {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file()}==before


def test_changed_score_receipt_is_rejected_before_gold_record_read(tmp_path,monkeypatch):
    p,root=synthetic_scored_files(tmp_path,monkeypatch)
    (root/'scores.jsonl').write_text('{}\n')
    module=api();old=module.read_jsonl
    def guard(path):
        assert 'gold' not in str(path)
        return old(path)
    monkeypatch.setattr(module,'read_jsonl',guard)
    with pytest.raises(ValueError,match='checksum'):module.reproduce(p,root)


def test_base_analysis_mutation_is_detected_by_fresh_statistics(tmp_path,monkeypatch):
    import json
    p,root=synthetic_scored_files(tmp_path,monkeypatch)
    path=root/'analysis.json';value=json.loads(path.read_text());value['primary']['effect']=-999.
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='analysis digest'):api().reproduce(p,root)

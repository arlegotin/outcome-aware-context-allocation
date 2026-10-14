"""Freeze contracts: mutation, attempt, sampling and accounting boundaries."""
import copy
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from outcome_poc.storage import atomic_json, content_hash
from outcome_poc.schemas import Task

FAMILIES = ('ADAPTIVE-k-published','ADAPTIVE-k-tuned','FIXED','LLM-SUFFICIENCY',
            'POST-OUTCOME','PRE-LINEAR','PRE-OUTCOME-GBM','PRE-RF','PROXY-LABEL',
            'QUERY-ONLY','SHUFFLED-LABEL-GBM')


def api():
    assert importlib.util.find_spec('outcome_poc.protocol'), 'protocol implementation missing'
    return importlib.import_module('outcome_poc.protocol')


def inputs(tmp_path):
    reps={}
    for family in FAMILIES:
        row={'family':family,'config_id':family,'selection_pool':family!='SHUFFLED-LABEL-GBM'}
        if family=='FIXED': row.update(k=9)
        elif family.startswith('ADAPTIVE'): row.update(buffer=5 if family.endswith('published') else 1)
        elif family!='LLM-SUFFICIENCY':
            row.update(model_name=family,model_artifact_sha256='a'*64,threshold_mode='numeric',threshold=.1)
        reps[family]={'representative':row}
    selected={'A*':{**reps['PRE-OUTCOME-GBM']['representative'],'fit_escalation_probability':.2},
              'B*':reps['PROXY-LABEL']['representative'],'families':reps,
              'fixed_ten_anchor':{'family':'FIXED','config_id':'FIXED-10','k':10},'missing_families':[]}
    source=tmp_path/'runtime.py';source.write_text('bound runtime\n')
    artifact=tmp_path/'model.bin';artifact.write_bytes(b'model')
    tasks=[Task(str(i),'protected','Question?', [f'doc-{j}' for j in range(10)]) for i in range(10)]
    development={'reader':{'max_context_tokens':8192,'max_new_tokens':256,'timeout_seconds':20.,
                           'model_revision':'r','model_hash':'h','decoding_hash':'d'},
        'encoder':{'revision':'e'},'repetitions':2,'calibration':{'path':'cal','sha256':'c'*64},
        'diagnostics':{'no_context':{'split':'tune','count':2,'selection_rule':'hash'}},
        'forecast':{'conservative_seconds_per_question':45.,'fixed_remaining_seconds':7200.,
                    'report_reserve_seconds':7200.,'available_seconds':14700.,'bytes_per_question':1000},
        'retrieval':{'index_dir':'sample-index','algorithm':'frozen-source'},'models':{},'identities':{'feature_schema':'f','scorer':'s'}}
    capacity={'passed':True,'max_prompt_tokens':7936,'forced_output_tokens':256,'max_request_seconds':10.}
    return {'development':development,'selection':selected,'capacity':capacity,'population_ids':[t.task_id for t in tasks],
            'tasks':tasks,'n':5,'source_commit':'a'*40,'source_files':[str(source)],'artifact_files':[str(artifact)],
            'output_dir':str(tmp_path/'frozen'),'run_dir':str(tmp_path/'run'),
            'deadline_utc':'2099-01-01T00:00:00+00:00','fixture':True}


def test_methods_written_before_uniform_sorted_population_sampling(tmp_path,monkeypatch):
    p=api();config=inputs(tmp_path);original=p.sample_protected
    def observe(ids,n,seed=271828):
        assert (Path(config['output_dir'])/'methods.json').exists()
        assert not (Path(config['output_dir'])/'sample.json').exists()
        return original(ids,n,seed)
    monkeypatch.setattr(p,'sample_protected',observe)
    protocol=p.freeze(config)
    expected=np.random.Generator(np.random.PCG64(271828)).choice(sorted(config['population_ids']),5,replace=False).tolist()
    assert protocol['sample']['task_ids']==expected
    assert p.verify_protocol(Path(config['output_dir'])/'protocol.json')==protocol
    with pytest.raises(ValueError,match='already|exists|frozen'): p.freeze(config)


@pytest.mark.parametrize('ids,n',[(['a','a'],1),(['a'],0),(['a'],2),(['a'],True)])
def test_sampling_rejects_invalid_population_or_size(ids,n):
    with pytest.raises(ValueError): api().sample_protected(ids,n)


@pytest.mark.parametrize('change',[lambda c:c['development']['reader'].update(timeout_seconds=float('nan')),
    lambda c:c['selection']['families'].pop('PRE-RF'),
    lambda c:c['development'].update(repetitions=1),
    lambda c:c['capacity'].update(forced_output_tokens=255),
    lambda c:c['development']['forecast'].update(report_reserve_seconds=1),
    lambda c:c.update(n=10)])
def test_freeze_rejects_unresolved_nonfinite_incomplete_or_unfeasible_configuration(tmp_path,change):
    c=inputs(tmp_path);change(c)
    with pytest.raises(ValueError): api().freeze(c)


def test_source_binding_preserves_science_and_locks_at_first_attempt(tmp_path):
    p=api();c=inputs(tmp_path);frozen=p.freeze(c)
    Path(c['source_files'][0]).write_text('new implementation\n')
    with pytest.raises(ValueError,match='changed|checksum'): p.verify_protocol(Path(c['output_dir'])/'protocol.json')
    rebound=p.bind_source(frozen,'b'*40)
    assert {k:rebound[k] for k in ('methods','sample','schedule')}=={k:frozen[k] for k in ('methods','sample','schedule')}
    assert rebound['protocol_hash']!=frozen['protocol_hash']
    assert rebound['source']['commit']=='b'*40
    p.verify_protocol(Path(c['output_dir'])/'protocol.json')
    (tmp_path/'new-report.py').write_text('report only')
    assert p.verify_protocol(Path(c['output_dir'])/'protocol.json')==rebound
    attempt=Path(c['run_dir'])/'jobs'/'anything'/'attempt-1';attempt.mkdir(parents=True)
    atomic_json(attempt/'started.json',{'failed_before_generation':True})
    with pytest.raises(ValueError,match='attempt'): p.bind_source(rebound,'c'*40)


def test_protocol_rejects_rehashed_scientific_manifest_mutation(tmp_path):
    p=api();c=inputs(tmp_path);protocol=p.freeze(c)
    protocol['schedule']['jobs'].pop()
    protocol['protocol_hash']=content_hash({k:v for k,v in protocol.items() if k!='protocol_hash'})
    atomic_json(Path(c['output_dir'])/'protocol.json',protocol)
    with pytest.raises(ValueError,match='schedule|digest|manifest'): p.verify_protocol(Path(c['output_dir'])/'protocol.json')


def test_protected_execution_remains_blocked_before_task14(tmp_path):
    from dataclasses import replace
    from serving_helpers import fixture_runtime
    from outcome_poc.runner import serve
    runtime,job,_=fixture_runtime(tmp_path)
    task=replace(job['task'],split='protected')
    with pytest.raises(ValueError,match='protected'): serve(task,job['policy'],runtime,job)
    assert runtime.reader.backend.calls==0


def test_source_rebind_cannot_change_scientific_artifacts_or_frozen_index_inputs(tmp_path):
    p=api();c=inputs(tmp_path);f=p.freeze(c)
    assert f['sample']['document_ids_hash']==content_hash([f'doc-{j}' for j in range(10)])
    assert f['methods']['retrieval']==c['development']['retrieval']
    Path(c['artifact_files'][0]).write_bytes(b'changed model')
    with pytest.raises(ValueError,match='artifact'):p.bind_source(f,'b'*40)


def test_wrong_fixed_ten_anchor_is_rejected(tmp_path):
    p=api();c=inputs(tmp_path);c['selection']['fixed_ten_anchor']['k']=9
    with pytest.raises(ValueError,match='anchor'):p.freeze(c)


def test_fixture_protocol_schedule_resumes_interrupted_transaction_without_repeat_payment(tmp_path,monkeypatch):
    from outcome_poc import runner
    from serving_helpers import fixture_runtime
    runtime,base,_=fixture_runtime(tmp_path)
    c=inputs(tmp_path);c.update(tasks=[base['task']],population_ids=[base['task'].task_id],n=1)
    c['development']['reader']={**runtime.config,'timeout_seconds':20.}
    runtime.config=c['development']['reader']
    p=api();f=p.freeze(c);rows=f['schedule']['jobs']
    class Model:
        def __init__(self,n):self.n_features_in_=n
        def predict(self,values):return np.zeros(len(values))
    models={family:Model(46 if family=='POST-OUTCOME' else 42) for family in FAMILIES}
    jobs=[{**base,**row,'task':base['task'],'policy':p.materialize_policy(row['method'],models),
           'protocol_hash':'development-fixture-'+f['protocol_hash']} for row in rows]
    original=runner.atomic_json
    def interrupt(path,value):
        if path.name=='completion.json':raise KeyboardInterrupt('fixture killed at commit')
        return original(path,value)
    monkeypatch.setattr(runner,'atomic_json',interrupt)
    with pytest.raises(KeyboardInterrupt):runner.execute_job(jobs[0],runtime,Path(c['run_dir']))
    paid=runtime.reader.backend.calls
    monkeypatch.setattr(runner,'atomic_json',original)
    runner.execute_job(jobs[0],runtime,Path(c['run_dir']))
    assert runtime.reader.backend.calls==paid
    for job in jobs[1:]:runner.execute_job(job,runtime,Path(c['run_dir']))
    closed=runner.close_run(Path(c['run_dir']),jobs)
    assert closed['record_count']==18 and closed['closure_version']==2
    assert runtime.reader.backend.calls==19
    with pytest.raises(ValueError,match='attempt'):p.bind_source(f,'b'*40)


def test_external_dependency_manifest_cannot_rebind_changed_dependency_bytes(tmp_path):
    p=api();c=inputs(tmp_path);dependency=tmp_path/'installed-backend.so';dependency.write_bytes(b'original')
    manifest=tmp_path/'dependency-bindings.json';atomic_json(manifest,{str(dependency):p.file_hash(dependency)})
    c['artifact_manifest_path']=str(manifest)
    dependency.write_bytes(b'changed')
    with pytest.raises(ValueError,match='artifact|dependency'):p.freeze(c)


def test_later_reporting_commit_does_not_invalidate_unchanged_frozen_files(tmp_path,monkeypatch):
    p=api();c=inputs(tmp_path);f=p.freeze(c)
    monkeypatch.setattr(p.subprocess,'check_output',lambda *a,**k:'b'*40+'\n')
    (tmp_path/'report-only.py').write_text('new descendant report module')
    assert p.verify_protocol(Path(c['output_dir'])/'protocol.json')==f


def test_production_source_list_cannot_omit_the_local_model_loader(tmp_path,monkeypatch):
    p=api();c=inputs(tmp_path);c['fixture']=False
    def committed(commit,names,fixture=False):
        return {'commit':commit,'sha256':{name:p.file_hash(name) for name in names}}
    monkeypatch.setattr(p,'_capture_source',committed)
    f=p.freeze(c)
    assert 'src/outcome_poc/train.py' in f['source']['sha256']
    assert 'src/outcome_poc/protocol.py' in f['source']['sha256']

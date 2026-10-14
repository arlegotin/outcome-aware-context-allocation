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
        'models':{},'identities':{'feature_schema':'f','scorer':'s'}}
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

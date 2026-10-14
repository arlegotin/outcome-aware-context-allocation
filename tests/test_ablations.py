"""Hand-calculated synthetic receipts; no reader, index or benchmark inputs."""
from copy import deepcopy
from dataclasses import asdict, replace
import importlib
import json
from pathlib import Path

import pytest

from outcome_poc.protocol import freeze_methods, plan_jobs
from outcome_poc.schemas import CostEvent, Prediction, ScoredTask, Task
from outcome_poc.storage import content_hash, canonical_bytes
from test_protocol import inputs


def api():
    assert importlib.util.find_spec('outcome_poc.robustness'), 'robustness implementation missing'
    return importlib.import_module('outcome_poc.robustness')


def synthetic(tmp_path):
    config = inputs(tmp_path)
    methods = freeze_methods(config['development'], config['selection'], config['capacity'])
    tasks = [Task('q0', 'protected', 'Fixture question?', [f'd{i}' for i in range(10)]),
             Task('q1', 'protected', 'Another fixture?', [f'd{i}' for i in range(10)])]
    jobs = plan_jobs(methods, tasks)
    protocol = {'protocol_hash':'fixture-protocol', 'fixture':True, 'run_dir':str(tmp_path/'run'),
                'sample':{'task_ids':['q0','q1'], 'n':2, 'N':20},
                'methods':methods, 'schedule':{'jobs':jobs}}
    scores, predictions, events, evidence, receipts = [], [], [], [], {}
    for pos, job in enumerate(jobs):
        method = job['method']; family = method['family']; tid = job['task_id']; jid = job['job_id']
        k = method.get('k', 10 if family in ('POST-OUTCOME','LLM-SUFFICIENCY') else
                       10 if family=='PRE-OUTCOME-GBM' and tid=='q1' else 2)
        pid = (f'FIXED-{k}' if family=='FIXED' else
               f'ADAPTIVE-k-{"published" if family.endswith("published") else "tuned"}-B{method["buffer"]}'
               if family.startswith('ADAPTIVE-k') else method.get('model_name', family))
        elapsed = 0.; jobevents = []; paid = []
        def event(role, seconds):
            nonlocal elapsed
            start = int(round((pos*100+elapsed)*1e9)); elapsed += seconds
            stop = int(round((pos*100+elapsed)*1e9))
            ev = CostEvent(content_hash([jid,role]),'confirmation',tid,pid,role,start,stop,
                           (stop-start)/1e9,0,0,'none',None,None,None,None,1,'ok')
            jobevents.append(ev)
            return ev
        event('retrieval',1.)
        roles = [('draft',2),('answer',k)] if family=='POST-OUTCOME' else (
                [('judge',2),('answer',k)] if family=='LLM-SUFFICIENCY' else [('answer',k)])
        for role, budget in roles:
            event('evidence:'+role,.2); event('prompt:'+role,.3)
            ev = event('generation:'+role,2. if budget==2 else 4.)
            if family=='POST-OUTCOME' and role=='answer':
                jobevents[-1] = ev = replace(ev,clean_prefill_seconds=.5)
            event('parse:'+role,.1)
            result = {'raw_output':'fixture '+str(budget),'answer':'fixture','citations':[['d0',0]],
                      'status':'ok','prompt_token_ids':[100,budget],'generated_token_ids':[200],
                      'prompt_tokens':2,'generated_tokens':1,'stop_reason':'stop','telemetry':{}}
            if family=='POST-OUTCOME' and role=='answer':result['telemetry']['clean_prefill_seconds']=.5
            paid.append({'event':asdict(ev),'request':{
                'model_revision':'r','model_hash':'h','prompt_hash':f'prompt-{tid}-{budget}',
                'decoding_hash':'d','role':'judge' if role=='judge' else 'answer',
                'max_context_tokens':8192,'max_new_tokens':16 if role=='judge' else 256,
                'timeout_seconds':20.,'cache_mode':'none'},'result':result})
        event('routing',.1 if family=='FIXED' else .4); event('payload',.2)
        # Direct repeats are deliberately slower than the independent saved source.
        elapsed += .1 + (.5*job['repetition_id'] if job['scope']=='primary' else 0.)
        stop = int(round((pos*100+elapsed)*1e9))
        jobevents.append(CostEvent(content_hash([jid,'serving']),'confirmation',tid,pid,'serving',
            pos*100_000_000_000,stop,(stop-pos*100_000_000_000)/1e9,0,0,'none',None,None,None,None,1,'ok'))
        duration = jobevents[-1].elapsed_seconds
        final = paid[-1]['result']
        prediction = Prediction('confirmation',tid,pid,protocol['protocol_hash'],jid,1,job['repetition_id'],
            [f'd{i}' for i in range(k)],final['raw_output'],'fixture',[('d0',0)],'ok','r',
            paid[-1]['request']['prompt_hash'],'d',duration,2,1,len(paid),[p['event']['event_id'] for p in paid])
        success = int((tid=='q0' and k==2) or (tid=='q1' and k==10))
        score = ScoredTask('confirmation',tid,pid,jid,job['repetition_id'],success,success,success,
                           float(success),float(success),float(success),duration,duration+.5)
        mapping = {'job_id':jid,'task_id':tid,'scope':job['scope'],'arm':job['arm'],
            'config_id':method['config_id'],'repetition_id':job['repetition_id'],
            'prediction_hash':content_hash(prediction),'score_hash':content_hash(score),
            'attempts':[{'attempt':1,'event_ids':[e.event_id for e in jobevents],'files':{}}],
            'event_ids':[e.event_id for e in jobevents],
            'shared_allocations':[{'event_id':'shared','source_id':'setup','allocated_seconds':.5}],
            'output_parity_hash':content_hash([tid,k,method]),'status':'ok','action_k':k,
            'prompt_tokens':2,'final_serving_start_ns':pos*100_000_000_000}
        predictions.append(prediction);scores.append(score);events.extend(jobevents);evidence.append(mapping)
        receipts[jid] = {'decision':{'action_k':k,'policy_id':pid},'paid':paid}
    mapping = {'protocol_hash':protocol['protocol_hash'],'jobs':evidence,
               'cost_authority':'ScoredTask complete validated accounting; components are nested'}
    return protocol,scores,events,predictions,mapping,receipts


def test_attribution_keeps_frozen_pair_and_all_family_denominators(tmp_path):
    p,s,e,*_ = synthetic(tmp_path); before = canonical_bytes(p)
    result = api().ablate(p,s,e)
    assert len(result['comparisons']) == 13
    assert all(row['assigned_tasks']==2 for row in result['comparisons'])
    proxy = next(r for r in result['comparisons'] if r['family']=='PROXY-LABEL')
    assert proxy['joint_cells'] == {'both_fail':0,'candidate_only':1,'comparator_only':0,'both_success':1}
    assert proxy['joint_difference'] == .5
    assert result['selected'] == p['methods']['selected']
    assert result['selection_performed'] is False and canonical_bytes(p)==before
    assert result['all_family_superiority'] == 'not prespecified'


@pytest.mark.parametrize('corrupt',['missing','duplicate','identity','events'])
def test_attribution_rejects_reduced_denominator_and_ambiguous_inputs(tmp_path,corrupt):
    p,s,e,*_ = synthetic(tmp_path)
    if corrupt=='missing': s.pop()
    if corrupt=='duplicate': s[-1]=s[0]
    if corrupt=='identity': s[0]=replace(s[0],task_id='wrong')
    if corrupt=='events': e.append(e[0])
    with pytest.raises(ValueError): api().ablate(p,s,e)


def test_accounting_reconstructs_from_fixed_source_and_own_routing_without_double_count(tmp_path):
    args = synthetic(tmp_path)
    result = api().audit_accounting(*args)
    rows = [r for r in result['reconstruction'] if r['arm']=='A' and r['task_id']=='q0']
    assert len(rows)==2
    assert [r['reconstructed_seconds'] for r in rows] == pytest.approx([4.3,4.3])
    assert [r['direct_seconds'] for r in rows] == pytest.approx([4.8,5.3])
    assert [r['direct_minus_reconstructed'] for r in rows] == pytest.approx([.5,1.])
    first = result['jobs'][0]
    assert first['instrumented_union_seconds'] + first['residual_overhead_seconds'] == pytest.approx(first['enclosing_seconds'])
    assert first['experiment_seconds'] == pytest.approx(first['serving_seconds']+.5)
    assert result['primary_cost_authority'] == 'actual fresh direct complete pipeline'
    assert result['post_optimistic_bound']['executed'] is False
    assert result['post_optimistic_bound']['removed_full_prefill_seconds'] == 1.
    assert sum(r['assigned_jobs'] for r in result['action_length_strata'])==8
    assert all(r['compatible_jobs']==r['assigned_jobs'] for r in result['action_length_strata'])


@pytest.mark.parametrize('role',['retrieval','parse:answer','generation:draft'])
def test_missing_paid_component_cannot_be_hidden_inside_residual(tmp_path,role):
    p,s,e,pred,mapping,receipts = synthetic(tmp_path)
    chosen = next(row for row in mapping['jobs'] if any(v.event_id in row['event_ids'] and v.role==role for v in e))
    removed = next(v for v in e if v.event_id in chosen['event_ids'] and v.role==role)
    e.remove(removed);chosen['event_ids'].remove(removed.event_id)
    chosen['attempts'][0]['event_ids'].remove(removed.event_id)
    with pytest.raises(ValueError,match='role|paid|component|generation'):
        api().audit_accounting(p,s,e,pred,mapping,receipts)


def test_policy_parity_hash_is_not_cross_policy_output_identity(tmp_path):
    p,s,e,pred,mapping,receipts = synthetic(tmp_path)
    result = api().audit_accounting(p,s,e,pred,mapping,receipts)
    assert all(r['status']=='compatible' for r in result['reconstruction'])
    direct = next(j for j in p['schedule']['jobs'] if j['scope']=='primary' and j['arm']=='A')
    receipts[direct['job_id']]['paid'][-1]['result']['generated_token_ids']=[999]
    result = api().audit_accounting(p,s,e,pred,mapping,receipts)
    mismatch = next(r for r in result['reconstruction'] if r['job_id']==direct['job_id'])
    assert mismatch['status']=='incompatible' and mismatch['reconstructed_seconds'] is None
    assert result['assigned_direct_jobs']==8 and len(result['reconstruction'])==8


def test_event_ownership_cannot_cross_repeated_policy_jobs(tmp_path):
    p,s,e,pred,mapping,receipts = synthetic(tmp_path)
    repeated=[r for r in mapping['jobs'] if r['task_id']=='q0' and r['arm']=='A']
    repeated[1]['event_ids'][0]=repeated[0]['event_ids'][0]
    with pytest.raises(ValueError,match='ownership|event|attempt'):
        api().audit_accounting(p,s,e,pred,mapping,receipts)


def test_oracle_uses_actual_two_actions_and_AA_uses_only_fresh_repeats(tmp_path):
    args=synthetic(tmp_path);p,s,e,pred,mapping,_=args
    result=api().diagnostics(p,s,pred,mapping)
    assert result['oracle']['cells']=={'both_fail':0,'rescue':1,'harm':1,'both_success':0}
    assert result['oracle']['oracle_quality']==1.
    assert result['oracle']['frontier'][-1]['successes']==2
    assert result['oracle']['deployable'] is False
    assert result['AA']['A']['assigned_tasks']==2
    assert result['AA']['A']['pairs'][0]['seconds']==pytest.approx([4.8,5.3])
    assert result['always_abstain']['ratio'] is None
    assert result['always_abstain']['reason']=='zero_successes'
    assert result['no_context']['status']=='not_scored_in_primary'


def receipt_tree(tmp_path, monkeypatch):
    """Stub only frozen full-run admission; exercise real new receipt I/O/hashes."""
    from outcome_poc import protected,protocol as protocol_module
    from outcome_poc.storage import atomic_json,append_jsonl
    from outcome_poc.protocol import file_hash
    from types import SimpleNamespace
    p,s,e,pred,mapping,receipts=synthetic(tmp_path)
    root=Path(p['run_dir']);root.mkdir()
    for row in mapping['jobs']:
        jid=row['job_id'];directory=root/'jobs'/jid/'attempt-1';directory.mkdir(parents=True)
        paths=[]
        path=directory/'decision.json';atomic_json(path,{'decision':receipts[jid]['decision']});paths.append(path)
        for number,paid in enumerate(receipts[jid]['paid'],1):
            path=directory/f'paid-{number}.started.json';atomic_json(path,{'request':paid['request']});paths.append(path)
            path=directory/f'paid-{number}.finished.json'
            atomic_json(path,{k:v for k,v in paid.items() if k!='request'});paths.append(path)
        row['attempts'][0]['files']={str(path.relative_to(root)):file_hash(path) for path in paths}
    for score in s: append_jsonl(root/'scores.jsonl',score)
    atomic_json(root/'job-evidence.json',mapping)
    for name in ('predictions.closed.json','protected-run.closed.json'): atomic_json(root/name,{'synthetic':True})
    # No gold file is created: core admission is an isolated, already tested boundary.
    atomic_json(root/'scores.jsonl.closed.json',{'protocol_hash':p['protocol_hash'],
        'record_count':len(s),'assigned_unique_tasks':2,'paid_receipt_coverage':'forward_v2',
        'hashes':{name:file_hash(root/name) for name in ('scores.jsonl','job-evidence.json','predictions.closed.json','protected-run.closed.json')}})
    families={}
    for job in p['schedule']['jobs']:
        if job['scope']=='primary':continue
        key=job['scope']+':'+job['method']['config_id']
        rows=[x for x in p['schedule']['jobs'] if x['scope']==job['scope'] and x['method']['config_id']==job['method']['config_id']]
        values=[score for score in s if score.job_id in {r['job_id'] for r in rows}]
        success=sum(v.joint_em for v in values);total=sum(v.total_serving_seconds for v in values)
        families[key]={'n':2,'repetitions':1,'success_count':success,'quality':success/2,
            'total_time':total,'mean_time':total/2,'ratio':total/success if success else None,
            'reason':None if success else 'zero_successes','answer_em':sum(v.answer_em for v in values)/2,
            'scope':job['scope'],'config_id':job['method']['config_id'],'job_ids':[r['job_id'] for r in rows]}
    atomic_json(root/'analysis.json',{'protocol_hash':p['protocol_hash'],'assigned_unique_tasks':2,
        'population':20,'families':families,'primary':{'status':'inconclusive'},'quality_guards':[],
        'quality_claim_valid':False,'outcome':'inconclusive'})
    monkeypatch.setattr(protocol_module,'verify_protocol',lambda _:p)
    monkeypatch.setattr(protected,'validate_run',lambda *_:(pred,SimpleNamespace(verify_unchanged=lambda:None)))
    from outcome_poc import runner
    monkeypatch.setattr(runner,'load_events',lambda _:e)
    return p,root


def test_closed_consumer_binds_external_analysis_and_reuses_frozen_metrics(tmp_path,monkeypatch):
    p,root=receipt_tree(tmp_path,monkeypatch)
    before={str(path):path.read_bytes() for path in root.rglob('*') if path.is_file()}
    result=api().analyze_closed(p)
    assert result['input_hashes']['analysis.json']
    assert result['families']==json.loads((root/'analysis.json').read_text())['families']
    assert result['scientific_data_access']=='closed receipts only; no gold records opened'
    assert before=={str(path):path.read_bytes() for path in root.rglob('*') if path.is_file()}


@pytest.mark.parametrize('corrupt',['analysis','score','attempt'])
def test_closed_consumer_rejects_changed_unbound_analysis_or_bound_receipts(tmp_path,monkeypatch,corrupt):
    from outcome_poc.storage import atomic_json
    p,root=receipt_tree(tmp_path,monkeypatch)
    if corrupt=='analysis':
        value=json.loads((root/'analysis.json').read_text());next(iter(value['families'].values()))['ratio']=0.
        atomic_json(root/'analysis.json',value)
    elif corrupt=='score': (root/'scores.jsonl').write_text('{}\n')
    else: next(root.glob('jobs/*/attempt-*/decision.json')).write_text('{}')
    with pytest.raises(ValueError):api().analyze_closed(p)


def test_frozen_descriptor_and_mapping_action_cannot_be_replaced_in_analysis(tmp_path):
    p,s,e,pred,mapping,receipts=synthetic(tmp_path)
    job=next(j for j in p['schedule']['jobs'] if j['scope']=='representative' and j['method']['family']=='PRE-RF')
    job['method']['threshold']=.9
    with pytest.raises(ValueError,match='frozen'):api().ablate(p,s,e)


def test_failed_attempt_and_owned_reload_stay_in_reconstructed_numerator(tmp_path):
    p,s,e,pred,mapping,receipts=synthetic(tmp_path)
    source=next(j for j in p['schedule']['jobs'] if j['scope']=='oracle-source' and j['task_id']=='q0')
    jid=source['job_id'];i=next(i for i,v in enumerate(pred) if v.job_id==jid)
    current=[v for v in e if v.event_id in mapping['jobs'][i]['event_ids']]
    updated=[replace(v,attempt=2) for v in current]
    e=[v for v in e if v.event_id not in {x.event_id for x in current}]+updated
    for paid in receipts[jid]['paid']:paid['event']['attempt']=2
    pred[i]=replace(pred[i],attempt=2)
    failed=CostEvent('failed-attempt','confirmation','q0',pred[i].policy_id,'serving',0,2_000_000_000,2.,0,0,'none',None,None,None,None,1,'infra_error')
    reload=replace(failed,event_id='owned-reload',role='worker_reload',start_ns=2_000_000_000,stop_ns=5_000_000_000,elapsed_seconds=3.,status='ok')
    e.extend([failed,reload]);row=mapping['jobs'][i]
    row['attempts']=[{'attempt':1,'event_ids':['failed-attempt','owned-reload'],'files':{}},
                     {**row['attempts'][0],'attempt':2}]
    row['event_ids']=['failed-attempt','owned-reload',*row['event_ids']]
    s[i]=replace(s[i],total_serving_seconds=s[i].total_serving_seconds+5,total_experiment_seconds=s[i].total_experiment_seconds+5)
    row['prediction_hash']=content_hash(pred[i]);row['score_hash']=content_hash(s[i])
    result=api().audit_accounting(p,s,e,pred,mapping,receipts)
    selected=next(r for r in result['reconstruction'] if r['task_id']=='q0' and r['arm']=='A')
    assert selected['reconstructed_seconds']==pytest.approx(9.3)
    assert result['jobs'][i]['serving_seconds']==pytest.approx(9.)
    assert result['jobs'][i]['attempts']==2


def test_mapping_action_and_paid_request_fields_must_be_complete(tmp_path):
    p,s,e,pred,mapping,receipts=synthetic(tmp_path)
    mapping['jobs'][0]['action_k']=2
    with pytest.raises(ValueError,match='action'):api().audit_accounting(p,s,e,pred,mapping,receipts)


def test_optimistic_bound_is_unknown_without_measured_full_prefill_telemetry(tmp_path):
    p,s,e,pred,mapping,receipts=synthetic(tmp_path)
    jid=next(j['job_id'] for j in p['schedule']['jobs'] if j['method']['family']=='POST-OUTCOME')
    receipts[jid]['paid'][-1]['result']['telemetry']={}
    bound=api().audit_accounting(p,s,e,pred,mapping,receipts)['post_optimistic_bound']
    assert bound['optimistic_serving_seconds'] is None and bound['reason']=='clean_prefill_not_fully_measured'


def test_closed_cli_writes_only_separate_output_and_help_is_lazy(tmp_path,monkeypatch):
    from outcome_poc.storage import atomic_json
    from outcome_poc.__main__ import main
    p,root=receipt_tree(tmp_path,monkeypatch)
    protocol_path=tmp_path/'protocol.json';atomic_json(protocol_path,p)
    output=tmp_path/'robustness.json'
    assert main(['ablate','--protocol',str(protocol_path),'--output',str(output)])==0
    assert json.loads(output.read_text())['attribution']['assigned_tasks']==2
    first=output.read_bytes()
    assert main(['ablate','--protocol',str(protocol_path),'--output',str(output)])==0
    assert output.read_bytes()==first
    from outcome_poc.storage import read_jsonl
    attempts=list(read_jsonl(output.with_suffix('.attempts.jsonl')))
    assert len(attempts)==2 and all(r['elapsed_seconds']>0 and r['status']=='ok' for r in attempts)
    with pytest.raises(ValueError,match='outside'):main(['ablate','--protocol',str(protocol_path),'--output',str(root/'bad.json')])

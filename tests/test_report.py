"""Report claims and accounting from invented evidence only."""
from copy import deepcopy
import importlib
import json
import subprocess
import sys

import pytest


def api():
    assert importlib.util.find_spec('outcome_poc.report'), 'report implementation missing'
    return importlib.import_module('outcome_poc.report')


def evidence():
    return {'execution_status':'complete','assigned_questions':40,'assigned_jobs':160,'completed_jobs':160,
        'wall_time_valid':True,'timing_validation':{'status':'passed','evidence':'fixture-timing'},
        'scope':'Synthetic reader/retriever/population/hardware; A versus frozen B only',
        'selected':{'A':'outcome','B':'proxy'},'analysis':{
            'primary':{'status':'valid','efficiency_advantage':True,'ci':[-3.,-1.],
                'recorded_flags':{'timing_stationary':True,'deterministic_outputs':True,'single_dominant':False}},
            'quality_outcomes_valid':True,
            'quality_guards':[{'comparator':c,'metric':m,'ci':[0.,.1],'tail_alpha':.05/16,
                'harm_count':0,'rescue_count':1} for c in ('selected','fixed_ten') for m in ('joint_em','answer_em')]},
        'regressions':{'failure_clear':True,'latency_clear':True},'methods':[]}


def test_known_invalid_wall_time_overrides_numerical_win_and_quality_claim(tmp_path):
    s=evidence();s['wall_time_valid']=False
    s['wall_time_reason']='Host sleep excluded: wall300.75s versus perf2.4468s'
    result=api().report(s,tmp_path/'final_report.md')
    assert result['outcome']=='inconclusive'
    assert not result['claims']['efficiency']
    assert result['timing']['interpretation']=='active-compute diagnostic only'
    text=(tmp_path/'final_report.md').read_text()
    assert 'Host sleep excluded' in text and text.rstrip().splitlines()[-1]=='inconclusive'


def test_incomplete_retains_assignment_and_rejects_subset_scores(tmp_path):
    s=evidence();s.update(execution_status='incomplete',assigned_questions=480,assigned_jobs=8640,completed_jobs=111)
    s.pop('analysis');s['methods']=[]
    result=api().report(s,tmp_path/'final_report.md')
    assert result['assigned_questions']==480 and result['assigned_jobs']==8640
    assert result['analysis'] is None and result['outcome']=='inconclusive'
    s['analysis']=evidence()['analysis']
    with pytest.raises(ValueError,match='incomplete|unclosed'):api().report(s,tmp_path/'bad.md')


@pytest.mark.parametrize('mutate',[
    lambda s:s['analysis']['quality_guards'].pop(),
    lambda s:s['analysis']['quality_guards'][0].update(ci=[-.01,.1]),
    lambda s:s['regressions'].update(failure_clear=None),
    lambda s:s['regressions'].update(latency_clear=False)])
def test_quality_preservation_requires_four_guards_and_no_regression(mutate,tmp_path):
    s=evidence();mutate(s)
    result=api().report(s,tmp_path/'final_report.md')
    assert result['claims']['quality_preserved'] is False
    text=(tmp_path/'final_report.md').read_text()
    if s['regressions'].get('latency_clear') is False:
        assert 'latency regression' in text
    else:
        assert 'quality preservation remains unresolved' in text


def test_valid_efficiency_with_unresolved_quality_is_explicitly_qualified(tmp_path):
    s=evidence();s['analysis']['quality_guards'][0]['ci']=[-.01,.1]
    result=api().report(s,tmp_path/'final_report.md')
    assert result['outcome']=='qualified positive' and result['claims']['efficiency']
    assert result['selected']['B']=='proxy'
    assert json.loads((tmp_path/'summary.json').read_text())['outcome']==result['outcome']
    assert 'frozen B only' in (tmp_path/'final_report.md').read_text()


@pytest.mark.parametrize('mutate',[
    lambda s:s.update(wall_time_valid=None),
    lambda s:s.update(timing_validation={'status':'unexecuted'}),
    lambda s:s['analysis']['primary'].update(status='inconclusive'),
    lambda s:s['analysis']['primary']['recorded_flags'].update(timing_stationary=None)])
def test_missing_validity_never_becomes_positive(mutate):
    s=evidence();mutate(s)
    assert api().classify_outcome(s)=='inconclusive'


def test_blocked_and_development_only_work_without_ml_dependencies(tmp_path):
    state=tmp_path/'state.json';state.write_text(json.dumps({'execution_status':'blocked','missing_prerequisites':['reader']}))
    code="""import sys,importlib.abc
class Deny(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in ('mlx','mlx_lm','torch','numpy','scipy','outcome_poc.scoring'): raise AssertionError(fullname)
sys.meta_path.insert(0,Deny())
from outcome_poc.__main__ import main
main(['report','--state',sys.argv[1],'--output',sys.argv[2]])
"""
    result=subprocess.run([sys.executable,'-c',code,str(state),str(tmp_path/'report.md')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert (tmp_path/'report.md').read_text().rstrip().endswith('blocked by prerequisites')
    assert api().classify_outcome({'execution_status':'development_only'})=='inconclusive'


def test_zero_success_ratio_and_break_even_use_per_query_saving():
    r=api().ratio_summary([2.,4.],[0,0])
    assert r['ratio'] is None and r['reason']=='zero_successes' and r['n']==2
    assert api().break_even(100.,2.,1.)=={'queries':None,'reason':'nonpositive_saving','delta_t':-1.}
    assert api().break_even(None,1.,2.)['reason']=='unknown_adaptation_cost'
    assert api().break_even(100.,1.,3.)['queries']==50.


def test_cost_sources_deduplicate_allocations_and_nested_work():
    rows=[{'physical_id':'native','seconds':10.,'category':'experiment'},
          {'physical_id':'generation','seconds':8.,'parent_id':'native','category':'experiment'},
          {'physical_id':'index','seconds':3.,'category':'adaptation'},
          {'physical_id':'index','seconds':3.,'category':'adaptation','allocation_stage':'tune'},
          {'physical_id':'old-cold','seconds':None,'reason':'unmeasured','category':'assets'}]
    result=api().cost_inventory(rows)
    assert result['known_physical_seconds']==13.
    assert result['total_physical_seconds'] is None
    assert result['unknown_physical_ids']==['old-cold']
    assert result['counted_physical_ids']==['index','native','old-cold']
    rows.append({'physical_id':'index','seconds':4.,'category':'adaptation'})
    with pytest.raises(ValueError,match='conflicting'):api().cost_inventory(rows)


def test_rows_keep_repetition_within_question_and_failed_cost(tmp_path):
    from test_ablations import synthetic
    from dataclasses import replace
    p,s,e,pred,mapping,_=synthetic(tmp_path)
    # Every method has 2 unique assigned questions; primary has two repetitions.
    selected=[j for j in p['schedule']['jobs'] if j['scope']=='primary' and j['arm']=='A']
    ids={j['job_id'] for j in selected}
    s=[replace(x,joint_em=0) if x.job_id in ids else x for x in s]
    pred=[replace(x,status='timeout') if x.job_id in ids else x for x in pred]
    rows=api().method_rows(p,s,pred,e,mapping)
    a=next(row for row in rows if row['scope']=='primary' and row['arm']=='A')
    assert a['assigned_n']==2 and a['repetitions']==2 and a['failure_rate']==1.
    assert a['ratio'] is None and a['mean_seconds']>0 and a['paid_calls']==4
    assert len(rows)==16
    with pytest.raises(ValueError,match='schedule|assigned'):api().method_rows(p,s[:-1],pred,e,mapping)


def test_report_does_not_publish_raw_dataset_fields(tmp_path):
    s=evidence();s['provenance']={'raw_output':'secret fixture answer'}
    with pytest.raises(ValueError,match='private|raw'):api().report(s,tmp_path/'final.md')


def test_known_cost_subtotal_does_not_turn_empty_inventory_into_zero_total():
    result=api().cost_inventory([])
    assert result['total_physical_seconds'] is None
    assert result['reason']=='no_cost_sources'


def test_incomplete_cannot_publish_efficiency_in_supplied_method_rows(tmp_path):
    s={'execution_status':'incomplete','assigned_questions':480,'assigned_jobs':8640,
       'methods':[{'assigned_n':10,'ratio':.01}]}
    with pytest.raises(ValueError,match='incomplete'):api().report(s,tmp_path/'bad.md')


def test_positive_requires_scope_and_evaluated_pair(tmp_path):
    s=evidence();s.pop('scope')
    with pytest.raises(ValueError,match='scope|selected'):api().report(s,tmp_path/'bad.md')


def test_source_inventory_rejects_unknown_without_reason_and_cycles():
    with pytest.raises(ValueError,match='reason'):api().cost_inventory([{'physical_id':'x','seconds':None}])
    with pytest.raises(ValueError,match='cyclic'):api().cost_inventory([
        {'physical_id':'x','seconds':1.,'parent_id':'y'},{'physical_id':'y','seconds':1.,'parent_id':'x'}])


def test_distinct_runs_do_not_alias_setup_but_actual_index_origin_is_reused():
    rows=[{'physical_id':'setup','run_identity':run,'seconds':3.,'category':'experiment'} for run in ('protocol1/root1','protocol2/root2')]
    rows += [{'physical_id':'index','run_identity':run,'original_physical_id':'index-attempt:original',
              'seconds':5.,'category':'adaptation'} for run in ('protocol1/root1','protocol2/root2')]
    result=api().cost_inventory(rows)
    assert result['known_physical_seconds']==11.
    assert len(result['counted_physical_ids'])==3


def test_quality_table_and_unknown_method_fields_remain_explicit(tmp_path):
    s=evidence();s['methods']=[{'scope':'primary','arm':'A','config_id':'outcome','assigned_n':40,
        'repetitions':2,'joint_em':0.,'answer_em':.5,'support_f1':.2,'mean_seconds':1.,'p95_seconds':2.,
        'ratio':None,'reason':'zero_successes','prompt_tokens':100,'output_tokens':10,'paid_calls':80,
        'failure_rate':.1,'adaptation_seconds':None}]
    s['analysis']['primary'].update(status='inconclusive',efficiency_advantage=False,ci=None)
    result=api().report(s,tmp_path/'final_report.md')
    text=(tmp_path/'final_report.md').read_text()
    assert 'infinity (zero successes)' in text and 'unavailable' in text
    assert 'primary_interval' in (tmp_path/'baseline-table.csv').read_text()
    assert result['methods'][0]['primary_interval'] is None


@pytest.mark.parametrize('wall',[False,None,True])
@pytest.mark.parametrize('economics',[None,{}, {'adaptation_seconds':100.,'mean_a':1.,'mean_b':3.}])
def test_incomplete_or_invalid_cannot_retain_injected_break_even(tmp_path,wall,economics):
    s={'execution_status':'incomplete','assigned_questions':480,'assigned_jobs':8640,'completed_jobs':100,
       'wall_time_valid':wall,'break_even':{'queries':1.,'delta_t':100.,'reason':None}}
    if economics is not None:s['economics']=economics
    result=api().report(s,tmp_path/'report.md')
    assert result['break_even']['queries'] is None
    assert result['break_even']['delta_t'] is None
    assert result['break_even']['reason'] in ('incomplete_results','wall_time_invalid_or_unverified')


def economic_evidence():
    s=evidence()
    s['methods']=[{'scope':'primary','arm':arm,'config_id':config,'assigned_n':40,
                   'repetitions':2,'mean_seconds':mean} for arm,config,mean in [('A','outcome',2.),('B','proxy',3.)]]
    s['analysis']['primary'].update(arm_a={'mean_time':2.},arm_b={'mean_time':3.})
    s['analysis']['assessment_binding']={'protocol_hash':'p','score_closure_hash':'closed'}
    s['protocol']={'protocol_hash':'p'}
    s['provenance']={'input_hashes':{'scores.jsonl.closed.json':'closed'}}
    s['economics']={'adaptation_seconds':100.}
    return s


@pytest.mark.parametrize('wall',[False,None])
def test_complete_invalid_wall_time_discards_injected_break_even_without_economics(tmp_path,wall):
    s=economic_evidence();s['wall_time_valid']=wall;s.pop('economics')
    s['break_even']={'queries':1.,'delta_t':100.,'reason':None}
    result=api().report(s,tmp_path/'report.md')
    assert result['break_even']=={'queries':None,'delta_t':None,'reason':'wall_time_invalid_or_unverified'}


def test_break_even_derives_means_from_closed_selected_arms(tmp_path):
    s=economic_evidence();s['break_even']={'queries':1.,'delta_t':100.,'reason':None}
    assert api().report(s,tmp_path/'report.md')['break_even']=={'queries':100.,'delta_t':1.,'reason':None}
    s['economics']['mean_a']=.001;s['economics']['mean_b']=100.
    with pytest.raises(ValueError,match='mean|closed'):api().report(s,tmp_path/'bad.md')


@pytest.mark.parametrize('change',[
    lambda s:s.pop('methods'),
    lambda s:s.pop('provenance'),
    lambda s:s['analysis']['assessment_binding'].update(score_closure_hash='different'),
    lambda s:s['methods'][0].update(config_id='retuned'),
    lambda s:s['analysis']['primary'].pop('arm_a'),
    lambda s:s['methods'][0].update(mean_seconds=None)])
def test_missing_authoritative_metrics_withholds_break_even(tmp_path,change):
    s=economic_evidence();change(s)
    s['economics'].update(mean_a=1.,mean_b=3.)
    result=api().report(s,tmp_path/'report.md')
    assert result['break_even']['queries'] is None
    assert result['break_even']['reason']=='missing_authoritative_metrics'


def test_closed_means_cannot_disagree_with_primary_analysis(tmp_path):
    s=economic_evidence();s['methods'][0]['mean_seconds']=.1
    with pytest.raises(ValueError,match='mean|closed'):api().report(s,tmp_path/'bad.md')


def test_bound_economics_keeps_unknown_adaptation_and_nonpositive_saving(tmp_path):
    s=economic_evidence();s['economics']['adaptation_seconds']=None
    assert api().report(s,tmp_path/'unknown.md')['break_even']['reason']=='unknown_adaptation_cost'
    s['methods'][0]['mean_seconds']=4.;s['analysis']['primary']['arm_a']['mean_time']=4.
    result=api().report(s,tmp_path/'slower.md')
    assert result['break_even']=={'queries':None,'delta_t':-1.,'reason':'nonpositive_saving'}
    assert 'infinity' in (tmp_path/'slower.md').read_text()


def test_supported_quality_loss_names_affected_guard_next_to_efficiency(tmp_path):
    s=evidence();s['analysis']['quality_guards'][0]['ci']=[-.2,-.1]
    result=api().report(s,tmp_path/'report.md')
    text=(tmp_path/'report.md').read_text()
    assert result['outcome']=='efficiency/quality tradeoff'
    assert 'supports lower joint EM versus frozen B*' in text
    assert 'quality preservation remains unresolved' not in text


@pytest.mark.parametrize('field,label',[('failure_clear','failure-rate regression'),('latency_clear','latency regression')])
def test_explicit_regression_is_not_described_as_unknown(tmp_path,field,label):
    s=evidence();s['regressions'][field]=False
    api().report(s,tmp_path/'report.md');text=(tmp_path/'report.md').read_text()
    assert label in text and 'quality preservation remains unresolved' not in text


def test_nondeterministic_quality_does_not_establish_supported_loss(tmp_path):
    s=evidence();s['analysis']['quality_outcomes_valid']=False
    s['analysis']['quality_guards'][0]['ci']=[-.2,-.1]
    result=api().report(s,tmp_path/'report.md')
    assert result['claims']['quality_loss_supported'] is False


def test_shared_origin_parents_resolve_before_nested_component_dedup():
    rows=[]
    for run in ('r1','r2'):
        # Child precedes parent and its nested origin also repeats across runs.
        rows.extend([{'physical_id':'encoding','parent_id':'index','original_physical_id':'shared-encoding',
                      'run_identity':run,'seconds':2.,'category':'adaptation'},
                     {'physical_id':'index','original_physical_id':'shared-index','run_identity':run,
                      'seconds':3.,'category':'adaptation'},
                     {'physical_id':'setup','run_identity':run,'seconds':4.,'category':'experiment'}])
    result=api().cost_inventory(rows)
    assert result['known_physical_seconds']==11.
    assert result['sources']['origin:shared-encoding']['parent_id']=='origin:shared-index'
    assert result['counted_physical_ids']==['origin:shared-index','r1:setup','r2:setup']

import importlib.util
from pathlib import Path
import pytest


def tool():
    path=Path('tools/task13_calibrate.py')
    assert path.exists(),'calibration tool missing'
    spec=importlib.util.spec_from_file_location('task13_calibrate',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def test_calibration_subset_is_stratified_deterministic_and_development_only():
    from outcome_poc.schemas import Task
    tasks=[Task(str(i),'tune','q'*i,['d']*10) for i in range(1,25)]
    selected=tool().choose_calibration_tasks(tasks,{t.task_id:len(t.question) for t in tasks},per_stratum=2)
    assert len(selected)==6 and len(set(selected))==6
    assert sum(int(i)<=8 for i in selected)==2
    assert sum(8<int(i)<=16 for i in selected)==2
    assert sum(int(i)>16 for i in selected)==2
    assert selected==tool().choose_calibration_tasks(list(reversed(tasks)),{t.task_id:len(t.question) for t in tasks},per_stratum=2)
    with pytest.raises(ValueError):tool().choose_calibration_tasks([Task('p','protected','q',[])],{'p':1})


def test_forced_output_modification_is_scoped_and_restored():
    from types import SimpleNamespace
    fake=SimpleNamespace(stream_generate=lambda *a,**k:k)
    original=fake.stream_generate
    with tool().force_max_output(fake,[0,2]) as suppressed:
        assert fake.stream_generate(1,2,3)['logits_processors']==[suppressed]
    assert fake.stream_generate is original
    with pytest.raises(RuntimeError):
        with tool().force_max_output(fake,[0]): raise RuntimeError('failure')
    assert fake.stream_generate is original


def test_maximum_prompt_accounts_for_token_merging_at_padding_boundary():
    # Adding the first padding token changes the tokenization of the prior suffix.
    def count(text): return 11 if text=='base' else 10+text.count(' a')
    value=tool().pad_to_tokens('base',count,100)
    assert count(value)==100
    with pytest.raises(ValueError):tool().pad_to_tokens('base',count,5)


def test_timing_summary_keeps_pair_covariance_and_full_roster_costs():
    rows=[]
    for task in ('short','long'):
        for rep,(a,b) in enumerate(((1.,2.),(2.,4.),(3.,6.),(4.,8.)),1):
            for arm,seconds in [('A',a),('B',b)]:
                rows.append({'task_id':task,'scope':'primary','phase':'full-roster' if rep<3 else 'later-pair-block',
                    'arm':arm,'repetition_id':rep,'elapsed_seconds':seconds,'output_hash':arm,'token_hash':arm,
                    'generation_calls':1,'status':'ok'})
        for i in range(14):rows.append({'task_id':task,'scope':'representative','phase':'full-roster',
            'elapsed_seconds':1.,'generation_calls':1,'status':'ok'})
    result=tool().timing_summary(rows,{'short':0,'long':2},full_roster_envelope_seconds=50.)
    assert result['full_roster_seconds_per_question']==[23.,23.]
    import numpy as np
    np.testing.assert_allclose(result['paired_tasks'][0]['arm_covariance_seconds_squared'],[[5/3,10/3],[10/3,20/3]],rtol=1e-15)
    assert result['deterministic_outputs'] is True
    assert result['timing_stationary'] is None
    assert result['native_envelope_factor']==50/46
    rows[0]['token_hash']='changed'
    assert tool().timing_summary(rows,{'short':0,'long':2},50.)['deterministic_outputs'] is False


def test_batch_forecast_uses_higher_complete_roster_mean_and_envelope():
    rows=[]
    for rep in (1,2):
        for arm in ('A','B'):
            rows.append({'task_id':'x','scope':'primary','phase':'full-roster','arm':arm,
                         'repetition_id':rep,'elapsed_seconds':1.,'output_hash':arm,'token_hash':arm})
    summary=tool().timing_summary(rows,{'x':0},4.,historical_mean_seconds=30.,historical_envelope_factor=1.1)
    assert summary['conservative_seconds_per_question']==pytest.approx(49.5)

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

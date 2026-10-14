import importlib.util
from pathlib import Path

import pytest

from outcome_poc import runner,scoring
from outcome_poc.schemas import GoldRecord
from outcome_poc.storage import append_jsonl
from serving_helpers import fixture_runtime


def test_final_development_rescore_matches_closed_saved_metrics(tmp_path):
    path=Path(__file__).parents[1]/'tools/task14_parity.py'
    assert path.exists(), 'development scorer parity tool missing'
    spec=importlib.util.spec_from_file_location('task14_parity',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    runtime,job,_=fixture_runtime(tmp_path)
    p=runner.execute_job(job,runtime,tmp_path);runner.close_run(tmp_path,[job])
    gold=GoldRecord('task','blue',[('Lamp 0',0)])
    append_jsonl(tmp_path/'gold.jsonl',gold)
    for identity in job['task'].candidate_ids: append_jsonl(tmp_path/'documents.jsonl',runtime.documents.get(identity))
    expected=scoring.Scorer().score(p,gold,runtime.documents,run_dir=tmp_path)
    append_jsonl(tmp_path/'scores.jsonl',expected)
    result=module.rescore_development_run(tmp_path,tmp_path/'gold.jsonl',tmp_path/'documents.jsonl',tmp_path/'new')
    assert result['exact_score_parity'] and result['count']==1
    (tmp_path/'scores.jsonl').write_text((tmp_path/'scores.jsonl').read_text().replace('"joint_em":1','"joint_em":0'))
    with pytest.raises(ValueError,match='parity'):
        module.rescore_development_run(tmp_path,tmp_path/'gold.jsonl',tmp_path/'documents.jsonl',tmp_path/'bad')

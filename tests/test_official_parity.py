"""Run the authenticated official source on authored data, when supplied.

No network in tests. Set HOTPOT_EVALUATOR_PATH to the pinned public file. Its
optional ujson import uses stdlib json only in this test; scoring functions and
the eval entry point execute unchanged from authenticated source bytes.
"""
import ast
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

from outcome_poc.scoring import Scorer, EVALUATOR_PROVENANCE
from outcome_poc.schemas import GoldRecord, Prediction
from retrieval_helpers import document, store


@pytest.fixture(scope='module')
def official():
    name = os.environ.get('HOTPOT_EVALUATOR_PATH')
    if not name:
        pytest.skip('pinned external evaluator absent; set HOTPOT_EVALUATOR_PATH for actual-source parity')
    raw = Path(name).read_bytes()
    assert len(raw) == EVALUATOR_PROVENANCE['source_bytes']
    assert hashlib.sha256(raw).hexdigest() == EVALUATOR_PROVENANCE['source_sha256']
    spec = importlib.util.spec_from_file_location('authenticated_hotpot_reference',name)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'ujson':json}):
        spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('answer,gold_answer,citations,gold_indices', [
    ('The, RED-blue!', 'redblue', [1,1], [1]),
    ('yes', 'yes red', [1], [1]),
    ('no red', 'no', [1], [1]),
    ('red red blue', 'red blue blue', [0,1], [1]),
    ('', 'the', [], []),
    ('violet', 'violet', [3], [1,3]),
    ('noanswer', 'noanswer', [1,3], [1,3]),
])
def test_actual_scorer_matches_pinned_official_entrypoint(tmp_path,capsys,official,answer,gold_answer,citations,gold_indices):
    doc = document('Original title', ['Noise.','Bridge.','Noise again.','Final relation.'])
    documents = store(tmp_path,[doc])
    p = Prediction('run','task','fixed','protocol','job',1,0,[doc.doc_id], 'raw',answer,
                   [(doc.doc_id,i) for i in citations],'ok','rev','prompt','decoder',1.,1,1,1,['event'])
    g = GoldRecord('task',gold_answer,[(doc.title,i) for i in gold_indices])
    scored = Scorer().score(p,g,documents)
    prediction = tmp_path/'official-prediction.json'
    gold = tmp_path/'official-gold.json'
    prediction.write_text(json.dumps({'answer':{'task':answer},'sp':{'task':[(doc.title,i) for i in citations]}}))
    gold.write_text(json.dumps([{'_id':'task','answer':gold_answer,'supporting_facts':g.supporting_facts}]))
    official.eval(prediction,gold)
    reference = ast.literal_eval(capsys.readouterr().out.strip())
    assert scored.answer_em == reference['em']
    assert scored.answer_f1 == pytest.approx(reference['f1'])
    assert scored.support_em == reference['sp_em']
    assert scored.support_f1 == pytest.approx(reference['sp_f1'])
    if answer.strip():
        assert scored.joint_em == reference['joint_em']
        assert scored.joint_f1 == pytest.approx(reference['joint_f1'])
    else:
        assert reference['joint_em'] == 1 and scored.joint_em == 0  # intentional validity guard
    invalid = Scorer().score(replace(p,status='invalid_citation'),g,documents)
    assert invalid.joint_em == 0
    if citations:
        outside = Scorer().score(replace(p,evidence_ids=[]),g,documents)
        assert outside.joint_em == 0

"""Fit-only learner contracts and independently scored acquisition fixtures."""
from dataclasses import replace
import importlib.util
import json

import numpy as np
import pytest

from outcome_poc.features import build_features, feature_schema
from outcome_poc.schemas import GoldRecord, PairedActionRow
from test_features import packet


def training():
    assert importlib.util.find_spec('outcome_poc.train'), 'paired fit module is missing'
    from outcome_poc import train
    return train


def rows():
    ranked = [replace(d, title=f'Invented {d.rank}') for d in packet()]
    return [PairedActionRow(f't{i}', question, ranked,
            dict(zip([f['name'] for f in feature_schema()['features']], map(float, build_features(question, ranked)))),
            f's{i}', f'f{i}', small, full, small, full, [f'es{i}'], [f'ef{i}'], 1., 3., 'ok', 'ok')
            for i, (question, small, full) in enumerate([('Who?', 1, 0), ('When?', 0, 0), ('Is it?', 0, 1)] * 8)]


def gold(values):
    return {r.task_id: GoldRecord(r.task_id, 'x', [('Invented 0', 0), ('Invented 2', 1)]) for r in values}


def test_signed_targets_failures_zero_and_infrastructure_blocks_fit():
    module = training()
    values = rows()
    assert module.outcome_targets(values).tolist()[:3] == [-1, 0, 1]
    failed = replace(values[0], small_status='parse_error', small_joint_em=0, small_answer_em=0)
    assert module.outcome_targets([failed]).tolist() == [0]
    with pytest.raises(ValueError, match='semantic'):
        module.outcome_targets([replace(failed, small_joint_em=1)])
    with pytest.raises(ValueError, match='infrastructure'):
        module.outcome_targets([replace(values[0], full_status='infra_error')])
    with pytest.raises(ValueError): module.outcome_targets([values[0], values[0]])


def test_proxy_uses_fit_gold_support_missing_from_first_two_only():
    module = training()
    values = rows()[:3]
    records = gold(values)
    records['t0'] = GoldRecord('t0', 'unused', [('Invented 0', 0), ('Invented 1', 1)])
    assert module.proxy_targets(values, records).tolist() == [0, 1, 1]
    with pytest.raises(ValueError, match='fit'):
        module.fit_gates(values, {**records, 'tune': GoldRecord('tune','x',[])}, None)


def test_fit_artifacts_lock_families_fit_stats_thresholds_and_checksums(tmp_path):
    module = training()
    values = rows()
    fitted = module.fit_gates(values, gold(values), tmp_path)
    assert set(fitted['models']) == {'PRE-OUTCOME-GBM', 'PRE-RF', 'QUERY-ONLY', 'PROXY-LABEL', 'SHUFFLED-LABEL-GBM', *[f'PRE-LINEAR-{a}' for a in (.1, 1, 10, 100)]}
    manifest = fitted['models']['PRE-OUTCOME-GBM']
    model = module.load_gate(manifest)
    params = model.get_params()
    assert {k: params[k] for k in ('loss','n_estimators','learning_rate','max_depth','min_samples_leaf','subsample','random_state')} == dict(loss='squared_error',n_estimators=100,learning_rate=.1,max_depth=3,min_samples_leaf=8,subsample=.8,random_state=1729)
    rf = module.load_gate(fitted['models']['PRE-RF'])
    assert (rf.n_estimators,rf.min_samples_leaf,rf.max_features,rf.random_state) == (300,8,1.,1729)
    assert module.load_gate(fitted['models']['QUERY-ONLY']).n_features_in_ == 7
    ridge = module.load_gate(fitted['models']['PRE-LINEAR-1'])
    matrix = module.feature_matrix(values)
    np.testing.assert_allclose(ridge.mean_, matrix.mean(axis=0))
    assert ridge.scale_[35] == 1.
    assert sorted(fitted['shuffled_targets']) == sorted(module.outcome_targets(values).tolist())
    assert manifest['fit_ids'] == [r.task_id for r in values]
    assert manifest['feature_schema_hash'] == '465358cb6034137494dfd41815a7edf239d234579e9a1686cb4204ee02f2f6a3'
    assert len(manifest['training_predictions']) == 24
    assert -1 <= min(manifest['training_predictions']) <= max(manifest['training_predictions']) <= 1
    path = tmp_path / manifest['artifact_file']
    path.write_bytes(path.read_bytes() + b'corruption')
    with pytest.raises(ValueError, match='checksum'): module.load_gate(manifest)


def test_unbound_or_changed_features_and_external_model_are_rejected(tmp_path):
    module = training()
    with pytest.raises(ValueError, match='features'):
        module.feature_matrix([replace(rows()[0], features={'wrong': 1.})])
    with pytest.raises(ValueError): module.load_gate({'artifact_path': '/tmp/external.pkl'})


def test_raw_collection_closes_before_separate_scored_merge(tmp_path):
    assert importlib.util.find_spec('outcome_poc.collection'), 'annotation-free collection module is missing'
    from outcome_poc.collection import collect_raw_pairs
    from serving_helpers import fixture_runtime
    from outcome_poc import scoring
    from types import SimpleNamespace
    from outcome_poc.storage import append_jsonl
    runtime, job, _ = fixture_runtime(tmp_path/'fixture')
    task = replace(job['task'], split='fit')
    root = tmp_path/'run'
    collect_raw_pairs([task], runtime, {'run_dir':str(root), 'assigned_ids':['task']})
    assert runtime.reader.backend.calls == 2
    assert (root/'predictions.closed.json').exists()
    module = training()
    with pytest.raises((ValueError, FileNotFoundError)):
        module.collect_pairs([task], runtime, {'run_dir':str(root), 'scores_path':str(root/'scores.jsonl')})
    documents = tmp_path/'docs.jsonl'
    for identity in task.candidate_ids: append_jsonl(documents, runtime.documents.get(identity))
    gold_path = tmp_path/'gold.jsonl'
    append_jsonl(gold_path, GoldRecord('task','blue',[(runtime.documents.get(task.candidate_ids[0]).title,0)]))
    scoring.main(SimpleNamespace(predictions=str(root/'predictions.jsonl'),run_dir=str(root), gold=str(gold_path),documents=str(documents),output=str(root/'scores.jsonl')))
    paired = module.collect_pairs([task], runtime, {'run_dir':str(root), 'scores_path':str(root/'scores.jsonl')})
    assert len(paired) == 1 and paired[0].small_joint_em == 1
    assert paired[0].full_joint_em == 1
    assert runtime.reader.backend.calls == 2


def test_collection_rejects_annotation_configuration_and_infrastructure(tmp_path):
    from outcome_poc.collection import collect_raw_pairs
    from serving_helpers import fixture_runtime
    runtime, job, _ = fixture_runtime(tmp_path, ['INFRA'])
    with pytest.raises(ValueError, match='annotation'):
        collect_raw_pairs([job['task']], runtime, {'gold':'private','run_dir':str(tmp_path/'bad'),'assigned_ids':['task']})
    with pytest.raises(ValueError, match='infrastructure'):
        collect_raw_pairs([job['task']], runtime, {'run_dir':str(tmp_path/'run'),'assigned_ids':['task']})
    assert not (tmp_path/'run/predictions.closed.json').exists()
    assert runtime.reader.backend.calls == 1


def test_fit_commands_route_collection_without_scorer_or_gold_arguments():
    import subprocess
    import sys
    for command in ('collect','fit'):
        result = subprocess.run([sys.executable,'-m','outcome_poc',command,'--help'], capture_output=True,text=True)
        assert result.returncode == 0
        assert '--config' in result.stdout and '--gold' not in result.stdout


def test_scorer_receipt_seals_outcomes_against_post_scoring_edits(tmp_path):
    from outcome_poc.collection import collect_raw_pairs
    from outcome_poc import scoring
    from outcome_poc.storage import append_jsonl
    from serving_helpers import fixture_runtime
    from types import SimpleNamespace
    runtime, job, _ = fixture_runtime(tmp_path)
    root = tmp_path/'run'
    collect_raw_pairs([job['task']],runtime,{'run_dir':str(root),'assigned_ids':['task']})
    documents, gold_path = tmp_path/'docs.jsonl', tmp_path/'gold.jsonl'
    for identity in job['task'].candidate_ids: append_jsonl(documents,runtime.documents.get(identity))
    append_jsonl(gold_path,GoldRecord('task','blue',[(runtime.documents.get(job['task'].candidate_ids[0]).title,0)]))
    path = root/'scores.jsonl'
    scoring.main(SimpleNamespace(predictions=str(root/'predictions.jsonl'), run_dir=str(root),gold=str(gold_path),documents=str(documents),output=str(path)))
    items = [json.loads(line) for line in path.read_text().splitlines()]
    items[0]['joint_em'] = 0
    path.write_text(''.join(json.dumps(item)+'\n' for item in items))
    with pytest.raises(ValueError,match='scorer receipt'):
        training().collect_pairs([job['task']],None,{'run_dir':str(root),'scores_path':str(path)})


def test_bound_paid_draft_features_use_character_length_and_contract_valid_abstention():
    module = training()
    assert hasattr(module,'paid_draft_inputs'), 'paid-draft fit input builder missing'
    features = module.paid_draft_inputs({'raw_output':'abcde', 'answer':'  ', 'status':'abstain',
                                       'citations':[{'doc_id':'d0','sentence_index':0}]*2})
    np.testing.assert_allclose(features,[1.791759469228055,1.,1.,1.])
    invalid = module.paid_draft_inputs({'raw_output':'x', 'answer':'wrong', 'status':'invalid_citation',
                                      'citations':[{'doc_id':'d0','sentence_index':0}]})
    assert invalid[1:] == [0.,0.,0.]


def test_training_gold_loader_rejects_nonfit_labels_and_requires_exact_ids(tmp_path):
    module = training()
    assert hasattr(module,'load_fit_gold'), 'fit-only gold loader missing'
    from outcome_poc.storage import append_jsonl
    path = tmp_path/'fit-gold.jsonl'
    append_jsonl(path,GoldRecord('fit','x',[('d0',0)]))
    assert set(module.load_fit_gold(path,['fit'])) == {'fit'}
    with pytest.raises(ValueError,match='fit'): module.load_fit_gold(path,['missing'])
    append_jsonl(path,GoldRecord('tune','poison',[]))
    with pytest.raises(ValueError,match='fit'): module.load_fit_gold(path,['fit'])


def test_gate_rejects_external_pickle_constructor_even_with_forged_checksum(tmp_path):
    import pickle
    import hashlib
    module = training()
    fitted = module.fit_gates(rows(),gold(rows()),tmp_path)
    manifest = fitted['models']['PRE-OUTCOME-GBM']
    class External:
        def __reduce__(self): return (eval, ('123',))
    payload = pickle.dumps(External())
    (tmp_path/manifest['artifact_file']).write_bytes(payload)
    manifest['artifact_sha256'] = hashlib.sha256(payload).hexdigest()
    (tmp_path/'fit-origin.json').write_text(json.dumps(fitted))
    with pytest.raises(ValueError,match='external'):
        module.load_gate(manifest)


def test_resolved_estimator_config_rejects_default_or_spec_drift():
    module = training()
    assert hasattr(module,'validate_estimator_config'), 'resolved defaults validator missing'
    settings = json.loads(open('configs/development.json').read())['training']['estimators']
    module.validate_estimator_config(settings)
    settings['rf']['max_features'] = 'sqrt'
    with pytest.raises(ValueError,match='prespecified'): module.validate_estimator_config(settings)


def test_scored_merge_binds_exact_question_even_when_feature_values_match(tmp_path):
    from outcome_poc.collection import collect_raw_pairs
    from outcome_poc import scoring
    from outcome_poc.storage import append_jsonl
    from serving_helpers import fixture_runtime
    from types import SimpleNamespace
    runtime, job, _ = fixture_runtime(tmp_path)
    root = tmp_path/'run'
    collect_raw_pairs([job['task']],runtime,{'run_dir':str(root),'assigned_ids':['task']})
    documents, gold_path = tmp_path/'docs.jsonl', tmp_path/'gold.jsonl'
    for identity in job['task'].candidate_ids: append_jsonl(documents,runtime.documents.get(identity))
    append_jsonl(gold_path,GoldRecord('task','blue',[(runtime.documents.get(job['task'].candidate_ids[0]).title,0)]))
    scoring.main(SimpleNamespace(predictions=str(root/'predictions.jsonl'),run_dir=str(root),gold=str(gold_path),documents=str(documents),output=str(root/'scores.jsonl')))
    with pytest.raises(ValueError,match='bound task'):
        training().collect_pairs([replace(job['task'],question='Color!')],None,{'run_dir':str(root),'scores_path':str(root/'scores.jsonl')})

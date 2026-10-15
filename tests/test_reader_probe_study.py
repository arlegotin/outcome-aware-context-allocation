"""Authored preflight records only; no benchmark or model inputs."""
import json
from pathlib import Path
import pytest
from outcome_poc.storage import atomic_json
from outcome_poc.reader_probe import profile


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    from outcome_poc.reader_probe import study
    checkout = tmp_path/'checkout'
    checkout.mkdir()
    (checkout/'requirements.lock').write_text('authored lock')
    (checkout/'data/raw').mkdir(parents=True)
    (checkout/'data/raw/probe').write_text('authored denied bytes')
    (checkout/'artifacts/analysis').mkdir(parents=True)
    (checkout/'artifacts/analysis/probe').write_text('authored outcome sentinel')
    config = checkout/'config.json'
    config.write_bytes(Path('configs/reader-capability-preflight.json').read_bytes())
    manifest = checkout/'assets.json'
    atomic_json(manifest, {'assets': {'reader': {'local_path':str(tmp_path/'assets'),
        'revision':profile.READER['revision'], 'snapshot_hash':'a'*64}}})
    monkeypatch.setattr(study, 'CHECKOUT', checkout)
    monkeypatch.setattr(study, 'verify_manifest', lambda *args: None)
    root = checkout/'artifacts/runs/new'
    study.prepare(root, config, manifest)
    return root


def test_prepare_seals_exact_calls_and_assets_stay_external(prepared):
    from outcome_poc.reader_probe import study
    plan = study.verify(prepared)
    assert len(plan['calls']) == len({c['call_id'] for c in plan['calls']}) == 3
    assert [c['repetition'] for c in plan['calls']] == [1,2,1]
    assert [c['shape'] for c in plan['calls']] == ['short','short','long']
    assert all(c['role']=='answer' for c in plan['calls'])
    assert not list((prepared/'source').rglob('*.safetensors'))
    assert 'enable_thinking' in json.dumps(plan)


@pytest.mark.parametrize('name', ['config.json','assets.json','requirements.lock','native.sb','source/src/outcome_poc/reader_probe/profile.py'])
def test_changed_sealed_file_rejected(prepared,name):
    from outcome_poc.reader_probe import study
    path=prepared/name
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError):study.verify(prepared)


def test_long_builder_keeps_complete_sentences_and_actual_tokens():
    from outcome_poc.reader_probe.study import build_prompt, ANSWER_SENTENCE
    from test_reader_probe_runtime import Tokenizer
    short=build_prompt(Tokenizer(),'short')
    long=build_prompt(Tokenizer(),'long')
    assert 7800 <= len(long['prompt_token_ids']) <= 7936
    assert len(long['prompt_token_ids'])+256 <= 8192
    assert long['document']['sentences'][0] == ANSWER_SENTENCE
    assert all(s.endswith('.') for s in long['document']['sentences'])
    assert short == build_prompt(Tokenizer(),'short')


def test_existing_manifest_inside_new_root_is_not_overwritten(tmp_path,monkeypatch):
    from outcome_poc.reader_probe import study
    checkout=tmp_path/'checkout';checkout.mkdir()
    (checkout/'requirements.lock').write_text('authored lock')
    (checkout/'data/raw').mkdir(parents=True)
    (checkout/'data/raw/probe').write_text('authored denial')
    config=checkout/'config.json'
    config.write_bytes(Path('configs/reader-capability-preflight.json').read_bytes())
    root=checkout/'artifacts/runs/new';root.mkdir(parents=True)
    path=root/'assets.json'
    atomic_json(path,{'assets':{'reader':{'local_path':str(tmp_path/'external-assets')}}})
    before=path.read_bytes()
    monkeypatch.setattr(study,'CHECKOUT',checkout)
    monkeypatch.setattr(study,'verify_manifest',lambda *args:None)
    plan=study.prepare(root,config,path)
    assert path.read_bytes()==before
    assert study.prepare(root,config,path)==plan


def test_extra_bytecode_in_snapshot_is_rejected(prepared):
    from outcome_poc.reader_probe import study
    path=prepared/'source/src/outcome_poc/__pycache__/unexpected.pyc'
    path.parent.mkdir()
    path.write_bytes(b'authored unexpected cached code')
    with pytest.raises(ValueError,match='source'):
        study.verify(prepared)

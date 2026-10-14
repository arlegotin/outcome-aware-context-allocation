import copy
import hashlib
import json

from outcome_poc.storage import read_jsonl
from test_data import prepare_rows


def test_normalization_groups_nfc_case_and_whitespace(tmp_path, raw_hotpot):
    from outcome_poc.data import normalize_question
    assert normalize_question('  CAFÉ\t lantern\n') == 'café lantern'
    assert normalize_question('Cafe\u0301 LANTERN') == 'café lantern'
    one, two = copy.deepcopy(raw_hotpot), copy.deepcopy(raw_hotpot)
    one.update(_id='z', question='CAFÉ  lantern')
    two.update(_id='a', question='cafe\u0301\tLANTERN')
    output, result = prepare_rows(tmp_path, [one, two])
    assert result['counts']['training_groups'] == 1
    ledger = list(read_jsonl(output / 'duplicate-membership.jsonl'))
    assert ledger[0]['representative_id'] == 'a'
    assert ledger[0]['member_ids'] == ['a', 'z']


def test_dev_duplicate_with_other_id_removes_entire_training_group(tmp_path, raw_hotpot):
    train = [copy.deepcopy(raw_hotpot) for _ in range(2)]
    train[0]['_id'], train[1]['_id'] = 'train-a', 'train-z'
    dev = copy.deepcopy(raw_hotpot)
    dev.update(_id='dev-new-id', question='  WHICH lantern GLOWS? ')
    output, result = prepare_rows(tmp_path, train, [dev])
    assert result['counts']['training_groups'] == 0
    assert result['counts']['protected_population'] == 1
    assert result['counts']['removed_training_rows'] == 2
    assert result['counts']['exact_question_overlap_after_removal'] == 0
    assert {r['task_id'] for r in read_jsonl(output / 'exclusions.jsonl')} == {'train-a', 'train-z'}


def test_reservations_and_nested_extensions_stay_disjoint_and_order_independent(tmp_path, raw_hotpot):
    from outcome_poc.data import load_tasks
    train = []
    for index in range(900):
        row = copy.deepcopy(raw_hotpot)
        row.update(_id=f'train-{index:04}', question=f'Which invented constellation {index}?')
        train.append(row)
    dev = copy.deepcopy(raw_hotpot)
    dev['_id'] = 'protected'
    output, result = prepare_rows(tmp_path / 'a', train, [dev])
    _, reversed_result = prepare_rows(tmp_path / 'b', list(reversed(train)), [dev])
    assert result['reservations'] == reversed_result['reservations']
    ordered = sorted(train, key=lambda row: (
        hashlib.sha256(json.dumps([20261014, row['question'].lower()],
                                 ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        row['question'].lower()))
    assert result['reservations']['pilot'] == [row['_id'] for row in ordered[:64]]
    assert result['reservations']['tune'] == [row['_id'] for row in ordered[64:192]]
    assert result['reservations']['fit'] == [row['_id'] for row in ordered[192:448]]
    reserves = result['reservations']
    assert len(reserves['pilot']) == 64
    assert len(reserves['tune']) == 128
    assert len(reserves['fit']) == 256
    assert len(reserves['fit_extension']) == 452
    assert len(load_tasks(output / 'tasks.jsonl', 'pilot')) == 32
    assert len(load_tasks(output / 'tasks.jsonl', 'fit')) == 256
    prefix = reserves['fit_prefixes']['512']
    assert prefix[:256] == reserves['fit']
    assert len(prefix) == 512
    assert not set(prefix) & set(reserves['tune'] + reserves['pilot'] + reserves['protected'])
    assert not set(reserves['pilot'][:32]) & set(reserves['pilot'][32:])


def test_protected_duplicates_retain_minimum_id_and_all_members(tmp_path, raw_hotpot):
    one, two = copy.deepcopy(raw_hotpot), copy.deepcopy(raw_hotpot)
    one['_id'], two['_id'] = 'dev-z', 'dev-a'
    output, result = prepare_rows(tmp_path, [], [one, two])
    assert result['counts']['protected_population'] == 1
    assert result['reservations']['protected'] == ['dev-a']
    assert list(read_jsonl(output / 'duplicate-membership.jsonl'))[0]['member_ids'] == ['dev-a', 'dev-z']

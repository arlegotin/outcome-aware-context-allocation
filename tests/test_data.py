import copy
import json

import pytest

from outcome_poc.storage import read_jsonl


def prepare_rows(tmp_path, train, dev=()):
    from outcome_poc.data import prepare
    tmp_path.mkdir(parents=True, exist_ok=True)
    train_path, dev_path = tmp_path / 'train.json', tmp_path / 'dev.json'
    train_path.write_text(json.dumps(train), encoding='utf-8')
    dev_path.write_text(json.dumps(dev), encoding='utf-8')
    output = tmp_path / 'prepared'
    return output, prepare(train_path, dev_path, output)


def test_conversion_keeps_sentence_indices_and_content_ids(tmp_path, raw_hotpot):
    from outcome_poc.data import DocumentStore, load_tasks, audit_data
    first, report = prepare_rows(tmp_path / 'a', [raw_hotpot])
    other = copy.deepcopy(raw_hotpot)
    other['context'].reverse()
    second, _ = prepare_rows(tmp_path / 'b', [other])
    tasks = load_tasks(first / 'tasks.jsonl', 'pilot')
    assert len(tasks) == 1
    assert set(tasks[0].candidate_ids) == set(load_tasks(second / 'tasks.jsonl', 'pilot')[0].candidate_ids)
    document = DocumentStore(first / 'documents.jsonl').get(tasks[0].candidate_ids[0])
    assert document.sentences == ['Lantern 0 rests.', 'Lantern 0 glows.']
    gold = list(read_jsonl(first / 'gold' / 'gold.jsonl'))
    assert gold[0]['supporting_facts'] == [['Invented lantern 0', 1], ['Invented lantern 1', 0]]
    assert audit_data(first)['status'] == 'ok'
    assert report['counts']['protected_population'] == 0


def test_different_text_same_title_is_valid_when_not_support_ambiguous(tmp_path, raw_hotpot):
    from outcome_poc.data import DocumentStore, load_tasks
    raw_hotpot['context'][9][0] = raw_hotpot['context'][8][0]
    output, _ = prepare_rows(tmp_path, [raw_hotpot])
    task = load_tasks(output / 'tasks.jsonl', 'pilot')[0]
    store = DocumentStore(output / 'documents.jsonl')
    assert task.candidate_ids[8] != task.candidate_ids[9]
    assert store.get(task.candidate_ids[8]).title == store.get(task.candidate_ids[9]).title


@pytest.mark.parametrize('mutation,reason', [
    ('question', 'invalid_question'), ('unicode', 'invalid_unicode'),
    ('answer', 'invalid_answer'), ('packet', 'paragraph_count'),
    ('duplicate_content', 'duplicate_packet_content'),
    ('ambiguous', 'ambiguous_support_title'), ('index', 'invalid_support_reference'),
    ('bool_index', 'invalid_support_reference'), ('title', 'invalid_context'),
    ('sentences', 'invalid_context'), ('id', 'invalid_id'), ('empty_title', 'invalid_context'),
])
def test_rejections_record_ids_and_reasons(tmp_path, raw_hotpot, mutation, reason):
    if mutation == 'question': raw_hotpot['question'] = 2
    if mutation == 'unicode': raw_hotpot['question'] = '\ud800'
    if mutation == 'answer': raw_hotpot['answer'] = None
    if mutation == 'packet': raw_hotpot['context'].pop()
    if mutation == 'duplicate_content': raw_hotpot['context'][9] = raw_hotpot['context'][0]
    if mutation == 'ambiguous': raw_hotpot['context'][9][0] = raw_hotpot['context'][0][0]
    if mutation == 'index': raw_hotpot['supporting_facts'][0][1] = 2
    if mutation == 'bool_index': raw_hotpot['supporting_facts'][0][1] = True
    if mutation == 'title': raw_hotpot['context'][0][0] = 2
    if mutation == 'empty_title': raw_hotpot['context'][9][0] = ''
    if mutation == 'sentences': raw_hotpot['context'][0][1] = ['okay', None]
    if mutation == 'id': raw_hotpot['_id'] = ''
    output, result = prepare_rows(tmp_path, [raw_hotpot])
    rows = list(read_jsonl(output / 'exclusions.jsonl'))
    assert rows[0]['reason'] == reason
    assert rows[0]['task_id'] == raw_hotpot['_id']
    assert result['counts']['validated_train_rows'] == 0


def test_duplicate_ids_reject_all_occurrences_even_invalid_one(tmp_path, raw_hotpot):
    invalid = copy.deepcopy(raw_hotpot)
    invalid['question'] = None
    output, result = prepare_rows(tmp_path, [raw_hotpot], [invalid])
    assert result['counts']['protected_population'] == 0
    assert result['counts']['training_groups'] == 0
    assert sum(r['reason'] == 'duplicate_id' for r in read_jsonl(output / 'exclusions.jsonl')) == 2


@pytest.mark.parametrize('payload', ['{}', '[{},]', '[{}] trailing', '[', '[{"a":1,"a":2}]'])
def test_malformed_array_fails_without_publishing_manifest(tmp_path, payload):
    from outcome_poc.data import prepare
    source = tmp_path / 'bad.json'
    source.write_text(payload)
    dev = tmp_path / 'dev.json'
    dev.write_text('[]')
    with pytest.raises(ValueError):
        prepare(source, dev, tmp_path / 'prepared')
    assert not (tmp_path / 'prepared' / 'manifest.json').exists()


def test_runtime_loaders_refuse_annotation_fields(tmp_path, raw_hotpot):
    from outcome_poc.data import DocumentStore, load_tasks
    output, _ = prepare_rows(tmp_path, [raw_hotpot])
    row = list(read_jsonl(output / 'tasks.jsonl'))[0]
    row['answer'] = 'leaked'
    (output / 'tasks.jsonl').write_text(json.dumps(row) + '\n')
    with pytest.raises(ValueError, match='fields'):
        load_tasks(output / 'tasks.jsonl', 'pilot')
    row = list(read_jsonl(output / 'documents.jsonl'))[0]
    row['support_pairs'] = []
    (output / 'documents.jsonl').write_text(json.dumps(row) + '\n')
    with pytest.raises(ValueError, match='fields'):
        DocumentStore(output / 'documents.jsonl')


def test_audit_detects_corrupt_files(tmp_path, raw_hotpot):
    from outcome_poc.data import audit_data
    output, _ = prepare_rows(tmp_path, [raw_hotpot])
    with (output / 'tasks.jsonl').open('a') as stream:
        stream.write('{}\n')
    with pytest.raises(ValueError, match='hash'):
        audit_data(output)


def test_streaming_array_handles_records_and_separators_across_chunks(raw_hotpot, tmp_path):
    from outcome_poc.data import _raw_rows
    source = tmp_path / 'raw.json'
    source.write_text(json.dumps([raw_hotpot, raw_hotpot]) + ' \n')
    assert list(_raw_rows(source, chunk_size=7)) == [raw_hotpot, raw_hotpot]


def test_cli_prepares_and_audits_configured_paths(tmp_path, raw_hotpot, capsys):
    from outcome_poc.__main__ import main
    train, dev = tmp_path / 'train.json', tmp_path / 'dev.json'
    train.write_text(json.dumps([raw_hotpot]))
    dev.write_text('[]')
    output = tmp_path / 'configured-output'
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'preparation': {'train_path': str(train), 'dev_path': str(dev),
                                                 'output_dir': str(output),
                                                 'asset_manifest': str(tmp_path / 'absent.json')}}))
    assert main(['prepare', '--config', str(config)]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'prepared'
    assert main(['audit-data', '--config', str(config)]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'ok'


def test_runtime_loader_rejects_duplicate_json_keys(tmp_path, raw_hotpot):
    from outcome_poc.data import DocumentStore
    output, _ = prepare_rows(tmp_path, [raw_hotpot])
    path = output / 'documents.jsonl'
    text = path.read_text()
    path.write_text(text.replace('"title":', '"title":"hidden","title":', 1))
    with pytest.raises(ValueError, match='duplicate'):
        DocumentStore(path)

import json
import subprocess
import sys


COMMANDS = ["discover", "assets", "smoke", "prepare", "index", "audit-data",
            "validate-harness", "pilot", "collect", "fit", "tune", "freeze",
            "plan", "run", "score", "ablate", "transfer", "reproduce", "report"]


def test_module_help_lists_every_proposed_command_without_heavy_imports():
    script = '''
import contextlib, io, json, runpy, sys
sys.argv = ["outcome_poc", "--help"]
output = io.StringIO()
with contextlib.redirect_stdout(output):
    try:
        runpy.run_module("outcome_poc", run_name="__main__")
    except SystemExit as error:
        assert error.code == 0
print(json.dumps({"help": output.getvalue(), "modules": list(sys.modules)}))
'''
    completed = subprocess.run([sys.executable, "-c", script],
                               capture_output=True, text=True, check=True)
    result = json.loads(completed.stdout)
    for command in COMMANDS:
        assert command in result["help"]
    assert not any(name == "mlx" or name.startswith("mlx.") or
                   name == "outcome_poc.scoring" for name in result["modules"])


def test_unimplemented_command_returns_clear_unavailable_stage_error():
    completed = subprocess.run([sys.executable, "-m", "outcome_poc", "run"],
                               capture_output=True, text=True)
    assert completed.returncode != 0
    assert "unavailable" in completed.stderr.lower()
    assert "run" in completed.stderr


def test_serving_command_does_not_offer_gold_argument():
    completed = subprocess.run([sys.executable, "-m", "outcome_poc", "run", "--help"],
                               capture_output=True, text=True, check=True)
    assert "--gold" not in completed.stdout



def test_index_cli_does_not_advertise_or_accept_unscheduled_protected_population(tmp_path):
    help_result = subprocess.run([sys.executable, '-m', 'outcome_poc', 'index', '--help'],
                                 text=True, capture_output=True, check=True)
    assert 'protected' not in help_result.stdout
    result = subprocess.run([sys.executable, '-m', 'outcome_poc', 'index', '--config',
                             str(tmp_path / 'missing.json'), '--split', 'protected'],
                            text=True, capture_output=True)
    assert result.returncode == 2
    assert 'invalid choice' in result.stderr


def test_reader_cli_has_pilot_only_inputs_and_no_gold_argument():
    result = subprocess.run([sys.executable, '-m', 'outcome_poc', 'reader', '--help'],
                            text=True, capture_output=True)
    assert result.returncode == 0 and '--evidence-budget' in result.stdout
    assert '--gold' not in result.stdout and '--split' not in result.stdout


def test_score_cli_requires_closed_predictions_before_reading_gold(tmp_path):
    from outcome_poc.storage import append_jsonl, atomic_json
    from outcome_poc.schemas import Prediction, GoldRecord
    from retrieval_helpers import document, store
    import hashlib
    doc = document('Original lamp', ['A blue lamp.'])
    documents = store(tmp_path, [doc])
    predictions, gold, output = tmp_path / 'predictions.jsonl', tmp_path / 'gold.jsonl', tmp_path / 'scores.jsonl'
    append_jsonl(predictions, Prediction('run', 'task', 'fixed-ten', 'protocol', 'job', 1, 0,
                 [doc.doc_id], 'raw', 'blue', [(doc.doc_id, 0)], 'ok', 'r', 'p', 'd', 1., 10, 10, 1, ['event']))
    args = [sys.executable, '-m', 'outcome_poc', 'score', '--predictions', str(predictions),
            '--gold', str(gold), '--documents', str(documents.path), '--output', str(output)]
    unclosed = subprocess.run(args, text=True, capture_output=True)
    assert unclosed.returncode != 0 and 'closed prediction' in unclosed.stderr
    append_jsonl(gold, GoldRecord('task', 'blue', [('Original lamp', 0)]))
    atomic_json(predictions.with_suffix('.closed.json'), {'prediction_sha256': hashlib.sha256(predictions.read_bytes()).hexdigest(),
                                                       'record_count': 1})
    closed = subprocess.run(args, text=True, capture_output=True)
    assert closed.returncode == 0, closed.stderr
    result = json.loads(output.read_text())
    assert result['joint_em'] == 1 and result['answer_f1'] == 1

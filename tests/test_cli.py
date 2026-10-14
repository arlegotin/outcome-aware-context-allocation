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

"""Command registry; model and scoring modules are imported only on dispatch."""

import argparse
import importlib


# Future stages implement main(args); help remains available before their dependencies.
COMMAND_MODULES = {
    "discover": "environment", "assets": "assets", "smoke": "generation",
    "prepare": "data", "index": "retrieval", "audit-data": "data",
    "validate-harness": "validation", "pilot": "runner", "collect": "runner",
    "fit": "train", "tune": "select", "freeze": "protocol", "plan": "protocol",
    "run": "runner", "score": "scoring", "ablate": "robustness",
    "transfer": "robustness", "reproduce": "report", "report": "report",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local outcome-aware context allocation experiment")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMAND_MODULES:
        subparsers.add_parser(command, help=f"{command} experiment stage")
    args = parser.parse_args(argv)
    module_name = f"outcome_poc.{COMMAND_MODULES[args.command]}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name != module_name:
            raise
        parser.error(f"stage unavailable: '{args.command}' is not implemented")
    handler = getattr(module, "main", None)
    if handler is None:
        parser.error(f"stage unavailable: '{args.command}' is not implemented")
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

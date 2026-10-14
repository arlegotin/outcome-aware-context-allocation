"""Command registry; model and scoring modules are imported only on dispatch."""

import argparse
import importlib


# Future stages implement main(args); help remains available before their dependencies.
COMMAND_MODULES = {
    "discover": "environment", "assets": "assets", "smoke": "generation",
    "prepare": "data", "index": "retrieval", "audit-data": "data", "reader": "generation",
    "validate-harness": "runner", "pilot": "pilot", "collect": "runner",
    "fit": "train", "tune": "select", "freeze": "protocol", "plan": "protocol",
    "run": "runner", "score": "scoring", "ablate": "robustness",
    "transfer": "robustness", "reproduce": "report", "report": "report",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local outcome-aware context allocation experiment")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMAND_MODULES:
        stage_parser = subparsers.add_parser(command, help=f"{command} experiment stage")
        if command in {"discover", "assets", "smoke", "prepare", "audit-data", "index", "reader", "validate-harness", "pilot"}:
            stage_parser.add_argument("--config", required=True, help="local JSON setup configuration")
        if command == "index":
            stage_parser.add_argument("--split", required=True, choices=["pilot", "fit", "tune"], help="scheduled active partition")
        if command == "reader":
            stage_parser.add_argument('--task-id', help='pilot task ID; default is first pilot task')
            stage_parser.add_argument('--evidence-budget', type=int, choices=[2, 10], default=10)
            stage_parser.add_argument('--output', required=True, help='private diagnostic directory')
        if command == "score":
            stage_parser.add_argument('--run-dir', help='complete durable run ledger for experimental accounting')
            for argument in ('predictions', 'gold', 'documents', 'output'):
                stage_parser.add_argument(f'--{argument}', required=True)
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

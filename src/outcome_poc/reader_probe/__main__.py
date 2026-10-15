"""Explicit asset acquisition entry point; inference is a separate operation."""
import argparse
import json
from pathlib import Path

from .assets import acquire


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest='command', required=True)
    command = subcommands.add_parser('assets')
    command.add_argument('--config', type=Path, required=True)
    command.add_argument('--asset-root', type=Path, required=True)
    command.add_argument('--manifest', type=Path, required=True)
    for name in ('prepare', 'verify', 'run', '_serve'):
        command = subcommands.add_parser(name)
        command.add_argument('--root', type=Path, required=True)
        if name == 'prepare':
            command.add_argument('--config', type=Path, required=True)
            command.add_argument('--assets', type=Path, required=True)
    args = parser.parse_args()
    if args.command != 'assets':
        from . import study, runtime
        if args.command == 'prepare': result = study.prepare(args.root, args.config, args.assets)
        elif args.command == 'verify': result = study.verify(args.root)
        elif args.command == 'run': result = runtime.launch(args.root)
        else:
            runtime.native_entry(args.root)
            return
        print(json.dumps(result, sort_keys=True))
        return
    manifest = acquire(args.config, args.asset_root, args.manifest)
    print(json.dumps({'status': manifest['status'], 'manifest_hash': manifest['manifest_hash'],
                      'acquisition': manifest['acquisition']}, sort_keys=True))


if __name__ == '__main__':
    main()

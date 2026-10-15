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
    args = parser.parse_args()
    manifest = acquire(args.config, args.asset_root, args.manifest)
    print(json.dumps({'status': manifest['status'], 'manifest_hash': manifest['manifest_hash'],
                      'acquisition': manifest['acquisition']}, sort_keys=True))


if __name__ == '__main__':
    main()

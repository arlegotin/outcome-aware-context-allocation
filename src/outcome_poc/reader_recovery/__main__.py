"""Explicit new CLI; imports privileged preparation/scoring only on demand."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description='Reader recovery v1: bounded diagnosis, no automatic selection/confirmation')
    commands = parser.add_subparsers(dest='command',required=True)
    prepare = commands.add_parser('prepare',help='reserve fresh IDs and project diagnostic evidence before outcomes')
    prepare.add_argument('--config',type=Path,required=True)
    prepare.add_argument('--root',type=Path,required=True)
    prepare.add_argument('--selection-from',type=Path,help='preserve an identical pre-outcome reservation after software setup repair')
    prepare.add_argument('--deny-root',type=Path,action='append',default=[],help='additional earlier setup/annotation root to deny in both serving processes')
    validation = commands.add_parser('prepare-validation',help='freeze the single authored candidate on the prior untouched64 IDs; no resampling')
    validation.add_argument('--config',type=Path,required=True)
    validation.add_argument('--root',type=Path,required=True)
    validation.add_argument('--diagnosis-root',type=Path,required=True)
    for name in ('index','verify','score'):
        sub = commands.add_parser(name)
        sub.add_argument('--root',type=Path,required=True)
    for name in ('run','_serve'):
        sub = commands.add_parser(name,help='native diagnostic group; single attempt, no semantic retry')
        sub.add_argument('--root',type=Path,required=True)
        sub.add_argument('--group',choices=('natural','oracle'),required=True)
    args = parser.parse_args(argv)
    if args.command=='prepare-validation':
        from .validation import prepare_validation
        result = prepare_validation(args.root,args.config,args.diagnosis_root)
    elif args.command=='prepare':
        from .preparation import prepare
        result = prepare(args.root,args.config,selection_from=args.selection_from,deny_roots=args.deny_root)
        result = {'plan_hash':result['plan_hash'],'root':result['root']}
    elif args.command=='index':
        from .preparation import index
        result = index(args.root)
    elif args.command=='verify':
        from .study import verify
        plan = verify(args.root)
        result = {'plan_hash':plan['plan_hash'],'status':'verified frozen inputs; execution not implied'}
    elif args.command=='score':
        from .scoring import score
        result = score(args.root)
    else:
        from .runtime import launch,run_group
        result = (launch if args.command=='run' else run_group)(args.root,args.group)
    print(json.dumps(result,allow_nan=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())

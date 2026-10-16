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
    fresh = commands.add_parser('prepare-fresh-validation',help='NEW v2: independent metadata preparation only; scientific execution disabled')
    fresh.add_argument('--config',type=Path,required=True)
    fresh.add_argument('--root',type=Path,required=True)
    learning = commands.add_parser('prepare-learning-study',help='NEW v5: frozen fit and untouched learning-holdout acquisition')
    learning.add_argument('--config',type=Path,required=True)
    learning.add_argument('--root',type=Path,required=True)
    action = commands.add_parser('prepare-action-study',help='NEW v4: admitted-reader independent 2/5/10 development action screen')
    action.add_argument('--config',type=Path,required=True)
    action.add_argument('--root',type=Path,required=True)
    scientific = commands.add_parser('prepare-scientific',help='NEW v3: single-use frozen native reader trial through actual allocation runner')
    scientific.add_argument('--config',type=Path,required=True)
    scientific.add_argument('--root',type=Path,required=True)
    validation = commands.add_parser('prepare-validation',help='freeze the single authored candidate on the prior untouched64 IDs; no resampling')
    validation.add_argument('--config',type=Path,required=True)
    validation.add_argument('--root',type=Path,required=True)
    validation.add_argument('--diagnosis-root',type=Path,required=True)
    for name in ('index','index-bounded','verify','score'):
        sub = commands.add_parser(name)
        sub.add_argument('--root',type=Path,required=True)
    for name in ('run','_serve'):
        sub = commands.add_parser(name,help='native diagnostic group; single attempt, no semantic retry')
        sub.add_argument('--root',type=Path,required=True)
        sub.add_argument('--group',choices=('natural','oracle'),required=True)
    args = parser.parse_args(argv)
    if args.command=='prepare-learning-study':
        from .learning_preparation_v5 import prepare_learning
        result = prepare_learning(args.root,args.config)
    elif args.command=='prepare-action-study':
        from .action_preparation_v4 import prepare_action
        result = prepare_action(args.root,args.config)
    elif args.command=='prepare-scientific':
        from .preparation_v3 import prepare_scientific
        result = prepare_scientific(args.root,args.config)
    elif args.command=='prepare-fresh-validation':
        from .fresh import prepare_fresh_validation
        result = prepare_fresh_validation(args.root,args.config)
    elif args.command=='prepare-validation':
        from .validation import prepare_validation
        result = prepare_validation(args.root,args.config,args.diagnosis_root)
    elif args.command=='prepare':
        from .preparation import prepare
        result = prepare(args.root,args.config,selection_from=args.selection_from,deny_roots=args.deny_root)
        result = {'plan_hash':result['plan_hash'],'root':result['root']}
    elif args.command=='index-bounded':
        from .preparation_v3 import index_bounded
        result = index_bounded(args.root)
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

"""Lazy, stage-local CLI; privileged preparation never enters a verify process."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(description='Frozen paired reader quality comparison')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','index','verify','run','score','admit','report','_serve'):
        child=sub.add_parser(name);child.add_argument('--root',type=Path,required=True)
        if name=='prepare':child.add_argument('--config',type=Path,required=True)
        if name in {'index','verify','run','score','_serve'}:child.add_argument('--stage',choices=('development','confirmation'),required=name!='verify')
    args=parser.parse_args(argv)
    if args.command=='prepare':
        from .preparation import prepare
        plan=prepare(args.root,args.config);result={'status':'prepared','plan_hash':plan['plan_hash']}
    elif args.command=='index':
        from .preparation import index
        result=index(args.root,args.stage)
    elif args.command in {'run','_serve'}:
        from .runtime import launch,native_entry
        result=(native_entry if args.command=='_serve' else launch)(args.root,args.stage)
        if args.command=='_serve':return 0
    elif args.command in {'score','admit','report'}:
        from .scoring import score_stage,admit,report
        result=score_stage(args.root,args.stage) if args.command=='score' else (admit if args.command=='admit' else report)(args.root)
    else:
        from .study import verify
        plan=verify(args.root,stage=args.stage);result={'status':'verified','plan_hash':plan['plan_hash'],'scientific_stage':args.stage}
    print(json.dumps(result,sort_keys=True,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())

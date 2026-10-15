"""Lazy, stage-local CLI; privileged preparation never enters a verify process."""
import argparse
import json
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(description='Frozen paired reader quality comparison')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','index','verify'):
        child=sub.add_parser(name);child.add_argument('--root',type=Path,required=True)
        if name=='prepare':child.add_argument('--config',type=Path,required=True)
        if name in {'index','verify'}:child.add_argument('--stage',choices=('development','confirmation'),required=name=='index')
    args=parser.parse_args(argv)
    if args.command=='prepare':
        from .preparation import prepare
        plan=prepare(args.root,args.config);result={'status':'prepared','plan_hash':plan['plan_hash']}
    elif args.command=='index':
        from .preparation import index
        result=index(args.root,args.stage)
    else:
        from .study import verify
        plan=verify(args.root,stage=args.stage);result={'status':'verified','plan_hash':plan['plan_hash'],'scientific_stage':args.stage}
    print(json.dumps(result,sort_keys=True,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())

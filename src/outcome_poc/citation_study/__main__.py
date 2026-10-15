"""Minimal dispatch; privileged annotation modules are lazy and serving-denied."""
import os
import sys
from pathlib import Path
if os.environ.get('OUTCOME_CITATION_SERVING'):
    from .runtime import install_guard
    install_guard(Path(os.environ['OUTCOME_CITATION_SERVING']))
import argparse
import json


def main(argv=None):
    parser=argparse.ArgumentParser(description='Frozen citation-chain paired reader study')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('prepare','index','verify','run','score','admit','report','_serve'):
        child=sub.add_parser(name);child.add_argument('--root',type=Path,required=True)
        if name in {'index','run','score','_serve'}:child.add_argument('--stage',choices=('diagnosis','comparison'),required=True)
        if name=='prepare':child.add_argument('--config',type=Path,default=Path('configs/citation-chain-reader-study.json'))
    args=parser.parse_args(argv)
    if args.command=='prepare':
        from .preparation import prepare
        result=prepare(args.root,args.config);result={'plan_hash':result['plan_hash'],'status':'prepared'}
    elif args.command=='index':
        from .preparation import index
        from .runtime import stage_lock
        with stage_lock(args.root):result=index(args.root,args.stage)
    elif args.command in {'score','admit'}:
        from .scoring import score_stage,admit
        result=score_stage(args.root,args.stage) if args.command=='score' else admit(args.root)
    else:
        from .runtime import launch,native_entry,report
        if args.command=='run':result=launch(args.root,args.stage)
        elif args.command=='_serve':result=native_entry(args.root,args.stage)
        else:
            if args.command=='verify':
                from .study import verify
                from .compat import verify_index
                verify(args.root,privileged=True)
                for stage in ('diagnosis','comparison'):
                    if (args.root/'stages'/stage/'index-setup/index-seal.json').exists():verify_index(args.root/'stages'/stage/'index-setup')
            result=report(args.root)
    print(json.dumps(result,sort_keys=True,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())

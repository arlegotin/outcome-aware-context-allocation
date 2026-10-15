"""Uncapped development follow-up CLI; privileged scoring dispatch is lazy."""
import argparse
import json
import os
import sys
from pathlib import Path
from .study import STAGES, prepare, verify, read, publish, identity, verify_files

if os.environ.get('OUTCOME_FOLLOWUP_SERVING'):
    from .runtime import GoldImportGuard
    sys.meta_path.insert(0,GoldImportGuard())
    expected=Path(os.environ['OUTCOME_FOLLOWUP_SERVING'])/'source/src/outcome_poc'
    for name,module in list(sys.modules.items()):
        if name.startswith('outcome_poc') and getattr(module,'__file__',None):
            if not Path(module.__file__).resolve().is_relative_to(expected):
                raise RuntimeError(f'non-snapshot serving import: {name}')


def report(root):
    root=Path(root).resolve()
    plan=verify(root)
    result={'plan_hash':plan['plan_hash'],'planned_generations':688,'old_24h_window_applies':False,'stages':{}}
    from .runtime import selected_jobs, completion, validate_closed_stage, session_accounting
    from ..storage import read_jsonl
    def ledger(path):return list(read_jsonl(path)) if path.exists() else []
    def duration(row):return (row['stop_ns']-row['start_ns'])/1e9
    setup=ledger(root/'setup.jsonl')
    result['physical_costs']={'preparation_seconds':sum(duration(r) for r in setup if r['kind']=='preparation'),
        'index_setup_seconds':sum(duration(r) for r in setup if r['kind']=='index_setup'),
        'scoring_seconds':sum(duration(r) for r in ledger(root/'scoring-attempts.jsonl')),
        'serving_session_seconds':0.,'serving_session_lower_seconds':0.,'serving_session_upper_seconds':0.,
        'accounting_status':'complete','summing_rule':'Only disjoint preparation, index setup, resident sessions and scoring; service/load/warmup are nested diagnostics.'}
    for stage in STAGES:
        jobs=selected_jobs(root,stage)
        completed=sum(completion(root,plan,j) is not None for j in jobs)
        status={'assigned_observations':len(jobs),'terminal_observations':completed,
            'assigned_unique_questions':len({j['task_id'] for j in jobs}),
            'reserved_questions':32 if stage=='calibration' else len({j['task_id'] for j in jobs}),
            'status':'incomplete'}
        if (root/'stages'/stage/'closed.json').exists():
            validate_closed_stage(root,stage)
            status['status']='closed_unscored'
            if (root/'scores'/stage/'closed.json').exists():
                seal=read(root/'scores'/stage/'closed.json')
                if seal['plan_hash']!=plan['plan_hash']:raise ValueError('score plan mismatch')
                verify_files({str(root/'scores'/stage/n):v for n,v in seal['files'].items()})
                if seal['prediction_closure']!=identity(root/'stages'/stage/'closed.json'):
                    raise ValueError('score prediction closure mismatch')
                status.update(status='scored',summary=read(root/'scores'/stage/'summary.json'))
        stage_root=root/'stages'/stage
        sessions=session_accounting(root,stage,plan)
        status['session_accounting']=sessions
        status['session_seconds']=sessions['exact_seconds']
        physical=result['physical_costs']
        physical['serving_session_lower_seconds']+=sessions['lower_seconds']
        for key,value in (('serving_session_seconds',sessions['exact_seconds']),('serving_session_upper_seconds',sessions['upper_seconds'])):
            physical[key]=physical[key]+value if physical[key] is not None and value is not None else None
        if sessions['status']!='complete':physical['accounting_status']='unresolved'
        status['authored_warmup_calls']=len(list(stage_root.glob('warmup-*/paid.json')))
        samples=[r for p in stage_root.glob('resources-*.jsonl') for r in ledger(p)]
        status['resources']={key:max((r[key] for r in samples if r.get(key) is not None),default=None)
            for key in ('rss_parent_bytes','rss_children_bytes','peak_mlx_bytes','swap_used_bytes')}
        status['resources'].update(sampling_seconds=2.,interpretation='RSS and MLX overlap; maxima are separate observations')
        result['stages'][stage]=status
    physical=result['physical_costs']
    base=sum(physical[k] for k in ('preparation_seconds','index_setup_seconds','scoring_seconds'))
    physical['total_seconds']=base+physical['serving_session_seconds'] if physical['accounting_status']=='complete' else None
    physical['total_lower_seconds']=base+physical['serving_session_lower_seconds']
    physical['total_upper_seconds']=base+physical['serving_session_upper_seconds'] if physical['serving_session_upper_seconds'] is not None else None
    decision=root/'headroom-decision.json'
    if decision.exists():
        result['headroom_decision']=read(decision)
        if result['headroom_decision']['decision']=='defer' and result['stages']['headroom']['terminal_observations']==0:
            result['stages']['headroom']['status']='deferred'
    unstable=physical['accounting_status']!='complete' or any(s.get('summary',{}).get('timing_health',{}).get('unstable',False) for s in result['stages'].values())
    result['overall_timing_health']={'unstable':unstable,'cost_comparisons':'unresolved' if unstable else 'development descriptive only'}
    result['interpretation']='Three measured actions; support-doc oracle is annotation-assisted diagnosis. No deployable controller or quality-preservation claim.'
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='Frozen fresh development reader diagnosis; ignored local outputs only.')
    sub=parser.add_subparsers(dest='command',required=True)
    for name,description in [('prepare','Create a fresh fail-if-exists root; freeze selection before projecting support IDs.'),
       ('index','Build a fresh no-reuse selected-document index.'),('run','Launch native sandboxed resident serving.'),
       ('score','Score a completely closed stage in a separate Gold-enabled process.'),
       ('report','Print aggregate-only status and scored summaries; incomplete schedules stay unscored.'),
       ('verify','Verify sealed source/input/output identities.'),
       ('decide-headroom','Record the explicit post-diagnosis admit/defer decision.'),('_serve',argparse.SUPPRESS)]:
        child=sub.add_parser(name,help=description)
        child.add_argument('--root',type=Path,required=True,help='New study run root (no historical outputs).')
        if name=='prepare':child.add_argument('--config',type=Path,default=Path('configs/followup-reader-headroom.json'))
        if name in {'run','score','_serve'}:child.add_argument('--stage',choices=STAGES,required=True)
        if name=='decide-headroom':
            child.add_argument('--decision',choices=('admit','defer'),required=True)
            child.add_argument('--rationale',required=True)
    args=parser.parse_args(argv)
    if args.command=='prepare':
        plan=prepare(args.root,args.config);result={'status':'prepared','plan_hash':plan['plan_hash'],'planned_generations':688}
    elif args.command=='index':
        from .runtime import stage_lock, ResourceMonitor
        from .study import build_new_index
        from .clock import continuous_ns
        from ..data_runtime import DocumentStore
        from ..retrieval import EncoderBackend
        from ..generation import offline_network
        from ..storage import append_jsonl
        root=args.root.resolve();plan=verify(root)
        with stage_lock(root):
            setup=root/'index-setup';setup.mkdir(exist_ok=False)
            start=continuous_ns()
            monitor=ResourceMonitor(root/'index-resources.jsonl');monitor.start()
            try:
                with offline_network():
                    asset=read(root/'assets.json')['assets']['encoder']
                    encoder=EncoderBackend(Path(asset['local_path']))
                    if encoder.identity!={k:asset[k] for k in ('revision','snapshot_hash')}:raise ValueError('encoder identity mismatch')
                    store=DocumentStore(root/'documents.jsonl')
                    result=build_new_index(setup,[store.get(d) for d in sorted(store.offsets)],encoder)
            except BaseException as error:
                append_jsonl(root/'setup.jsonl',{'kind':'index_setup','start_ns':start,'stop_ns':continuous_ns(),'status':'failed','error':str(error)})
                raise
            finally:monitor.stop()
            append_jsonl(root/'setup.jsonl',{'kind':'index_setup','start_ns':start,'stop_ns':continuous_ns(),'status':'ok','overlaps':'index build; never sum'})
            verify(root)
    elif args.command=='run':
        from .runtime import launch
        result=launch(args.root,args.stage)
    elif args.command=='_serve':
        from .runtime import native_entry
        result=native_entry(args.root,args.stage)
    elif args.command=='score':
        from .scoring import score_stage
        result=score_stage(args.root,args.stage)
    elif args.command=='report':result=report(args.root)
    elif args.command=='decide-headroom':
        from .runtime import validate_closed_stage
        root=args.root.resolve();plan,_=validate_closed_stage(root,'diagnosis')
        if not (root/'scores/diagnosis/closed.json').exists():raise ValueError('score complete diagnosis before deciding')
        report(root)
        if not args.rationale.strip():raise ValueError('decision rationale required')
        result={'plan_hash':plan['plan_hash'],'decision':args.decision,'rationale':args.rationale,
            'diagnosis_scores':identity(root/'scores/diagnosis/closed.json')}
        publish(root/'headroom-decision.json',result)
    else:
        plan=verify(args.root)
        if (args.root/'index-setup/index-seal.json').exists():
            from .study import verify_index
            verify_index(args.root/'index-setup')
        result=report(args.root)
        result['verified']=True
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())

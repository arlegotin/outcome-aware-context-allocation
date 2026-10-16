"""NEW read-only v4 closure/resource gate, executed BEFORE Gold scoring.

Load frozen source with PYTHONPATH. The native watchdog permits bounded cleanup
grace; this check independently enforces the stricter registered complete cap.
Output must be a new private directory outside retained source/evidence.
"""
import argparse,json,sys
from pathlib import Path
sys.dont_write_bytecode=True


def validate(root,output):
    from outcome_poc.reader_recovery.scoring import closed_records
    from outcome_poc.reader_recovery.study import read,identity,publish
    from outcome_poc.reader_probe.study import inventory
    from outcome_poc.storage import read_jsonl,content_hash
    root=Path(root).resolve(strict=True);output=Path(output).resolve();metadata=read(root/'plan.json')
    retained={root,Path(__file__).resolve().parents[1],Path(metadata['config']['historical_checkout']).resolve(),
              *(Path(p).resolve() for p in metadata['denied_paths'])}
    if any(p.is_relative_to(output) or output.is_relative_to(p) for p in retained):raise ValueError('fresh gate output overlaps retained evidence')
    if output.exists():raise ValueError('fresh gate output required')
    before=inventory(root);plan,records=closed_records(root)
    if plan['config'].get('schema_version') not in (4,5):raise ValueError('explicit v4/v5 resource gate required')
    stage=read(root/'stages/natural/closed.json');session=stage['session_accounting']
    launches=list(read_jsonl(root/'launches.jsonl'))
    if len(launches)!=1:raise ValueError('exact one native launch required')
    launch=launches[0];envelope=(launch['stop_ns']-launch['start_ns'])/1e9
    count=len(list((root/'jobs').glob('*/allocation/jobs/*/attempt-*/paid-*.started.json')))
    recorded=sum(payload['calls'] for _,payload,_ in records)
    # The frozen warmup implementation has exactly one direct generation.
    warmup=read(root/'stages/natural/warmup/receipt.json')
    if warmup['plan_hash']!=plan['plan_hash'] or warmup['result']!=identity(root/'stages/natural/warmup/result.json'):
        raise ValueError('warmup call binding mismatch')
    gates=list(read_jsonl(root/'stages/natural/memory-gates.jsonl'))+list(read_jsonl(root/'stages/natural/paid-memory-gates.jsonl'))
    cap=plan['config']['native_budget_seconds'];calls=recorded+1
    if (not 0<=session['exact_seconds']<=envelope<=cap or count!=recorded or calls!=plan['config']['native_generation_budget_calls'] or
            not gates or not all(r['passed'] for r in gates)):
        raise ValueError('registered complete native envelope/call/resource cap failed; do not score Gold')
    report={'plan_hash':plan['plan_hash'],'assigned_jobs':len(records),'native_complete_envelope_seconds':envelope,
        'resident_session_seconds':session['exact_seconds'],'native_seconds_cap':cap,'paid_calls_including_warmup':calls,
        'native_call_cap':plan['config']['native_generation_budget_calls'],'paid_start_count':count,
        'all_resource_gates_passed':True,'registered_budget_passed':True,'performed_before_gold_scoring':not (root/'scores').exists(),
        'parent_closure':identity(root/'native-parent-closure.json'),'stage_closure':identity(root/'stages/natural/closed.json'),
        'source_hash':plan['source_snapshot_hash'],'tool_identity':identity(Path(__file__))}
    if inventory(root)!=before:raise ValueError('resource gate mutated retained run')
    report.update(input_inventory_hash=content_hash(before),retained_inputs_unchanged=True)
    output.mkdir(parents=True,exist_ok=False);publish(output/'resource-gate.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(validate(args.root,args.output),allow_nan=False))

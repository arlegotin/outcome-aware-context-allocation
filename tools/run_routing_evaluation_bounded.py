"""Run the frozen v5 offline evaluator in a fresh owned group, within 600 seconds.

This administrative wrapper does not alter the acquired study or its frozen
source. Its identity and complete envelope are recorded separately. Private
outputs and all failed attempts are retained. It performs no inference.
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def main():
    from outcome_poc.followup.clock import continuous_ns, boot_identity, clock_identity
    start = continuous_ns()
    import os
    from outcome_poc.reader_recovery.allocation_study import run_bounded_process
    from outcome_poc.reader_recovery.study import identity, read, publish
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--control', required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    output, control = args.output.resolve(), args.control.resolve()
    import outcome_poc
    if not Path(outcome_poc.__file__).resolve().is_relative_to(root/'source/src'):
        raise ValueError('exact frozen study source required')
    plan = read(root/'plan.json')
    if (plan['plan_hash'] != '3f6124b579d6b27f8b91f7aa7fe4a6fc1ac16c39b69fd96a86f2bdb843291c6b'
            or plan['config']['schema_version'] != 5):
        raise ValueError('only the registered complete v5 acquisition is authorized')
    retained = {root, Path('/private/tmp/oaca-routing-evaluation-tools-20261016'),
                Path(plan['config']['historical_checkout']).resolve(),
                *(Path(p).resolve() for p in plan['denied_paths'])}
    if any(p.is_relative_to(o) or o.is_relative_to(p) for p in retained for o in (control,output)):
        raise ValueError('fresh outputs overlap retained inputs')
    if control.exists() or output.exists() or control.is_relative_to(output) or output.is_relative_to(control):
        raise ValueError('two fresh separate private outputs required')
    control.mkdir(mode=0o700, parents=True, exist_ok=False)
    command = [sys.executable, '-B', '/private/tmp/oaca-routing-evaluation-tools-20261016/tools/evaluate_routing_signal.py',
               '--root',str(root),'--output',str(output)]
    tool = Path(command[2])
    publish(control/'started.json', {'plan_hash':plan['plan_hash'], 'start_ns':start,
        'boot_id':boot_identity(),'clock':clock_identity(),'cap_seconds':600,
        'wrapper':identity(Path(__file__)),'evaluator':identity(tool),'command':command,
        'frozen_source_hash':plan['source_snapshot_hash']})
    # The supervisor allows2s TERM and2s KILL cleanup; reserve those plus
    #2s publication time inside the complete600s envelope.
    remaining = 600 - (continuous_ns()-start)/1e9 - 6
    process, error = None, None
    try:
        if remaining <= 0:
            raise TimeoutError('offline budget exhausted before launch')
        process = run_bounded_process(command, dict(os.environ), control, remaining)
        if process.returncode != 0 or not (output/'public-summary.json').is_file():
            raise RuntimeError('offline evaluation failed; all evidence retained')
    except BaseException as caught:
        error = caught
    finally:
        summary = output/'public-summary.json'
        parent = control/'native-parent-closure.json'
        timeout = control/'native-stage-timeout.json'
        success = error is None and process is not None and process.returncode == 0 and summary.is_file()
        publish(control/'receipt.json', {'plan_hash':plan['plan_hash'],
            'returncode':process.returncode if process is not None else None,
            'public_summary':identity(summary) if success else None,
            'parent_closure':identity(parent) if parent.exists() else None,
            'failure_supervision':identity(timeout) if timeout.exists() else None,
            'error':None if error is None else f'{type(error).__name__}: {error}',
            'status':'completed' if success else 'failed', 'start_ns':start,
            'stop_lower_bound_ns':continuous_ns(),'boot_id':boot_identity()})
        stop = continuous_ns()
        publish(control/'envelope.json', {'start_ns':start,'stop_ns':stop,
            'seconds':(stop-start)/1e9,'cap_seconds':600,
            'includes_durable_receipt':True,'receipt':identity(control/'receipt.json'),
            'within_cap':(stop-start)/1e9 <= 600,
            'scope':'offline validation, fitting, held-out evaluation and durable receipt; not native serving'})
    if error is not None:
        raise error
    if (stop-start)/1e9 > 600:
        raise TimeoutError('complete offline envelope exceeded registration; evidence retained')


if __name__ == '__main__':
    main()

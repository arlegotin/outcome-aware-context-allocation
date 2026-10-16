"""NEW annotation-free verification of a complete continuously bounded index setup."""
from pathlib import Path
from ..storage import content_hash
from .study import read,identity


def validate_index_budget(root,plan):
    if plan['config'].get('schema_version') not in (4,5):return None
    root=Path(root);control=root/'index-supervision'
    if (control/'native-stage-timeout.json').exists():raise ValueError('incomplete bounded index setup')
    start=read(control/'started.json');parent=read(control/'native-parent-closure.json')
    receipt=read(control/'receipt.json');complete=read(control/'complete.json')
    if (start.get('plan_hash')!=plan['plan_hash'] or start.get('boot_id')!=plan['freeze']['boot_id'] or
            start.get('clock')!=plan['freeze']['clock'] or start.get('budget_seconds')!=plan['config']['index_budget_seconds'] or
            parent.get('command_hash')!=content_hash(start['command']) or parent.get('returncode')!=0 or
            parent.get('group_quiescent') is not True or parent.get('complete_assignment_scoring_allowed') is not True or
            receipt.get('plan_hash')!=plan['plan_hash'] or receipt.get('parent_closure')!=identity(control/'native-parent-closure.json') or
            receipt.get('index_seal')!=identity(root/'index-setup/index-seal.json') or
            complete.get('receipt')!=identity(control/'receipt.json') or
            complete.get('start_ns')!=start['start_ns'] or not 0<=start['start_ns']<=parent['stop_ns']<=complete['stop_ns'] or
            complete.get('seconds')!=(complete['stop_ns']-start['start_ns'])/1e9 or
            complete['seconds']>start['budget_seconds']):
        raise ValueError('bounded index setup receipt/domain/budget mismatch')
    return complete

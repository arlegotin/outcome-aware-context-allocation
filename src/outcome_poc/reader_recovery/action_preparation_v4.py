"""NEW privileged admission checks; never importable in action serving."""
from pathlib import Path
import json,os,subprocess
from ..storage import content_hash
from ..reader_probe.study import inventory
from .study import read,identity,verify_files
from .prompts import registry
from .action_study_v4 import SCREEN


CHECK=r'''
import json,sys
from pathlib import Path
from outcome_poc.reader_recovery.scoring import closed_records
from outcome_poc.reader_recovery.study import read,identity,verify_files
from outcome_poc.reader_recovery.analysis import validation_admission
from outcome_poc.storage import read_jsonl
root=Path(sys.argv[1]);plan,records=closed_records(root)
closure=read(root/'scores/closed.json')
if closure['plan_hash']!=plan['plan_hash'] or closure['assigned_jobs']!=len(records):raise ValueError('admission score roster mismatch')
verify_files({str(root/'scores'/name):value for name,value in closure['files'].items()})
rows=list(read_jsonl(root/'scores/scores.jsonl'));summary=read(root/'scores/summary.json')
admission=validation_admission(rows,read(root/'cohorts.json')['eligibility_count'])
if admission!=summary['reader_validation'] or not admission['admitted']:raise ValueError('independent reader gate not passed')
print(json.dumps({'plan_hash':plan['plan_hash'],'admission':admission,'arms':summary['arms']}))
'''


def authenticated_admission(config):
    if 'reader_admission' not in config:raise ValueError('authenticated independent reader admission required')
    attestation=config['reader_admission'];root=Path(attestation['root']).resolve(strict=True)
    if identity(root/'scores/closed.json')!=attestation['score_closure']:raise ValueError('reader admission score closure changed')
    audit=attestation['audit'];path=Path(audit['path'])
    if identity(path)!=audit['identity']:raise ValueError('independent admission audit changed')
    report=read(path);plan=read(root/'plan.json')
    if (report['root']!=str(root) or report['plan_hash']!=plan['plan_hash'] or report['retained_inputs_unchanged'] is not True or
            report['retained_scores']!=identity(root/'scores/scores.jsonl') or
            report['input_inventory_hash']!=content_hash(inventory(root)) or
            plan['config'].get('purpose')!='reader-admission' or plan['prompt_conditions']!=registry()):
        raise ValueError('independent admission audit/root/recipe binding mismatch')
    process=subprocess.run([config['native_interpreter'],'-B','-c',CHECK,str(root)],cwd=root,
        env={**os.environ,'PYTHONPATH':str(root/'source/src'),'PYTHONDONTWRITEBYTECODE':'1'},
        text=True,capture_output=True,timeout=60,check=True)
    checked=json.loads(process.stdout)
    if checked['plan_hash']!=plan['plan_hash'] or not checked['admission']['admitted']:
        raise ValueError('frozen-source independent reader admission failed')
    return plan


def admission_gate(config,source,N,eligible_hash):
    authenticated_admission(config)
    if config['research_screen']!=SCREEN:raise ValueError('prospective action-value screen changed')
    if config['purpose']=='authored-action-smoke':return
    if config.get('eligible_ids_hash')!=eligible_hash or config.get('eligible_N')!=N:
        raise ValueError('prospective action sampling frame changed')
    smoke=config.get('native_smoke')
    if not smoke:raise ValueError('authenticated exact-source 2/5/10 native smoke required')
    smoke_root=Path(smoke['root']);old=read(smoke_root/'plan.json');closure=read(smoke_root/'scores/closed.json')
    if identity(smoke_root/'scores/closed.json')!=smoke['score_closure'] or old['config']['purpose']!='authored-action-smoke':
        raise ValueError('action smoke identity/purpose mismatch')
    if closure['plan_hash']!=old['plan_hash'] or closure['assigned_jobs']!=6 or set(closure['files'])!={'scores.jsonl','summary.json'}:
        raise ValueError('action smoke score closure mismatch')
    verify_files({str(smoke_root/'scores'/name):value for name,value in closure['files'].items()})
    current={str(p.relative_to(source)):identity(p) for p in sorted((source/'src/outcome_poc').rglob('*.py'))+[source/'requirements.lock',source/'pyproject.toml']}
    if inventory(smoke_root/'source')!=current or any(a['strict_successes']!=2 for a in read(smoke_root/'scores/summary.json')['arms'].values()):
        raise ValueError('action native smoke exact source/known-answer mismatch')
    from .scoring import closed_records
    closed_records(smoke_root)


def prepare_action(root,config_path):
    from .action_study_v4 import is_action
    if not is_action(read(config_path)):raise ValueError('explicit v4 action protocol required')
    from .preparation_v3 import prepare_scientific
    return prepare_scientific(root,config_path)

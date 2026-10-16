"""NEW privileged v5 gate: reader admission, real action value and fresh smoke."""
from pathlib import Path
import json,os,subprocess
from ..storage import content_hash
from ..reader_probe.study import inventory
from .study import read,identity,verify_files
from .action_preparation_v4 import authenticated_admission
from .learning_study_v5 import is_learning,SCREEN

CHECK=r'''
import json,sys
from pathlib import Path
from outcome_poc.reader_recovery.scoring import closed_records
from outcome_poc.reader_recovery.study import read,identity,verify_files
from outcome_poc.reader_recovery.action_analysis_v4 import action_value_screen
from outcome_poc.schemas import PairedActionRow
from outcome_poc.storage import read_jsonl
root=Path(sys.argv[1]);plan,records=closed_records(root);closure=read(root/'scores/closed.json')
if closure['plan_hash']!=plan['plan_hash'] or closure['assigned_jobs']!=len(records):raise ValueError('action gate roster changed')
verify_files({str(root/'scores'/n):v for n,v in closure['files'].items()})
summary=read(root/'scores/summary.json');rows=list(read_jsonl(root/'scores/scores.jsonl'));cells={(r['task_id'],r['arm']):r for r in rows}
tasks={t['task_id']:t for t in read_jsonl(root/'tasks.jsonl')}
paired=[PairedActionRow(task_id=i,question=tasks[i]['question'],ranked_documents=[],features={},
 small_prediction_id=cells[i,'2']['job_id'],full_prediction_id=cells[i,'10']['job_id'],
 small_joint_em=cells[i,'2']['joint_em'],full_joint_em=cells[i,'10']['joint_em'],
 small_answer_em=cells[i,'2']['answer_em'],full_answer_em=cells[i,'10']['answer_em'],
 small_event_ids=[],full_event_ids=[],small_cost_seconds=cells[i,'2']['seconds'],full_cost_seconds=cells[i,'10']['seconds'],
 small_status=cells[i,'2']['status'],full_status=cells[i,'10']['status']) for i in read(root/'cohorts.json')['development']]
screen=action_value_screen(paired,summary['arms'],plan['config']['research_screen'])
if screen!=summary['action_value_screen'] or not screen['continue_to_learning']:raise ValueError('prospective action screen did not pass')
print(json.dumps({'plan_hash':plan['plan_hash'],'screen_passed':True}))
'''


def learning_gate(config,source,N,eligible_hash):
    authenticated_admission(config)
    if config.get('learning_screen')!=SCREEN or 'action_headroom' not in config:
        raise ValueError('authenticated action-value gate and learning screen required')
    a=config['action_headroom'];root=Path(a['root']).resolve(strict=True);plan=read(root/'plan.json')
    if identity(root/'scores/closed.json')!=a['score_closure']:raise ValueError('action score closure changed')
    proof=a['resource_gate'];path=Path(proof['path'])
    if identity(path)!=proof['identity']:raise ValueError('pre-Gold resource proof changed')
    resource=read(path)
    if (resource['plan_hash']!=plan['plan_hash'] or resource.get('registered_budget_passed') is not True or
            resource.get('performed_before_gold_scoring') is not True or resource.get('retained_inputs_unchanged') is not True or
            resource['native_seconds_cap']!=plan['config']['native_budget_seconds'] or
            not 0<=resource['resident_session_seconds']<=resource['native_complete_envelope_seconds']<=resource['native_seconds_cap'] or
            resource['paid_calls_including_warmup']!=plan['config']['native_generation_budget_calls'] or
            resource['parent_closure']!=identity(root/'native-parent-closure.json') or
            resource['stage_closure']!=identity(root/'stages/natural/closed.json')):
        raise ValueError('action study exceeded/missing registered resources or closure')
    audit=a['audit'];path=Path(audit['path'])
    if identity(path)!=audit['identity']:raise ValueError('fresh action Scorer audit changed')
    report=read(path)
    if (report['root']!=str(root) or report['plan_hash']!=plan['plan_hash'] or
            report['retained_inputs_unchanged'] is not True or report['retained_scores']!=identity(root/'scores/scores.jsonl') or
            report['input_inventory_hash']!=content_hash(inventory(root)) or plan['config']['purpose']!='action-headroom'):
        raise ValueError('fresh action audit/root binding mismatch')
    process=subprocess.run([config['native_interpreter'],'-B','-c',CHECK,str(root)],cwd=root,
        env={**os.environ,'PYTHONPATH':str(root/'source/src'),'PYTHONDONTWRITEBYTECODE':'1'},
        text=True,capture_output=True,timeout=60,check=True)
    if json.loads(process.stdout)!={'plan_hash':plan['plan_hash'],'screen_passed':True}:raise ValueError('frozen-source action gate failed')
    for field in ('precision','analysis_protocol'):
        value=config[field]
        if identity(value['path'])!=value['identity']:raise ValueError('prospective learning design/precision changed')
    forecast=read(config['precision']['path'])
    if forecast.get('N')!=config.get('eligible_N') or forecast.get('holdout_n')!=256 or forecast.get('fit_n')!=512:
        raise ValueError('prospective learning precision/frame mismatch')
    if config['purpose']=='authored-routing-smoke':return
    if config.get('eligible_N')!=N or config.get('eligible_ids_hash')!=eligible_hash:raise ValueError('fresh learning frame changed')
    smoke=config.get('native_smoke')
    if not smoke:raise ValueError('exact-source native routing smoke required')
    smoke_root=Path(smoke['root']);old=read(smoke_root/'plan.json');closure=read(smoke_root/'scores/closed.json')
    if (identity(smoke_root/'scores/closed.json')!=smoke['score_closure'] or old['config']['purpose']!='authored-routing-smoke' or
            closure['plan_hash']!=old['plan_hash'] or closure['assigned_jobs']!=4 or set(closure['files'])!={'scores.jsonl','summary.json'}):
        raise ValueError('native routing smoke score binding mismatch')
    verify_files({str(smoke_root/'scores'/n):v for n,v in closure['files'].items()})
    current={str(p.relative_to(source)):identity(p) for p in sorted((source/'src/outcome_poc').rglob('*.py'))+[source/'requirements.lock',source/'pyproject.toml']}
    if inventory(smoke_root/'source')!=current or any(a['strict_successes']!=2 for a in read(smoke_root/'scores/summary.json')['arms'].values()):
        raise ValueError('native routing smoke known-answer/exact source mismatch')
    from .scoring import closed_records
    closed_records(smoke_root)


def prepare_learning(root,config_path):
    if not is_learning(read(config_path)):raise ValueError('explicit v5 routing-signal protocol required')
    from .preparation_v3 import prepare_scientific
    return prepare_scientific(root,config_path)

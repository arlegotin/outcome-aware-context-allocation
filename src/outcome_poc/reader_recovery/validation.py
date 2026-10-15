"""Privileged preparation of one independently reserved reader validation."""
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import shutil
import subprocess
import numpy as np

from ..assets import verify_assets
from ..data_runtime import DocumentStore
from ..followup.clock import continuous_ns,boot_identity,clock_identity
from ..reader_probe.study import environment_identity,inventory
from ..storage import canonical_bytes,content_hash,read_jsonl,append_jsonl
from ..statistics import paired_quality_bounds
from .study import read,identity,publish,verify,READER,make_schedule
from .prompts import registry
from .reservations import preparation_reservations

PROTOCOL = 'reader-evidence-first-v1'


def validation_cohorts(prior):
    groups = [prior[k] for k in ('diagnosis','validation_reserved','evaluation_reserved')]
    ids = [i for group in groups for i in group]
    if [len(g) for g in groups]!=[32,64,128] or len(set(ids))!=224 or any(type(i) is not str or not i for i in ids):
        raise ValueError('prior reservation identity/count/overlap mismatch')
    return {'validation':list(groups[1]),'prior_diagnosis':list(groups[0]),'evaluation_reserved':list(groups[2]),
            'eligibility_count':prior['eligibility_count']-32,'source_eligibility_count':prior['eligibility_count'],
            'population_note':'Validation sample uniform conditional on the exposed diagnosis; exclude its32 questions. No resampling.'}


def prepare_validation(root,config_path,diagnosis_root):
    root,config_path,parent = Path(root).resolve(),Path(config_path).resolve(),Path(diagnosis_root).resolve()
    if root.exists():
        raise ValueError('new validation root must not exist; preserve all attempts')
    config = read(config_path)
    preparation_reservations(Path(__file__).resolve().parents[3],config['protocol_id'])
    if (config['protocol_id']!=PROTOCOL or content_hash(config['reader'])!=content_hash(READER) or
            [config[k] for k in ('validation_n','prior_diagnosis_n','evaluation_reserved_n')]!=[64,32,128] or
            config['arms']!=['baseline','evidence-first'] or config['repetitions']!=1 or
            config['semantic_retries']!=0 or config['cache_mode']!='none' or config['reuse_indexes']!=[]):
        raise ValueError('validation exceeds the single frozen candidate/recipe/reservation contract')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(config['deadline_utc']):
        raise ValueError('validation execution window expired')
    previous = verify(parent)
    if previous['config']['protocol_id']!='reader-recovery-v1' or not (parent/'scores/closed.json').is_file():
        raise ValueError('completed diagnosis and its untouched reservations required')
    historical = Path(config['historical_checkout']).resolve()
    source = Path(__file__).resolve().parents[3]
    if any(root.is_relative_to(p) or p.is_relative_to(root) for p in (parent,historical,source)):
        raise ValueError('validation root overlaps retained source/evidence')
    cohorts = validation_cohorts(read(parent/'cohorts.json'))
    root.mkdir(parents=True)
    start,error = continuous_ns(),None
    try:
        publish(root/'cohorts.json',cohorts)
        prepared = historical/'data/prepared'
        meta = read(prepared/'manifest.json')
        input_paths = [prepared/n for n in ('tasks.jsonl','documents.jsonl')]
        if any(identity(p)!=meta['files'][p.name] for p in input_paths):
            raise ValueError('prepared metadata identity changed')
        inputs = {str(p):identity(p) for p in input_paths+[parent/'plan.json',parent/'cohorts.json',parent/'scores/closed.json']}
        publish(root/'selection-frozen.json',{'cohorts':identity(root/'cohorts.json'),'inputs':inputs,
                'before_validation_outcomes':True,'parent_plan_hash':previous['plan_hash']})
        selected = set(cohorts['validation'])
        tasks = [t for t in read_jsonl(prepared/'tasks.jsonl') if t['task_id'] in selected]
        if len(tasks)!=64 or {t['task_id'] for t in tasks}!=selected:
            raise ValueError('validation task inventory incomplete')
        (root/'tasks.jsonl').write_bytes(b''.join(canonical_bytes(t)+b'\n' for t in tasks))
        documents = DocumentStore(prepared/'documents.jsonl')
        ids = sorted({d for t in tasks for d in t['candidate_ids']})
        (root/'documents.jsonl').write_bytes(b''.join(canonical_bytes(asdict(documents.get(d)))+b'\n' for d in ids))
        # A real empty denial probe, never an annotation projection.
        publish(root/'support-view.json',{})
        assets = read(parent/'assets.json')
        verify_assets(assets)
        publish(root/'assets.json',assets)
        publish(root/'prompt-conditions.json',registry())
        shutil.copyfile(config_path,root/'config.json')
        precision = {}
        for harms in (0,1,2):
            minimum = None
            for rescue in range(65-harms):
                a,b = np.zeros(64,dtype=int),np.zeros(64,dtype=int)
                a[:rescue],b[rescue:rescue+harms] = 1,1
                if paired_quality_bounds(a,b,cohorts['eligibility_count'],.003125)['ci'][0]>0:
                    minimum = rescue
                    break
            precision[str(harms)] = minimum
        publish(root/'precision.json',{'minimum_rescues_for_positive_lower_bound_by_harms':precision,
            'n':64,'N':cohorts['eligibility_count'],'tail_alpha':.003125,
            'scope':'Exact interval eligibility illustration, not power or a meaningful operational effect. The answer guard must also pass; modest gains may remain inconclusive.'})
        for p in sorted((source/'src/outcome_poc').rglob('*.py'))+[source/'requirements.lock',source/'pyproject.toml']:
            target = root/'source'/p.relative_to(source)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)
        (root/'source.diff').write_bytes(subprocess.check_output(['git','diff','--binary'],cwd=source))
        publish(root/'schedule.json',make_schedule(config,cohorts))
        denied = list(previous['denied_paths'])+[str(parent),str(source),str(root/'scores')]
        probes = list(previous['denied_probes'])+[str(parent/'support-view.json'),str(parent/'scores/scores.jsonl'),
                  str(source/'artifacts/runs/reader-recovery-v1-private-archive.tar.gz')]
        plan = {'root':str(root),'config':config,'config_identity':identity(config_path),
            'parent_diagnosis':{'plan_hash':previous['plan_hash'],'files':inputs},
            'freeze':{'boot_id':boot_identity(),'clock':clock_identity(),'settings':{'reader':config['reader']}},
            'gold_input':previous['gold_input'],'denied_paths':denied,'denied_probes':probes,
            'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),
            'environment':environment_identity(),'prompt_conditions':registry(),'files':inventory(root)}
        plan['plan_hash'] = content_hash(plan)
        publish(root/'plan.json',plan)
        verify(root)
        return {'root':str(root),'plan_hash':plan['plan_hash'],'assigned_jobs':128,'precision':precision}
    except BaseException as caught:
        error = caught
        raise
    finally:
        append_jsonl(root/'preparation-attempts.jsonl',{'start_ns':start,'stop_ns':continuous_ns(),
                     'clock_domain':'mach_continuous_time','status':'failed' if error else 'ok','error':str(error) if error else None})

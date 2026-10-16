"""NEW preparation-only independent validation schema. No generation admission.

Unique experiment identity is separate from study kind. This module is privileged
and must never enter a serving import closure. Historical v1 preparers stay closed.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np

from ..assets import verify_assets
from ..data_runtime import DocumentStore
from ..followup.study import all_strings
from ..reader_probe.study import inventory, environment_identity
from ..storage import canonical_bytes, content_hash, read_jsonl
from .reservations import preparation_reservations, eligible_ids
from .study import read, identity, publish, verify, make_schedule, is_fresh_validation, READER, verify_files
from .prompts import registry


def validate_output_locations(root, retained_roots, *, ledger_parents=()):
    root=Path(root).resolve()
    for output in (root,*(Path(p).resolve() for p in ledger_parents)):
        for retained in retained_roots:
            retained=Path(retained).resolve()
            if output.is_relative_to(retained) or retained.is_relative_to(output):
                raise ValueError('fresh output/ledger parent overlaps retained source/evidence')
    return root



def retained_locations(source, historical, additional, extras):
    """Protect every published retained root, including archived source checkouts."""
    roots={Path(source).resolve(),Path(historical).resolve()}
    roots.update(Path(p).parent.resolve() for p in additional['identities'] if Path(p).name=='cohorts.json')
    roots.update(Path(p).resolve(strict=True) for p in extras)
    for path in (Path(source)/'experiments').glob('*/evidence/retention.json'):
        record=read(path)
        roots.update(Path(p).resolve() for p in record['source_roots'])
        archive=Path(record['private_archive_path']).resolve()
        roots.add(archive)
        if archive.parent.name=='runs' and archive.parent.parent.name=='artifacts':
            roots.add(archive.parent.parent.parent)
    return sorted(roots)


def authenticated_reservations(source, protocol_id, expected_catalog):
    path=Path(source)/'experiments/reservation-manifests.json'
    if identity(path)!=expected_catalog:
        raise ValueError('reservation catalog identity changed')
    result=preparation_reservations(source,protocol_id)
    catalog=read(path)
    if not {'reader-recovery-v1','reader-evidence-first-v1'}<={r['protocol_id'] for r in catalog['protocols']}:
        raise ValueError('required recovery reservation families absent')
    return result


def historical_frame(historical, additional, expected_reservations):
    """Authenticate the four original families and current duplicate closure."""
    historical=Path(historical).resolve(strict=True)
    if type(expected_reservations) is not dict or not expected_reservations:
        raise ValueError('independently authenticated historical reservation identities required')
    verify_files(expected_reservations)
    prepared=historical/'data/prepared'
    meta=read(prepared/'manifest.json')
    names=('tasks.jsonl','documents.jsonl','duplicate-membership.jsonl','development-reservations.json')
    inputs={str(prepared/n):identity(prepared/n) for n in names}
    if any(inputs[str(prepared/n)]!=meta['files'][n] for n in names):
        raise ValueError('prepared metadata identities changed')
    inputs[str(prepared/'manifest.json')]=identity(prepared/'manifest.json')
    tasks=list(read_jsonl(prepared/'tasks.jsonl'))
    membership=list(read_jsonl(prepared/'duplicate-membership.jsonl'))
    training={i for g in membership if g['source']=='train' for i in g['member_ids']}
    config_path=historical/'configs/reader-quality-comparison.json'
    if str(config_path) not in expected_reservations:
        raise ValueError('historical reservation config authority absent')
    prior=read(config_path);inputs[str(config_path)]=identity(config_path)
    required={str(config_path),str(historical/prior['citation_cohorts']),
              str(historical/'artifacts/runs/reader-quality-comparison-v1/cohorts.json'),
              *(str(historical/n) for n in prior['old_metadata']+prior['prior_cohorts'])}
    if required!=set(expected_reservations):
        raise ValueError('historical reservation authority file coverage mismatch')
    declared=read(prepared/'development-reservations.json')
    old=set(declared['pilot']+declared['fit']+declared['tune'])
    for name in prior['old_metadata']:
        p=historical/name;old|=set(all_strings(read(p)))&training;inputs[str(p)]=identity(p)
    families={'original':old,'followup':set()}
    for name in prior['prior_cohorts']:
        p=historical/name;cohort=read(p)
        families['followup'].update(i for k in ('diagnosis','calibration_reserved','calibration','headroom') for i in cohort[k])
        inputs[str(p)]=identity(p)
    for family,name,keys in (
            ('citation',prior['citation_cohorts'],('diagnosis','comparison')),
            ('reader','artifacts/runs/reader-quality-comparison-v1/cohorts.json',('confirmation',))):
        p=historical/name;cohort=read(p)
        families[family]={i for key in keys for i in cohort[key]};inputs[str(p)]=identity(p)
    counts={k:len(v) for k,v in families.items()}
    union=set().union(*families.values())
    if (counts!={'original':448,'followup':224,'citation':320,'reader':128} or
            len(union)!=sum(counts.values()) or not union<=training or
            not additional['reserved_ids']<=training):
        raise ValueError('historical reservation inventory incomplete or changed')
    inputs.update(additional['identities'])
    eligible=eligible_ids(tasks,membership,union|additional['reserved_ids'])
    return prepared,tasks,eligible,inputs,counts


def prepare_fresh_validation(root, config_path):
    source=Path(__file__).resolve().parents[3]
    config_path=Path(config_path).resolve(strict=True)
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('duplicate fresh design key')
            result[k]=v
        return result
    config=json.loads(config_path.read_bytes(),object_pairs_hook=unique)
    canonical_bytes(config)  # Reject nonfinite/unsupported JSON before root creation.
    if not is_fresh_validation(config):
        raise ValueError('explicit fresh validation schema required')
    if (config.get('execution_mode')!='preparation-only' or config.get('native_generation_calls')!=0 or
            type(config.get('native_generation_calls')) is not int or
            config.get('semantic_retries')!=0 or config.get('cache_mode')!='none' or config.get('reuse_indexes')!=[] or
            config.get('reader')!=READER):
        raise ValueError('fresh v2 supports preparation only; scientific execution remains disabled')
    additional=authenticated_reservations(source,config['protocol_id'],config['reservation_catalog_identity'])
    historical=Path(config['historical_checkout']).resolve(strict=True)
    retained=retained_locations(source,historical,additional,config['retained_roots'])
    root=validate_output_locations(root,retained)
    if root.exists():raise ValueError('new fresh root must not exist; preserve attempts')
    started=datetime.fromisoformat(config['started_utc']);deadline=datetime.fromisoformat(config['deadline_utc'])
    now=datetime.now(timezone.utc)
    reserve=config['reporting_reserve_seconds']
    if (started.tzinfo is None or deadline.tzinfo is None or not started<=now<deadline or
            type(reserve) not in (int,float) or not np.isfinite(reserve) or reserve<=0 or
            (deadline-now).total_seconds()<=reserve):
        raise ValueError('current administrative window and positive reporting reserve required')
    prepared,tasks,eligible,inputs,counts=historical_frame(historical,additional,config['historical_reservation_identities'])
    if identity(prepared/'manifest.json')!=config['prepared_manifest_identity']:
        raise ValueError('prospective prepared manifest identity changed')
    n=config['validation_n']
    if n>len(eligible):raise ValueError('insufficient independent fresh population')
    chosen=np.random.Generator(np.random.PCG64(config['seed'])).permutation(len(eligible))[:n]
    cohorts={'validation':[eligible[int(i)] for i in chosen],
             'eligibility_count':len(eligible),'eligible_ids_hash':content_hash(eligible),
             'historical_reservation_counts':counts,'additional_reserved_ids':len(additional['reserved_ids']),
             'generator':{'algorithm':'numpy.Generator(PCG64)','seed':config['seed'],'numpy':np.__version__}}
    root.mkdir(parents=True,exist_ok=False)
    publish(root/'cohorts.json',cohorts)
    # Freeze metadata before projecting any assigned natural evidence. No Gold
    # answers, support projection or historical output is read. Reserved natural
    # evidence is not projected; normalized question text is used for closure.
    publish(root/'selection-frozen.json',{'config':identity(config_path),'cohorts':identity(root/'cohorts.json'),
                                        'inputs':inputs,'before_gold':True,'native_generation_calls':0})
    selected=set(cohorts['validation']);active=[t for t in tasks if t['task_id'] in selected]
    if any(t['split']!='fit_extension' for t in active):raise ValueError('fresh task split authorization mismatch')
    (root/'tasks.jsonl').write_bytes(b''.join(canonical_bytes(t)+b'\n' for t in active))
    documents=DocumentStore(prepared/'documents.jsonl')
    ids=sorted({d for t in active for d in t['candidate_ids']})
    (root/'documents.jsonl').write_bytes(b''.join(canonical_bytes(asdict(documents.get(d)))+b'\n' for d in ids))
    publish(root/'support-view.json',{})  # A real, empty denial probe.
    basic_path=historical/'artifacts/provenance/asset-manifest.json';basic=read(basic_path)
    assets={'required':['reader','encoder'],'assets':{k:basic['assets'][k] for k in ('reader','encoder')}}
    verify_assets(assets)
    if (assets['assets']['reader']['revision']!=READER['revision'] or
            assets['assets']['encoder']['revision']!='5c38ec7c405ec4b44b94cc5a9bb96e735b38267a'):
        raise ValueError('fresh asset revision mismatch')
    publish(root/'assets.json',assets);publish(root/'prompt-conditions.json',registry())
    shutil.copyfile(config_path,root/'config.json')
    for p in sorted((source/'src/outcome_poc').rglob('*.py'))+[source/'requirements.lock',source/'pyproject.toml']:
        target=root/'source'/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    (root/'source.diff').write_bytes(subprocess.check_output(['git','diff','--binary'],cwd=source))
    publish(root/'schedule.json',make_schedule(config,cohorts))
    plan={'root':str(root),'config':config,'config_identity':identity(config_path),
          'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),
          'environment':environment_identity(),'prompt_conditions':registry(),
          'scientific_execution':{'enabled':False,'reason':'preparation-only schema; complete allocation timing/stage integration and native validation required'},
          'input_identities':{**inputs,str(basic_path):identity(basic_path)},
          'files':inventory(root)}
    plan['plan_hash']=content_hash(plan);publish(root/'plan.json',plan);verify(root)
    return {'root':str(root),'plan_hash':plan['plan_hash'],'eligible_N':len(eligible),'assigned_jobs':2*n,
            'scientific_execution':False,'native_generation_calls':0}

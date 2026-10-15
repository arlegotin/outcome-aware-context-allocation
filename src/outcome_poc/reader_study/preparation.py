"""Privileged preparation and fresh shared indexing; never imported while serving."""
from dataclasses import asdict
from pathlib import Path
import shutil
import subprocess

from ..assets import verify_assets
from ..data_runtime import DocumentStore, load_tasks
from ..followup.clock import continuous_ns, clock_identity, boot_identity
from ..followup.runtime import stage_lock
from ..followup.study import all_strings, project_support, build_new_index, verify_index
from ..reader_probe.assets import verify_manifest as verify_strong_manifest
from ..reader_probe.profile import load_config as load_strong_profile
from ..reader_probe.study import (CHECKOUT, discover_denial_locations, denial_paths,
    _probes, inventory, environment_identity, DENIED_MODULES)
from ..retrieval import EncoderBackend
from ..storage import canonical_bytes, content_hash, read_jsonl, append_jsonl
from .study import (read, identity, publish, plan_cohorts, make_schedule, verify, verify_stage,
    decoding_settings, registry, STAGES, READERS, ENCODER, READER_IDS, SEED, _leaf_binding,
    STATISTICS, ADMISSION, validate_protocol)

EXPECTED_ELIGIBLE_COUNT = 88587
EXPECTED_ELIGIBLE_HASH = '340ac60b947956a03da43fa0a3bead3d1ceb60d39d648f658404bc8262f9fdc0'
EXPECTED_PREPARED_FINGERPRINT = '0be799643ab549f784c2d214c4c1cedce0a7d9195d25861b762aa6f70f0bf858'
PRIOR_COHORTS = ('artifacts/runs/followup-reader-headroom-v1/cohorts.json',
                 'artifacts/runs/followup-reader-headroom-v2/cohorts.json')
CITATION_COHORTS = 'artifacts/runs/citation-chain-reader-v1/cohorts.json'
def validate_config(config):
    return validate_protocol(config)


def validate_metadata_inventory(config):
    original=read(CHECKOUT/'configs/followup-reader-headroom.json')['old_metadata']
    if len(original)!=22 or set(config['old_metadata'])!=set(original) or len(config['old_metadata'])!=22:
        raise ValueError('all original 22 reservation metadata paths required')
    if set(config['prior_cohorts'])!=set(PRIOR_COHORTS) or len(config['prior_cohorts'])!=2:
        raise ValueError('both prior followup cohort files required')
    if config['citation_cohorts']!=CITATION_COHORTS:
        raise ValueError('mandatory citation cohort path required')
    for name in config['old_metadata']+config['prior_cohorts']+[config['citation_cohorts']]:
        if not Path(name).is_file():raise FileNotFoundError(name)


def _rows(path, values):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:
        for value in values:stream.write(canonical_bytes(value)+b'\n')


def _metadata(config):
    prepared=Path(config['prepared_dir']).resolve()
    names=('manifest.json','development-reservations.json','duplicate-membership.jsonl',
           'exclusions.jsonl','protected-population.json','tasks.jsonl','documents.jsonl')
    privileged={str(prepared/n):identity(prepared/n) for n in names}
    manifest=read(prepared/'manifest.json');reservations=read(prepared/'development-reservations.json')
    if manifest['fingerprint']!=EXPECTED_PREPARED_FINGERPRINT or manifest['reservations']!=reservations:
        raise ValueError('prepared manifest fingerprint/reservations mismatch')
    for name in names[1:]:
        if privileged[str(prepared/name)]!=manifest['files'][name]:
            raise ValueError('prepared manifest file identity mismatch')
    splits={'pilot':reservations['active_pilot'],'pilot_reservation':reservations['pilot'][32:],
        'fit':reservations['fit'],'tune':reservations['tune'],
        'fit_extension':reservations['fit_extension'],'protected':reservations['protected']}
    tasks=[]
    for split,ids in splits.items():
        rows=[asdict(t) for t in load_tasks(prepared/'tasks.jsonl',split)]
        if len(ids)!=len(set(ids)) or set(ids)!={t['task_id'] for t in rows}:
            raise ValueError('prepared split/reservation mismatch')
        tasks.extend(rows)
    if len(tasks)!=sum(1 for _ in read_jsonl(prepared/'tasks.jsonl')):
        raise ValueError('unrecognized prepared split')
    if set(read(prepared/'protected-population.json')['task_ids'])!=set(reservations['protected']):
        raise ValueError('protected population mismatch')
    membership=list(read_jsonl(prepared/'duplicate-membership.jsonl'))
    training={i for g in membership if g['source']=='train' for i in g['member_ids']}
    old_ids=set(reservations['pilot']+reservations['fit']+reservations['tune'])
    for name in config['old_metadata']:
        path=Path(name).resolve();old_ids|=set(all_strings(read(path)))&training
        privileged[str(path)]=identity(path)
    if len(old_ids)!=448:
        raise ValueError('original historical reservations must contain 448 IDs')
    prior_ids=set()
    for name in config['prior_cohorts']:
        path=Path(name).resolve();prior=read(path)
        for stage in ('diagnosis','calibration_reserved','calibration','headroom'):
            prior_ids.update(prior[stage])
        privileged[str(path)]=identity(path)
    if len(prior_ids)!=224 or not prior_ids<=training or prior_ids&old_ids:
        raise ValueError('all 224 independent followup reservations required')
    citation_path=Path(config['citation_cohorts']).resolve();citation=read(citation_path)
    citation_ids=set(citation['diagnosis']+citation['comparison'])
    if (len(citation['diagnosis'])!=64 or len(citation['comparison'])!=256 or len(citation_ids)!=320 or
            not citation_ids<=training or citation_ids&(old_ids|prior_ids)):
        raise ValueError('all 320 independent citation reservations required')
    privileged[str(citation_path)]=identity(citation_path)
    privileged[str(CHECKOUT/'configs/followup-reader-headroom.json')]=identity(CHECKOUT/'configs/followup-reader-headroom.json')
    cohorts=plan_cohorts(tasks,old_ids|prior_ids,membership,citation)
    if (cohorts['eligibility']['count']!=EXPECTED_ELIGIBLE_COUNT or
            cohorts['eligibility']['sorted_ids_hash']!=EXPECTED_ELIGIBLE_HASH):
        raise ValueError('fresh eligible population changed; prospective amendment required')
    return prepared,manifest,tasks,cohorts,privileged


def _assets(config,privileged):
    basic_path=Path(config['asset_manifest']).resolve();strong_path=Path(config['strong_asset_manifest']).resolve()
    profile_path=Path(config['strong_profile_config']).resolve()
    basic=read(basic_path);strong=read(strong_path)
    verify_strong_manifest(strong,load_strong_profile(profile_path))
    assets={'required':[*READER_IDS,'encoder'],'assets':{
        'qwen4b-instruct':basic['assets']['reader'],
        'qwen14b-nonthinking':strong['assets']['reader'],'encoder':basic['assets']['encoder']}}
    verify_assets(assets)
    for role,entry in assets['assets'].items():
        expected=config['encoder'] if role=='encoder' else config['readers'][role]['settings']
        if any(entry[k]!=expected[k] for k in ('repo_id','revision')) or entry['snapshot_hash']!=content_hash(entry['files']):
            raise ValueError('asset/profile pin mismatch')
    for path in (basic_path,strong_path,profile_path):privileged[str(path)]=identity(path)
    return assets


def _source(root):
    paths=sorted((CHECKOUT/'src/outcome_poc').rglob('*.py'))+[CHECKOUT/'requirements.lock',CHECKOUT/'pyproject.toml']
    original={str(p):identity(p) for p in paths}
    for path in paths:
        destination=root/'source'/path.relative_to(CHECKOUT)
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
        if identity(destination)!=original[str(path)]:raise ValueError('source changed while freezing')
    return original,inventory(root/'source')


def _leaves(root,plan,assets,schedule):
    leaves={}
    for stage in STAGES:
        leaves[stage]={}
        for reader in READER_IDS:
            leaf=root/'leaves'/stage/reader;leaf.mkdir(parents=True)
            jobs=[j for j in schedule if j['scientific_stage']==stage and j['reader_id']==reader]
            publish(leaf/'assets.json',{'required':['reader','encoder'],'assets':{'reader':assets['assets'][reader],'encoder':assets['assets']['encoder']}})
            publish(leaf/'schedule.json',jobs);publish(leaf/'prompts.json',registry())
            for name in plan['stage_files'][stage]:
                target=leaf/'inputs/diagnosis'/Path(name).name;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(root/name,target)
            outer=plan['freeze']
            freeze={'settings':{'reader':outer['settings']['readers'][reader]['settings'],'encoder':outer['settings']['encoder']},
                'reader_id':reader,'scientific_stage':stage,'bindings':outer['bindings'],
                'bindings_hash':outer['bindings_hash'],'boot_id':outer['boot_id'],'clock':outer['clock'],
                'decoding_hash':content_hash(decoding_settings(outer['settings']['readers'][reader]['settings'])),
                'leaf_binding':_leaf_binding(plan,stage,reader),'schedule_hash':content_hash(jobs),
                'cohorts_hash':outer['cohorts_hash'],'denied_paths':outer['denied_paths'],
                'denied_probes':outer['denied_probes']}
            lp={'schema_version':1,'root':str(leaf),'freeze':freeze,'files':inventory(leaf),
                'source_origin':{'path':str(root/'source'),'snapshot_hash':content_hash(outer['bindings']['source_snapshot']),
                                 'outer_bindings_hash':outer['bindings_hash']}}
            lp['plan_hash']=content_hash(lp);publish(leaf/'plan.json',lp)
            leaves[stage][reader]={'plan_hash':lp['plan_hash'],'identity':identity(leaf/'plan.json')}
    return leaves


def _prepare(root,config_path):
    config_path=Path(config_path).resolve();config=read(config_path)
    validate_config(config);validate_metadata_inventory(config)
    prepared,manifest,tasks,cohorts,privileged=_metadata(config)
    privileged[str(config_path)]=identity(config_path)
    assets=_assets(config,privileged)
    if any(root.is_relative_to(Path(a['local_path']).resolve()) or Path(a['local_path']).resolve().is_relative_to(root)
           for a in assets['assets'].values()):
        raise ValueError('assets must remain outside run/source snapshot')
    documents=DocumentStore(prepared/'documents.jsonl');by_id={t['task_id']:t for t in tasks}
    stage_files={}
    for stage in STAGES:
        selected=[by_id[i] for i in cohorts[stage]];directory=root/'inputs'/stage
        _rows(directory/'tasks.jsonl',selected)
        doc_ids=sorted({d for t in selected for d in t['candidate_ids']})
        _rows(directory/'documents.jsonl',(asdict(documents.get(d)) for d in doc_ids))
        stage_files[stage]=inventory(directory)
        stage_files[stage]={f'inputs/{stage}/{n}':v for n,v in stage_files[stage].items()}
    source_files,source_snapshot=_source(root)
    locations=discover_denial_locations(root)
    denied=sorted(set(denial_paths(locations)+[str(prepared)]+[str(Path(p).resolve()) for p in config['deny_paths']]))
    probes=sorted(set(_probes(denied,root)+locations['raw_probes']+locations['gold_probes']))
    sentinel=root/'stages/confirmation/index-setup/denial-sentinel'
    sentinel.parent.mkdir(parents=True);sentinel.write_bytes(b'authored future confirmation index denial probe\n')
    sentinel_files={str(sentinel.relative_to(root)):identity(sentinel)}
    profiles={r:{**config['readers'][r],'asset':assets['assets'][r],
                 'enable_thinking':False if r=='qwen14b-nonthinking' else None} for r in READER_IDS}
    bindings={'source_snapshot':source_snapshot,'assets':assets,'settings':config,
        'config':identity(config_path),'privileged_inputs':privileged,'reader_profiles':profiles,
        'prompts':registry(),'cohorts_hash':content_hash(cohorts),'stage_files':stage_files,
        'future_index_sentinel':sentinel_files}
    bindings_hash=content_hash(bindings);schedule=make_schedule(cohorts,bindings_hash)
    for name,value in [('cohorts.json',cohorts),('schedule.json',schedule),('prompts.json',registry()),
                       ('assets.json',assets),('config.json',config),('denial-locations.json',locations)]:
        publish(root/name,value)
    freeze={'kind':'paired-reader-quality-v1','schema_version':1,'settings':config,'bindings':bindings,
        'bindings_hash':bindings_hash,'cohorts_hash':content_hash(cohorts),'schedule_hash':content_hash(schedule),
        'boot_id':boot_identity(),'clock':clock_identity(),'environment':environment_identity(),
        'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=CHECKOUT,text=True).strip(),
        'source_files':source_files,'privileged_inputs':privileged,'denied_paths':denied,'denied_probes':probes,
        'denied_modules':list(DENIED_MODULES),'denial_locations_hash':content_hash(locations),
        'confirmation_denied_paths':[str(root/'inputs/confirmation'),str(root/'leaves/confirmation'),
            str(root/'stages/confirmation')],
        'confirmation_denied_probes':[str(root/'inputs/confirmation/tasks.jsonl'),
            str(root/'inputs/confirmation/documents.jsonl'),str(sentinel)]}
    # No Gold stream or support projection exists before method, inputs and roster freeze.
    publish(root/'selection-frozen.json',freeze)
    gold_path=prepared/'gold/gold.jsonl';expected_gold=manifest['files']['gold/gold.jsonl']
    if identity(gold_path)!=expected_gold:raise ValueError('Gold identity mismatch')
    selected=[by_id[i] for i in cohorts['development']]
    support=project_support(selected,{d:documents.get(d) for t in selected for d in t['candidate_ids']},read_jsonl(gold_path))
    projection=root/'inputs/development/support-doc-ids.jsonl';_rows(projection,support)
    sealed_stages={s:dict(files) for s,files in stage_files.items()}
    sealed_stages['development'][str(projection.relative_to(root))]=identity(projection)
    plan={'schema_version':1,'root':str(root),'freeze':freeze,'stage_files':sealed_stages,
        'future_index_sentinel':sentinel_files,'gold_input':{'path':str(gold_path),'identity':expected_gold}}
    plan['leaves']=_leaves(root,plan,assets,schedule)
    plan['files']={name:identity(root/name) for name in ('cohorts.json','schedule.json','prompts.json','assets.json',
                                                      'config.json','denial-locations.json','selection-frozen.json')}
    plan['plan_hash']=content_hash(plan);publish(root/'plan.json',plan)
    return verify(root,privileged=True)


def prepare(root:Path,config_path:Path)->dict:
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    start=continuous_ns();error=None
    try:
        with stage_lock(root):return _prepare(root,config_path)
    except BaseException as caught:
        error=caught;raise
    finally:
        append_jsonl(root/'setup.jsonl',{'kind':'preparation','start_ns':start,'stop_ns':continuous_ns(),
            'clock_domain':'mach_continuous_time','status':'failed' if error else 'ok','error':str(error) if error else None})


def index(root:Path,stage:str)->dict:
    root=Path(root).resolve()
    with stage_lock(root):
        plan=verify(root,stage=stage)
        container=root/'stages'/stage/'index-setup'
        setup=container/'build';setup.mkdir(parents=True,exist_ok=False)
        start=continuous_ns();error=None
        try:
            assets=read(root/'assets.json')['assets']
            encoder=EncoderBackend(Path(assets['encoder']['local_path']))
            documents=DocumentStore(root/'inputs'/stage/'documents.jsonl')
            seal=build_new_index(setup,(documents.get(i) for i in sorted(documents.offsets)),encoder)
            verify_index(setup,seal)
            envelope={'kind':'reader-quality-shared-index-v1','plan_hash':plan['plan_hash'],
                'scientific_stage':stage,'bindings_hash':plan['freeze']['bindings_hash'],
                'input_identities':plan['stage_files'][stage],
                'encoder':assets['encoder'],'index_setup':str(setup),'index_path':str(setup/'index'),
                'index_seal_path':str(setup/'index-seal.json'),'index_seal_identity':identity(setup/'index-seal.json'),
                'index_seal_hash':content_hash(seal)}
            publish(container.parent/'index-envelope.json',envelope)
            return seal
        except BaseException as caught:
            error=caught;raise
        finally:
            append_jsonl(container.parent/'index-setup.jsonl',{'kind':'index_setup','scientific_stage':stage,
                'start_ns':start,'stop_ns':continuous_ns(),'clock_domain':'mach_continuous_time',
                'status':'failed' if error else 'ok','error':str(error) if error else None,
                'plan_hash':plan['plan_hash'],'nested_index_seal':'index-setup/build/index-seal.json'})

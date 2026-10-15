"""Privileged, prospective preparation. Never imported by the serving entry path."""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess

from ..assets import verify_assets
from ..data_runtime import DocumentStore, load_tasks
from ..followup.clock import continuous_ns, clock_identity, boot_identity
from ..followup.study import all_strings, project_support, build_new_index
from ..retrieval import EncoderBackend
from ..storage import canonical_bytes, content_hash, read_jsonl, append_jsonl
from .study import read, identity, publish, plan_cohorts, make_schedule, verify, verify_stage, decoding_settings, STAGES
from .prompts import registry

EXPECTED_ELIGIBLE_COUNT = 88907
EXPECTED_ELIGIBLE_HASH = '7cd2dc2fee7388fef8cc5badd9c64317a91550b6badc0abf394ca99dd98e18a7'
EXPECTED_PREPARED_FINGERPRINT = '0be799643ab549f784c2d214c4c1cedce0a7d9195d25861b762aa6f70f0bf858'
READER = {'repo_id':'mlx-community/Qwen3-4B-Instruct-2507-4bit',
          'revision':'50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b','max_context_tokens':8192,
          'max_new_tokens':256,'timeout_seconds':120,'prefill_step_size':512,'temperature':0}
ENCODER = {'repo_id':'BAAI/bge-small-en-v1.5','revision':'5c38ec7c405ec4b44b94cc5a9bb96e735b38267a',
           'dimensions':384,'device':'cpu','precision':'float32','normalized':True}
PRIOR_COHORTS = ('artifacts/runs/followup-reader-headroom-v1/cohorts.json',
                 'artifacts/runs/followup-reader-headroom-v2/cohorts.json')


def validate_config(config):
    if (config['reader'] != READER or config['encoder'] != ENCODER or
            config['seed'] != 20261015 or config['diagnosis_n'] != 64 or config['comparison_n'] != 256):
        raise ValueError('citation study frozen reader/encoder/sampling settings differ')


def validate_metadata_inventory(config):
    checkout = Path(__file__).resolve().parents[3]
    original = read(checkout/'configs/followup-reader-headroom.json')['old_metadata']
    if len(original) != 22 or not set(original) <= set(config['old_metadata']):
        raise ValueError('all 22 historical metadata paths are mandatory')
    if not set(PRIOR_COHORTS) <= set(config['prior_cohorts']):
        raise ValueError('all prior follow-up reservations are mandatory')


def _rows(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:
        for value in values:
            stream.write(canonical_bytes(value)+b'\n')


def _prepare(root, config_path):
    config_path = Path(config_path).resolve()
    config = read(config_path)
    validate_config(config)
    validate_metadata_inventory(config)
    prepared = Path(config['prepared_dir']).resolve()
    names = ('manifest.json','development-reservations.json','duplicate-membership.jsonl',
             'exclusions.jsonl','protected-population.json','tasks.jsonl','documents.jsonl')
    privileged = {str(prepared/n):identity(prepared/n) for n in names}
    checkout = Path(__file__).resolve().parents[3]
    old_config = checkout/'configs/followup-reader-headroom.json'
    privileged[str(old_config)] = identity(old_config)
    manifest = read(prepared/'manifest.json')
    reservations = read(prepared/'development-reservations.json')
    if manifest['fingerprint'] != EXPECTED_PREPARED_FINGERPRINT or manifest['reservations'] != reservations:
        raise ValueError('prepared manifest fingerprint/reservations mismatch')
    for name in names[1:]:
        if privileged[str(prepared/name)] != manifest['files'][name]:
            raise ValueError('prepared manifest file identity mismatch')
    split_ids = {'pilot':reservations['active_pilot'],'pilot_reservation':reservations['pilot'][32:],
                 'fit':reservations['fit'],'tune':reservations['tune'],
                 'fit_extension':reservations['fit_extension'],'protected':reservations['protected']}
    tasks = []
    for split, ids in split_ids.items():
        rows = [asdict(t) for t in load_tasks(prepared/'tasks.jsonl',split)]
        if set(ids) != {t['task_id'] for t in rows} or len(ids) != len(set(ids)):
            raise ValueError('prepared split/reservation mismatch')
        tasks.extend(rows)
    if len(tasks) != sum(1 for _ in read_jsonl(prepared/'tasks.jsonl')):
        raise ValueError('unrecognized prepared split')
    if set(read(prepared/'protected-population.json')['task_ids']) != set(reservations['protected']):
        raise ValueError('protected population mismatch')
    membership = list(read_jsonl(prepared/'duplicate-membership.jsonl'))
    training_ids = {i for group in membership if group['source']=='train' for i in group['member_ids']}
    old_ids = set(reservations['pilot']+reservations['fit']+reservations['tune'])
    for name in config['old_metadata']:
        path = Path(name).resolve()
        old_ids |= set(all_strings(read(path))) & training_ids
        privileged[str(path)] = identity(path)
    prior_ids = set()
    for name in config['prior_cohorts']:
        path = Path(name).resolve()
        prior = read(path)
        for stage in ('diagnosis','calibration_reserved','calibration','headroom'):
            prior_ids.update(prior[stage])
        privileged[str(path)] = identity(path)
    # Production inventories cannot silently omit the 24 unexecuted calibration reservations.
    if config['prior_cohorts'] and len(prior_ids) != 224:
        raise ValueError('prior follow-up reservation union must contain 224 IDs')
    if not prior_ids <= training_ids:
        raise ValueError('prior reservations absent from training membership')
    old_ids |= prior_ids
    cohorts = plan_cohorts(tasks,old_ids,membership)
    if (cohorts['eligibility']['count'] != EXPECTED_ELIGIBLE_COUNT or
            cohorts['eligibility']['sorted_ids_hash'] != EXPECTED_ELIGIBLE_HASH):
        raise ValueError('eligible population changed; prospective amendment required')
    documents = DocumentStore(prepared/'documents.jsonl')
    by_id = {t['task_id']:t for t in tasks}
    stage_files = {}
    for stage in STAGES:
        selected = [by_id[i] for i in cohorts[stage]]
        doc_ids = sorted({d for t in selected for d in t['candidate_ids']})
        directory = root/'inputs'/stage
        _rows(directory/'tasks.jsonl',selected)
        _rows(directory/'documents.jsonl',(asdict(documents.get(d)) for d in doc_ids))
        stage_files[stage] = {str(p.relative_to(root)):identity(p) for p in directory.iterdir()}
    assets_path = Path(config['asset_manifest']).resolve()
    assets = read(assets_path)
    assets = {'required':['reader','encoder'],'assets':{k:assets['assets'][k] for k in ('reader','encoder')}}
    verify_assets(assets)
    for role in ('reader','encoder'):
        entry = assets['assets'][role]
        if any(entry[k] != config[role][k] for k in ('repo_id','revision')):
            raise ValueError('asset settings mismatch')
        if entry['snapshot_hash'] != content_hash(entry['files']):
            raise ValueError('asset snapshot hash mismatch')
    privileged[str(assets_path)] = identity(assets_path)
    privileged[str(config_path)] = identity(config_path)
    checkout = Path(__file__).resolve().parents[3]
    source_paths = sorted((checkout/'src/outcome_poc').rglob('*.py'))
    source_paths += [checkout/'requirements.lock',checkout/'pyproject.toml']
    source = {str(p):identity(p) for p in source_paths}
    for path in source_paths:
        target = root/'source'/path.relative_to(checkout)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
        if identity(target) != source[str(path)]:
            raise ValueError('source changed while freezing snapshot')
    source_snapshot = {str(p.relative_to(root/'source')):identity(p) for p in (root/'source').rglob('*') if p.is_file()}
    bindings = {'source_snapshot':source_snapshot,'assets':assets,'config':identity(config_path),
                'privileged_inputs':privileged,'settings':config,'decoding':decoding_settings(config),
                'prompts':registry(),'cohorts_hash':content_hash(cohorts),'stage_files':stage_files}
    bindings_hash = content_hash(bindings)
    schedule = make_schedule(cohorts,bindings_hash)
    for name,value in [('cohorts.json',cohorts),('schedule.json',schedule),('prompts.json',registry()),('assets.json',assets)]:
        publish(root/name,value)
    denied = [str(prepared),str(checkout/'data'),str(checkout/'models/pinned/data'),str(checkout/'artifacts')]
    denied += [str(Path(p).resolve()) for p in config.get('deny_paths',[])]
    freeze = {'kind':'citation-chain-v1','schema_version':1,'settings':config,'bindings':bindings,
              'bindings_hash':bindings_hash,'cohorts_hash':content_hash(cohorts),'schedule_hash':content_hash(schedule),
              'decoding_hash':content_hash(bindings['decoding']),
              'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip(),
              'source_files':source,'privileged_inputs':privileged,
              'clock':clock_identity(),'boot_id':boot_identity(),'old_window_applies':False,
              'denied_paths':denied,'denied_probes':[str(prepared/'gold/gold.jsonl')],
              'comparison_denied_path':str(root/'inputs/comparison'),
              'comparison_denied_paths':[str(root/'inputs/comparison'),str(root/'stages/comparison')],
              'comparison_denied_probe':str(root/'inputs/comparison/tasks.jsonl'),
              'created_utc':datetime.now(timezone.utc).isoformat()}
    # All selection, prompt strings, schedule, settings and source bytes close before Gold access.
    publish(root/'selection-frozen.json',freeze)
    gold_path = prepared/'gold/gold.jsonl'
    expected_gold = manifest['files']['gold/gold.jsonl']
    if identity(gold_path) != expected_gold:
        raise ValueError('prepared Gold identity mismatch')
    selected = [by_id[i] for i in cohorts['diagnosis']]
    support = project_support(selected,{d:documents.get(d) for t in selected for d in t['candidate_ids']},read_jsonl(gold_path))
    projection = root/'inputs/diagnosis/support-doc-ids.jsonl'
    _rows(projection,support)
    # Projection is intentionally sealed after selection; it cannot influence job IDs/order.
    sealed_stages = {stage:dict(files) for stage,files in stage_files.items()}
    sealed_stages['diagnosis'][str(projection.relative_to(root))] = identity(projection)
    common = {str(p.relative_to(root)):identity(p) for p in root.rglob('*')
              if p.is_file() and not p.is_relative_to(root/'inputs') and p.name != 'setup.jsonl'}
    plan = {'schema_version':1,'freeze':freeze,'files':common,'stage_files':sealed_stages,
            'asset_files':{str(Path(a['local_path'])/n):v for a in assets['assets'].values() for n,v in a['files'].items()},
            'gold_input':{'path':str(gold_path),'identity':expected_gold}}
    plan['plan_hash'] = content_hash(plan)
    publish(root/'plan.json',plan)
    verify(root,privileged=True)
    return plan


def prepare(root, config_path):
    root = Path(root).resolve()
    start = continuous_ns()
    root.mkdir(parents=True,exist_ok=False)
    error = None
    try:
        return _prepare(root,config_path)
    except BaseException as caught:
        error = caught
        raise
    finally:
        append_jsonl(root/'setup.jsonl',{'kind':'preparation','start_ns':start,'stop_ns':continuous_ns(),
                     'clock_domain':'mach_continuous_time','status':'failed' if error else 'ok',
                     'error':str(error) if error else None})


def index(root, stage):
    root = Path(root).resolve()
    plan = verify(root)
    verify_stage(root,stage,plan)
    setup = root/'stages'/stage/'index-setup'
    setup.mkdir(parents=True,exist_ok=False)
    start = continuous_ns()
    error = None
    try:
        assets = read(root/'assets.json')
        encoder = EncoderBackend(Path(assets['assets']['encoder']['local_path']))
        documents = DocumentStore(root/'inputs'/stage/'documents.jsonl')
        return build_new_index(setup,(documents.get(i) for i in sorted(documents.offsets)),encoder)
    except BaseException as caught:
        error = caught
        raise
    finally:
        # This outer envelope includes acquisition; build_new_index's inner seal is nested.
        append_jsonl(setup.parent/'index-setup.jsonl',{'kind':'index_setup','stage':stage,
                     'start_ns':start,'stop_ns':continuous_ns(),'clock_domain':'mach_continuous_time',
                     'status':'failed' if error else 'ok','error':str(error) if error else None,
                     'plan_hash':plan['plan_hash'],'nested_index_seal':'index-setup/index-seal.json'})

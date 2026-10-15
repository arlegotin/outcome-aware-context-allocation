"""Annotation-free paired factors, cohorts, and stage-local protocol verification."""
from dataclasses import asdict
import hashlib
from pathlib import Path

import numpy as np

from ..assets import verify_assets
from ..citation_study.prompts import registry as prompt_registry
from ..data_runtime import DocumentStore, load_tasks
from ..followup.study import read, identity, publish, normalized, validate_projection
from ..reader_probe.profile import READER as STRONG_READER
from ..reader_probe.study import inventory, environment_identity, DENIED_MODULES, denial_paths
from ..storage import content_hash, read_jsonl

SEED = 271829
NAMESPACE = 'reader-quality-v1'
STAGES = ('development', 'confirmation')
READER_IDS = ('qwen4b-instruct', 'qwen14b-nonthinking')
EXECUTION_MODE = 'continuous-resident-v1'
OLD_READER = {'repo_id':'mlx-community/Qwen3-4B-Instruct-2507-4bit',
    'revision':'50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b','max_context_tokens':8192,
    'max_new_tokens':256,'timeout_seconds':120,'prefill_step_size':512,'temperature':0}
READERS = {'qwen4b-instruct':{'factory':'NativeReaderFactory','settings':OLD_READER},
           'qwen14b-nonthinking':{'factory':'ProfileFactory','settings':STRONG_READER}}
ENCODER = {'repo_id':'BAAI/bge-small-en-v1.5','revision':'5c38ec7c405ec4b44b94cc5a9bb96e735b38267a',
           'dimensions':384,'device':'cpu','precision':'float32','normalized':True}


STATISTICS = {'primary':'confirmation:joint_em:10:14b-minus-4b',
    'quality_tail_alpha':0.0125,'answer_guard_tail_alpha':0.00625,
    'interval_method':'finite-population-hypergeometric-harm-rescue','repetitions':1,
    'timing_claim':'descriptive-only','confirmation_population':88587}
ADMISSION = {'complete_healthy_development':True,'natural10_joint_em':'14b-strictly-greater',
             'natural2_answer_em':'14b-no-lower','natural10_answer_em':'14b-no-lower'}


def validate_protocol(config):
    expected={'readers':READERS,'encoder':ENCODER,'seed':SEED,'development_n':16,
        'confirmation_n':128,'eligible_count':88587,
        'eligible_hash':'340ac60b947956a03da43fa0a3bead3d1ceb60d39d648f658404bc8262f9fdc0',
        'prompt_condition':'baseline','statistics':STATISTICS,'admission':ADMISSION}
    if any(content_hash(config.get(k))!=content_hash(v) for k,v in expected.items()):
        raise ValueError('reader study frozen protocol/config changed')
    paths={'prepared_dir','asset_manifest','strong_asset_manifest','strong_profile_config',
           'old_metadata','prior_cohorts','citation_cohorts','deny_paths'}
    if set(config)!=set(expected)|paths:
        raise ValueError('reader study config inventory changed')


def registry():
    return {'baseline':prompt_registry()['baseline']}


def decoding_settings(reader):
    """Exact GenerationRequest decoding declaration for a single reader leaf."""
    return {**reader,'cache_mode':'none','execution_mode':EXECUTION_MODE}


def plan_cohorts(tasks, old_ids, membership, citation, *, development_n=16, confirmation_n=128):
    if any(type(n) is not int or n <= 0 for n in (development_n,confirmation_n)):
        raise ValueError('positive integer cohort sizes required')
    by_id = {t['task_id']:t for t in tasks}
    if len(by_id) != len(tasks):
        raise ValueError('duplicate task ID')
    diagnosis, deferred = citation['diagnosis'], citation['comparison']
    if (len(set(diagnosis)) != len(diagnosis) or len(set(deferred)) != len(deferred) or
            set(diagnosis)&set(deferred) or not set(diagnosis+deferred)<=set(by_id) or
            any(by_id[i]['split']!='fit_extension' for i in diagnosis+deferred)):
        raise ValueError('citation reservation metadata invalid')
    if len(diagnosis)<development_n:
        raise ValueError('insufficient citation development reservations')
    development = sorted(diagnosis,key=lambda i:(hashlib.sha256(
        (NAMESPACE+':development:'+i).encode('utf-8')).digest(),i))[:development_n]
    old_ids = set(old_ids) | set(diagnosis+deferred) | {t['task_id'] for t in tasks
        if t['split'] in {'pilot','pilot_reservation','fit','tune'}}
    protected = {t['task_id'] for t in tasks if t['split']=='protected'}
    excluded = old_ids | protected | {i for g in membership if g['source']=='dev' for i in g['member_ids']}
    hashes = {content_hash(normalized(by_id[i]['question'])) for i in excluded if i in by_id}
    # Same fixed-point Unicode/group closure as the approved citation planner.
    while True:
        groups = [g for g in membership if excluded.intersection(g['member_ids']) or g['group_key_hash'] in hashes]
        expanded = excluded | {i for g in groups for i in g['member_ids']}
        expanded_hashes = hashes | {g['group_key_hash'] for g in groups}
        expanded_hashes |= {content_hash(normalized(by_id[i]['question'])) for i in expanded if i in by_id}
        if expanded==excluded and expanded_hashes==hashes:
            break
        excluded,hashes=expanded,expanded_hashes
    representatives = {}
    for group in membership:
        if group['disposition']=='retained':
            i=group['representative_id']
            if i in representatives:
                raise ValueError('duplicate retained representative membership')
            representatives[i]=group
    eligible=[]
    for task in tasks:
        i=task['task_id'];g=representatives.get(i)
        if (g is None or not g['member_ids'] or i!=min(g['member_ids']) or
                g['source']!=('dev' if task['split']=='protected' else 'train') or
                g['group_key_hash']!=content_hash(normalized(task['question']))):
            raise ValueError('prepared representative membership mismatch')
        if task['split']=='fit_extension' and i not in excluded and g['group_key_hash'] not in hashes:
            eligible.append(i)
    if len({representatives[i]['group_key_hash'] for i in eligible})!=len(eligible):
        raise ValueError('eligible duplicate normalized groups')
    ids=sorted(eligible)
    if len(ids)<confirmation_n:
        raise ValueError('insufficient independent fresh questions')
    permutation=np.random.Generator(np.random.PCG64(SEED)).permutation(len(ids))
    confirmation=[ids[int(i)] for i in permutation[:confirmation_n]]
    return {'development':development,'confirmation':confirmation,
        'sample_hashes':{'development':content_hash(development),'confirmation':content_hash(confirmation)},
        'confirmation_population':len(ids),
        'generator':{'seed':SEED,'algorithm':'numpy.random.Generator(PCG64)','numpy_version':np.__version__},
        'eligibility':{'count':len(ids),'sorted_ids':ids,'sorted_ids_hash':content_hash(ids),
            'excluded_ids':sorted(excluded),'old_ids':sorted(old_ids),'protected_ids':sorted(protected),
            'excluded_group_hashes':sorted(hashes)}}


def make_schedule(cohorts, bindings_hash):
    if set(cohorts['development'])&set(cohorts['confirmation']):
        raise ValueError('cohorts overlap')
    jobs=[]
    for stage in STAGES:
        if len(set(cohorts[stage]))!=len(cohorts[stage]):
            raise ValueError('duplicate cohort reservation')
        readers=sorted(READER_IDS,key=lambda r:(content_hash([SEED,NAMESPACE,stage,r]),r))
        for reader in readers:
            cells=[(i,a) for i in cohorts[stage] for a in
                (('2','10','support-documents') if stage=='development' else ('2','10'))]
            cells.sort(key=lambda c:(content_hash([SEED,NAMESPACE,stage,reader,*c]),*c))
            for task_id,arm in cells:
                factors={'stage':'diagnosis','scientific_stage':stage,'reader_id':reader,
                    'task_id':task_id,'prompt_condition':'baseline','evidence_arm':arm,'arm':arm,
                    'repetition':0,'execution_mode':EXECUTION_MODE,'bindings_hash':bindings_hash,
                    'system_hash':registry()['baseline']['system_hash']}
                jobs.append({**factors,'job_id':content_hash([NAMESPACE,factors]),'ordinal':len(jobs)})
    return jobs


def _files(base, files):
    for name,expected in files.items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts:
            raise ValueError('unsafe sealed relative path')
        path=Path(base)/p
        if any(q.is_symlink() for q in (path,*path.parents)) or identity(path)!=expected:
            raise ValueError(f'sealed file changed: {path}')


def _checksum(plan):
    if plan.get('plan_hash')!=content_hash({k:v for k,v in plan.items() if k!='plan_hash'}):
        raise ValueError('plan identity mismatch')


def leaf_root(root,stage,reader_id):
    if stage not in STAGES or reader_id not in READER_IDS:
        raise ValueError('unknown scientific stage or reader')
    return Path(root).resolve()/'leaves'/stage/reader_id


def _leaf_binding(plan,stage,reader_id):
    f=plan['freeze']
    return {'outer_bindings_hash':f['bindings_hash'],'scientific_stage':stage,'reader_id':reader_id,
        'reader_profile_hash':content_hash(f['bindings']['reader_profiles'][reader_id]),
        'source_snapshot_hash':content_hash(f['bindings']['source_snapshot']),
        'cohorts_hash':f['cohorts_hash']}


def verify_leaf(root,stage,reader_id,plan=None):
    root=Path(root).resolve();leaf=leaf_root(root,stage,reader_id)
    plan=plan or verify(root)
    # Admission happens before even leaf input identities are read.
    verify_stage(root,stage,plan)
    return _verify_leaf(root,stage,reader_id,plan)


def _verify_leaf(root,stage,reader_id,plan):
    leaf=leaf_root(root,stage,reader_id)
    expected=plan['leaves'][stage][reader_id]
    _files(leaf,{'plan.json':expected['identity']})
    lp=read(leaf/'plan.json');_checksum(lp)
    if lp['plan_hash']!=expected['plan_hash'] or lp['root']!=str(leaf):
        raise ValueError('leaf plan/root mismatch')
    _files(leaf,lp['files'])
    f=lp['freeze'];outer=plan['freeze']
    settings=outer['settings']['readers'][reader_id]['settings']
    if (f['reader_id']!=reader_id or f['scientific_stage']!=stage or
            f['settings']!={'reader':settings,'encoder':outer['settings']['encoder']} or
            f['bindings']!=outer['bindings'] or f['bindings_hash']!=outer['bindings_hash'] or
            f['boot_id']!=outer['boot_id'] or f['clock']!=outer['clock'] or
            f['leaf_binding']!=_leaf_binding(plan,stage,reader_id) or
            f['decoding_hash']!=content_hash(decoding_settings(settings))):
        raise ValueError('leaf reader/stage/profile binding mismatch')
    source={'path':str(root/'source'),'snapshot_hash':content_hash(outer['bindings']['source_snapshot']),
            'outer_bindings_hash':outer['bindings_hash']}
    if lp['source_origin']!=source:
        raise ValueError('leaf source origin mismatch')
    assets=read(root/'assets.json')['assets']
    if read(leaf/'assets.json')!={'required':['reader','encoder'],'assets':{'reader':assets[reader_id],'encoder':assets['encoder']}}:
        raise ValueError('leaf reader asset mismatch')
    schedule=[j for j in read(root/'schedule.json') if j['scientific_stage']==stage and j['reader_id']==reader_id]
    if read(leaf/'schedule.json')!=schedule or f['schedule_hash']!=content_hash(schedule):
        raise ValueError('leaf schedule mismatch')
    names={'assets.json','schedule.json','prompts.json'}
    for name,expected_identity in plan['stage_files'][stage].items():
        target='inputs/diagnosis/'+Path(name).name
        names.add(target)
        if lp['files'].get(target)!=expected_identity:
            raise ValueError('leaf evidence input mismatch')
    if set(lp['files'])!=names or read(leaf/'prompts.json')!=registry():
        raise ValueError('leaf input/prompt inventory mismatch')
    return lp


def _validate_admission(root,plan):
    try:
        from .runtime import validate_admission
    except ImportError as error:
        raise ValueError('confirmation admission validator unavailable') from error
    return validate_admission(root,plan)


def verify_stage(root,stage,plan=None):
    if stage not in STAGES:
        raise ValueError('unknown scientific stage')
    root=Path(root).resolve();plan=plan or verify(root)
    if stage=='confirmation':
        _validate_admission(root,plan)
    _verify_stage_inputs(root,stage,plan)
    _verify_stage_index(root,stage,plan)
    return plan


def _verify_stage_index(root,stage,plan):
    from ..followup.study import verify_index
    directory=root/'stages'/stage
    setup=directory/'index-setup/build'
    envelope_path=directory/'index-envelope.json'
    if not setup.exists() and not envelope_path.exists():
        return
    if not (setup/'index-seal.json').is_file() or not envelope_path.is_file():
        raise ValueError('shared index setup incomplete; preserve failed attempt')
    seal=read(setup/'index-seal.json')
    verify_index(setup,seal)
    expected={'kind':'reader-quality-shared-index-v1','plan_hash':plan['plan_hash'],
        'scientific_stage':stage,'bindings_hash':plan['freeze']['bindings_hash'],
        'input_identities':plan['stage_files'][stage],
        'encoder':read(root/'assets.json')['assets']['encoder'],
        'index_setup':str(setup),'index_path':str(setup/'index'),
        'index_seal_path':str(setup/'index-seal.json'),
        'index_seal_identity':identity(setup/'index-seal.json'),'index_seal_hash':content_hash(seal)}
    if read(envelope_path)!=expected:
        raise ValueError('shared index envelope binding mismatch')


def _verify_stage_inputs(root,stage,plan):
    files=plan['stage_files'][stage]
    prefix=f'inputs/{stage}/'
    names={prefix+'tasks.jsonl',prefix+'documents.jsonl'}
    if stage=='development':names.add(prefix+'support-doc-ids.jsonl')
    if set(files)!=names:
        raise ValueError('stage input inventory mismatch')
    _files(root,files)
    tasks=load_tasks(root/prefix/'tasks.jsonl','fit_extension')
    if [t.task_id for t in tasks]!=read(root/'cohorts.json')[stage]:
        raise ValueError('stage task order mismatch')
    documents=DocumentStore(root/prefix/'documents.jsonl')
    if set(documents.offsets)!={d for t in tasks for d in t.candidate_ids}:
        raise ValueError('stage document inventory mismatch')
    if stage=='development':
        validate_projection(list(read_jsonl(root/prefix/'support-doc-ids.jsonl')),[asdict(t) for t in tasks])
    sentinel=plan['future_index_sentinel']
    if stage=='confirmation':_files(root,sentinel)


def verify(root,*,privileged=False,stage=None):
    root=Path(root).resolve();plan=read(root/'plan.json');_checksum(plan)
    if plan['root']!=str(root):raise ValueError('sealed run moved')
    _files(root,plan['files'])
    freeze=plan['freeze'];bindings=freeze['bindings']
    validate_protocol(freeze['settings'])
    if read(root/'config.json')!=freeze['settings']:
        raise ValueError('frozen config/settings mismatch')
    if (content_hash(bindings)!=freeze['bindings_hash'] or bindings['settings']!=freeze['settings'] or
            read(root/'selection-frozen.json')!=freeze):
        raise ValueError('settings/execution binding mismatch')
    # Import the annotation-free validators only: preparation is serving-denied.
    if content_hash(freeze['settings']['readers'])!=content_hash(READERS) or freeze['settings']['encoder']!=ENCODER:
        raise ValueError('reader profiles changed')
    profiles={r:{**freeze['settings']['readers'][r],
        'asset':read(root/'assets.json')['assets'][r],
        'enable_thinking':False if r=='qwen14b-nonthinking' else None} for r in READER_IDS}
    if bindings['reader_profiles']!=profiles or bindings['assets']!=read(root/'assets.json'):
        raise ValueError('asset/reader profile binding mismatch')
    verify_assets(bindings['assets'])
    for role,asset in bindings['assets']['assets'].items():
        expected=ENCODER if role=='encoder' else READERS[role]['settings']
        if any(asset[k]!=expected[k] for k in ('repo_id','revision')):
            raise ValueError('asset/profile pin mismatch')
        if asset['snapshot_hash']!=content_hash(asset['files']):raise ValueError('asset snapshot identity mismatch')
    if inventory(root/'source')!=bindings['source_snapshot']:
        raise ValueError('sealed source inventory changed')
    if environment_identity()!=freeze['environment']:
        raise ValueError('sealed environment changed')
    cohorts=read(root/'cohorts.json');schedule=read(root/'schedule.json')
    if (content_hash(cohorts)!=freeze['cohorts_hash'] or bindings['cohorts_hash']!=freeze['cohorts_hash'] or
            content_hash(schedule)!=freeze['schedule_hash'] or schedule!=make_schedule(cohorts,freeze['bindings_hash'])):
        raise ValueError('cohort/schedule binding mismatch')
    if read(root/'prompts.json')!=registry() or bindings['prompts']!=registry():
        raise ValueError('baseline prompt registry mismatch')
    natural={s:{n:v for n,v in fs.items() if not n.endswith('/support-doc-ids.jsonl')} for s,fs in plan['stage_files'].items()}
    if (set(plan['stage_files'])!=set(STAGES) or set(plan['leaves'])!=set(STAGES) or
            any(set(plan['leaves'][s])!=set(READER_IDS) for s in STAGES) or
            plan['future_index_sentinel']!=bindings['future_index_sentinel'] or
            natural!=bindings['stage_files']):
        raise ValueError('natural stage input binding mismatch')
    locations=read(root/'denial-locations.json')
    if (freeze['denial_locations_hash']!=content_hash(locations) or
            not set(denial_paths(locations))<=set(freeze['denied_paths']) or
            freeze['denied_modules']!=list(DENIED_MODULES)):
        raise ValueError('denial projection mismatch')
    if stage is not None:
        verify_stage(root,stage,plan)
        for reader in READER_IDS:_verify_leaf(root,stage,reader,plan)
    if privileged:
        for path,expected in freeze['privileged_inputs'].items():
            if identity(path)!=expected:raise ValueError('privileged input changed')
        for path,expected in freeze['source_files'].items():
            if identity(path)!=expected:raise ValueError('source changed since preparation')
        if identity(plan['gold_input']['path'])!=plan['gold_input']['identity']:
            raise ValueError('Gold identity mismatch')
        for s in STAGES:
            _verify_stage_inputs(root,s,plan)
            for reader in READER_IDS:_verify_leaf(root,s,reader,plan)
    return plan

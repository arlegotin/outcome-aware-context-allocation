"""Immutable development-study planning. No annotation imports on serving paths."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import unicodedata

from ..storage import canonical_bytes, content_hash, atomic_json, read_jsonl, append_jsonl
from .clock import continuous_ns, clock_identity, boot_identity

SEED = 20261015
NAMESPACE = 'fresh-development-reader-headroom-v1'
STAGES = ('calibration', 'diagnosis', 'headroom')
ARMS = ('2', '5', '10')
ORACLE = 'ORACLE-SUPPORT-DOCS'


def read(path):
    return json.loads(Path(path).read_text())


def identity(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return {'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}


def verify_files(bindings):
    for path, expected in bindings.items():
        if identity(Path(path)) != expected:
            raise ValueError(f'sealed file changed: {path}')


def publish(path, value):
    """Idempotent immutable atomic publication; callers use a single-writer lock."""
    path = Path(path)
    if path.exists():
        if path.read_bytes() != canonical_bytes(value):
            raise ValueError(f'immutable output differs: {path}')
        return
    atomic_json(path, value)


def normalized(question):
    return ' '.join(unicodedata.normalize('NFC', question).casefold().split())


def all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from all_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_strings(child)


def plan_cohorts(tasks, old_ids, membership, document_lengths):
    by_id = {row['task_id']: row for row in tasks}
    if len(by_id) != len(tasks):
        raise ValueError('duplicate task ID')
    old_ids = set(old_ids) | {r['task_id'] for r in tasks if r['split'] in {'pilot','pilot_reservation','fit','tune'}}
    protected = {r['task_id'] for r in tasks if r['split'] == 'protected'}
    excluded = old_ids | protected
    # Expand to fixed point, preserving aliases even if a group overlaps another.
    while True:
        expanded = excluded | {member for row in membership if excluded.intersection(row['member_ids'])
                               for member in row['member_ids']}
        if expanded == excluded:
            break
        excluded = expanded
    old_questions = {normalized(by_id[i]['question']) for i in excluded if i in by_id}
    eligible = [r for r in tasks if r['split'] == 'fit_extension' and r['task_id'] not in excluded
                and normalized(r['question']) not in old_questions]
    # Prepared representatives must actually be unique under the specified normalization.
    if len({normalized(r['question']) for r in eligible}) != len(eligible):
        raise ValueError('eligible duplicate representative questions')
    ordered = sorted((r['task_id'] for r in eligible),
                     key=lambda i: (content_hash([SEED,NAMESPACE,i]), i))
    if len(ordered) < 224:
        raise ValueError('insufficient fresh eligible questions')
    diagnosis, reserved, headroom = ordered[:64], ordered[64:96], ordered[96:224]
    length_order = sorted(reserved, key=lambda i:(sum(document_lengths[d] for d in by_id[i]['candidate_ids']), i))
    return {'diagnosis': diagnosis, 'calibration_reserved': reserved,
            'calibration': [length_order[j*31//7] for j in range(8)], 'headroom': headroom,
            'eligibility': {'count':len(ordered), 'sorted_ids_hash':content_hash(sorted(ordered)),
                           'excluded_ids':sorted(excluded), 'old_ids':sorted(old_ids),
                           'protected_ids':sorted(protected),
                           'normalized_excluded_hash':content_hash(sorted(old_questions))}}


def make_schedule(cohorts):
    jobs = []
    for stage in STAGES:
        for task_id in cohorts[stage]:
            for repetition in range(2 if stage == 'calibration' else 1):
                arms = list(ARMS) + ([ORACLE] if stage == 'diagnosis' else [])
                arms.sort(key=lambda arm:(content_hash([SEED,NAMESPACE,stage,task_id,repetition,arm]),arm))
                for arm in arms:
                    job = {'stage':stage,'task_id':task_id,'arm':arm,'repetition':repetition}
                    jobs.append({**job, 'job_id':content_hash([NAMESPACE,job]), 'ordinal':len(jobs)})
    return jobs


def validate_projection(rows, tasks):
    by_id = {t['task_id']: t for t in tasks}
    seen = set()
    for row in rows:
        if (type(row) is not dict or set(row) != {'task_id','support_doc_ids'} or
                type(row['task_id']) is not str or row['task_id'] not in by_id or row['task_id'] in seen):
            raise ValueError('oracle projection fields/task identity invalid')
        ids = row['support_doc_ids']
        if (type(ids) is not list or not ids or any(type(d) is not str for d in ids) or
                len(ids)!=len(set(ids)) or not set(ids)<=set(by_id[row['task_id']]['candidate_ids'])):
            raise ValueError('oracle projection support document identity invalid')
        seen.add(row['task_id'])
    if seen != set(by_id):
        raise ValueError('oracle projection incomplete')


def project_support(tasks, documents, gold_rows):
    """Privileged preparation only: project IDs, discard answers and sentence labels."""
    by_id = {t['task_id']:t for t in tasks}
    result = {}
    for row in gold_rows:
        task_id = row['task_id']
        if task_id not in by_id:
            continue
        if task_id in result:
            raise ValueError('duplicate assigned Gold task')
        candidates = [documents[d] for d in by_id[task_id]['candidate_ids']]
        support = set()
        for title, index in row['supporting_facts']:
            matches = [d for d in candidates if d.title == title]
            if len(matches)!=1 or type(index) is not int or not 0<=index<len(matches[0].sentences):
                raise ValueError('missing or ambiguous support mapping')
            support.add(matches[0].doc_id)
        result[task_id] = {'task_id':task_id,'support_doc_ids':sorted(support)}
    rows = [result[i] for i in by_id if i in result]
    validate_projection(rows,tasks)
    return rows


def validate_config(config):
    expected_reader = {'repo_id':'mlx-community/Qwen3-4B-Instruct-2507-4bit',
        'revision':'50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b','max_context_tokens':8192,
        'max_new_tokens':256,'timeout_seconds':120,'prefill_step_size':512}
    expected_encoder = {'repo_id':'BAAI/bge-small-en-v1.5','revision':'5c38ec7c405ec4b44b94cc5a9bb96e735b38267a',
                        'dimensions':384,'device':'cpu','precision':'float32'}
    if config['reader'] != expected_reader or config['encoder'] != expected_encoder:
        raise ValueError('follow-up frozen reader/encoder settings differ')


def _prepare(root, config_path):
    """Fail-if-exists production preparation; cohorts close before Gold is opened."""
    from ..data_runtime import DocumentStore, load_tasks
    from ..assets import verify_assets
    from .runtime import sandbox_profile
    root, config_path = Path(root).resolve(), Path(config_path).resolve()
    config = read(config_path)
    validate_config(config)
    prepared = Path(config['prepared_dir']).resolve()
    tasks = []
    # Strict annotation-free validation over every row occurs in load_tasks.
    for split in ('pilot','pilot_reservation','fit','tune','fit_extension','protected'):
        tasks.extend(asdict(t) for t in load_tasks(prepared/'tasks.jsonl',split))
    if len(tasks) != sum(1 for _ in read_jsonl(prepared/'tasks.jsonl')):
        raise ValueError('unrecognized prepared split')
    documents = DocumentStore(prepared/'documents.jsonl')
    safe_names = ('manifest.json','development-reservations.json','duplicate-membership.jsonl',
                  'exclusions.jsonl','protected-population.json','tasks.jsonl','documents.jsonl')
    bindings = {str(prepared/n):identity(prepared/n) for n in safe_names}
    reservations=read(prepared/'development-reservations.json')
    old_ids=set(reservations['pilot']+reservations['fit']+reservations['tune'])
    metadata_unknown = set()
    known_ids = {t['task_id'] for t in tasks}
    membership = list(read_jsonl(prepared/'duplicate-membership.jsonl'))
    training_ids={i for group in membership if group['source']=='train' for i in group['member_ids']}
    for name in config['old_metadata']:
        path = Path(name).resolve()
        value = read(path)
        strings = set(all_strings(value))
        old_ids |= strings & training_ids
        metadata_unknown |= {s for s in strings if s.startswith(('invented-','fixture-'))}
        bindings[str(path)] = identity(path)
    bindings[str(config_path)] = identity(config_path)
    manifest = read(prepared/'manifest.json')
    for name in safe_names[1:]:
        if bindings[str(prepared/name)] != manifest['files'][name]:
            raise ValueError('prepared manifest identity mismatch')
    if manifest['reservations']!=reservations:
        raise ValueError('prepared reservations disagree with manifest')
    expected_splits={'pilot':reservations['active_pilot'],'pilot_reservation':reservations['pilot'][32:],
        'fit':reservations['fit'],'tune':reservations['tune'],'fit_extension':reservations['fit_extension'],
        'protected':reservations['protected']}
    for split,ids in expected_splits.items():
        if set(ids)!={t['task_id'] for t in tasks if t['split']==split}:
            raise ValueError('prepared split/reservation mismatch')
    if set(read(prepared/'protected-population.json')['task_ids'])!=set(reservations['protected']):
        raise ValueError('protected population mismatch')
    membership = list(read_jsonl(prepared/'duplicate-membership.jsonl'))
    representatives={r['representative_id']:r for r in membership if r['disposition']=='retained'}
    for t in tasks:
        group=representatives.get(t['task_id'])
        if (group is None or group['source']!=('dev' if t['split']=='protected' else 'train') or
                group['group_key_hash']!=content_hash(normalized(t['question'])) or
                t['task_id']!=min(group['member_ids'])):
            raise ValueError('prepared representative membership mismatch')
    class Lengths(dict):
        def __missing__(self,key):
            value=documents.get(key).character_count
            self[key]=value
            return value
    lengths = Lengths()
    cohorts = plan_cohorts(tasks, old_ids, membership, lengths)
    selected_ids = set(cohorts['diagnosis']+cohorts['calibration_reserved']+cohorts['headroom'])
    selected = [t for t in tasks if t['task_id'] in selected_ids]
    candidate_ids = sorted({d for t in selected for d in t['candidate_ids']})
    assets = read(Path(config['asset_manifest']).resolve())
    model_assets = {'required':['reader','encoder'], 'assets':{k:assets['assets'][k] for k in ('reader','encoder')}}
    verify_assets(model_assets)
    for role in ('reader','encoder'):
        for key in ('repo_id','revision'):
            if model_assets['assets'][role][key] != config[role][key]:
                raise ValueError('asset settings mismatch')
    bindings[str(Path(config['asset_manifest']).resolve())] = identity(Path(config['asset_manifest']))
    # Capture the entire in-repository Python import closure, including immutable historical dependencies.
    checkout = Path(__file__).resolve().parents[3]
    source = {str(p.resolve()):identity(p) for p in (checkout/'src/outcome_poc').rglob('*.py')}
    for name in ('requirements.lock','pyproject.toml'):
        source[str(checkout/name)] = identity(checkout/name)
    snapshot = root/'source'
    for filename in source:
        relative = Path(filename).relative_to(checkout)
        target = snapshot/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(filename,target)
    # Deny all original prepared stores, Gold aliases/raw data and historical artifacts.
    deny = [prepared, checkout/'data',checkout/'models/pinned/data',checkout/'artifacts']
    # root may live under artifacts; profile grants only root reads back after broad deny.
    deny += [Path(p).resolve() for p in config.get('deny_paths',[])]
    for p in (checkout/'data').rglob('*'):
        if p.is_dir() and ('gold' in p.name.casefold() or 'raw' in p.name.casefold()):
            deny.append(p.resolve())
    denied_probes = []
    for p in (prepared/'gold/gold.jsonl', checkout/'models/pinned/data/hotpot_train_v1.1.json'):
        if p.is_file():
            denied_probes.append(str(p.resolve()))
    profile = sandbox_profile(root,deny)
    (root/'native.sb').write_text(profile)
    for name,value in [('tasks.jsonl',selected),('documents.jsonl',[asdict(documents.get(d)) for d in candidate_ids])]:
        (root/name).write_bytes(b''.join(canonical_bytes(row)+b'\n' for row in value))
    publish(root/'cohorts.json',cohorts)
    schedule = make_schedule(cohorts)
    publish(root/'schedule.json',schedule)
    publish(root/'assets.json',model_assets)
    freeze = {'kind':NAMESPACE,'cohorts_hash':content_hash(cohorts),'schedule_hash':content_hash(schedule),
              'selected_task_ids':sorted(selected_ids),'selected_documents_hash':content_hash(candidate_ids),
              'prepared_fingerprint':manifest.get('fingerprint'), 'settings':config,
              'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip(),
              'source_files':source,'privileged_inputs':bindings,'unknown_metadata_ids':sorted(metadata_unknown),
              'clock':clock_identity(),'boot_id':boot_identity(),'old_window_applies':False,
              'denied_probes':denied_probes,'created_utc':datetime.now(timezone.utc).isoformat()}
    # This durable precursor proves cohort/action selection preceded new annotation projection.
    publish(root/'selection-frozen.json',freeze)
    gold_path = prepared/'gold/gold.jsonl'
    expected_gold = manifest['files']['gold/gold.jsonl']
    if identity(gold_path) != expected_gold:
        raise ValueError('prepared Gold identity mismatch')
    diagnosis_tasks = [t for t in selected if t['task_id'] in cohorts['diagnosis']]
    support = project_support(diagnosis_tasks,{d:documents.get(d) for d in candidate_ids},read_jsonl(gold_path))
    (root/'support-doc-ids.jsonl').write_bytes(b''.join(canonical_bytes(r)+b'\n' for r in support))
    files = {str(p.relative_to(root)):identity(p) for p in root.rglob('*') if p.is_file()}
    asset_files={str(Path(a['local_path'])/name):value for a in model_assets['assets'].values() for name,value in a['files'].items()}
    plan = {'freeze':freeze, 'files':files,'asset_files':asset_files,'gold_input':{'path':str(gold_path),'identity':expected_gold}}
    plan['plan_hash'] = content_hash(plan)
    publish(root/'plan.json',plan)
    verify(root)
    return plan


def prepare(root, config_path):
    root=Path(root).resolve()
    start=continuous_ns()
    root.mkdir(parents=True,exist_ok=False)
    error=None
    try:
        return _prepare(root,config_path)
    except BaseException as caught:
        error=caught
        raise
    finally:
        append_jsonl(root/'setup.jsonl',{'kind':'preparation','start_ns':start,'stop_ns':continuous_ns(),
            'clock_domain':'mach_continuous_time','status':'failed' if error else 'ok',
            'error':str(error) if error else None})


def verify(root, *, privileged=True):
    root = Path(root).resolve()
    plan = read(root/'plan.json')
    if plan['plan_hash'] != content_hash({k:v for k,v in plan.items() if k!='plan_hash'}):
        raise ValueError('plan checksum mismatch')
    verify_files({str(root/name):expected for name,expected in plan['files'].items()})
    verify_files(plan.get('asset_files',{}))
    if privileged:
        verify_files(plan['freeze']['source_files'])
        verify_files(plan['freeze']['privileged_inputs'])
        verify_files({plan['gold_input']['path']:plan['gold_input']['identity']})
    tasks = list(read_jsonl(root/'tasks.jsonl'))
    cohorts, schedule = read(root/'cohorts.json'), read(root/'schedule.json')
    if content_hash(cohorts)!=plan['freeze']['cohorts_hash'] or content_hash(schedule)!=plan['freeze']['schedule_hash']:
        raise ValueError('schedule/cohort binding mismatch')
    if schedule != make_schedule(cohorts):
        raise ValueError('invalid schedule')
    validate_projection(list(read_jsonl(root/'support-doc-ids.jsonl')),
                        [t for t in tasks if t['task_id'] in cohorts['diagnosis']])
    return plan


def build_new_index(root, documents, encoder, *, clock=continuous_ns):
    from ..retrieval import build_index
    root=Path(root).resolve()
    if any(root.iterdir()):
        raise ValueError('index setup parent must be fresh and empty')
    start=clock()
    try:
        manifest=build_index(documents,encoder,root/'index',reuse_indexes=())
        stop=clock()
    except BaseException as error:
        append_jsonl(root/'setup.jsonl',{'kind':'index_build','start_ns':start,'stop_ns':clock(),
             'status':'failed','error':f'{type(error).__name__}: {error}'})
        raise
    seal={'manifest_hash':content_hash(manifest),'files':{str(p.relative_to(root)):identity(p)
          for p in root.rglob('*') if p.is_file()}, 'start_ns':start,'stop_ns':stop,
          'clock_domain':'mach_continuous_time','internal_durations':'diagnostic active clock only'}
    verify_index(root,seal)
    publish(root/'index-seal.json',seal)
    return seal


def verify_index(root, seal=None):
    from ..retrieval import _completed_manifest
    root=Path(root).resolve()
    seal=seal or read(root/'index-seal.json')
    verify_files({str(root/n):v for n,v in seal['files'].items()})
    manifest=_completed_manifest(root/'index')
    if (type(manifest.get('offline')) is not dict or
            'reuse_sources' not in manifest['offline'] or manifest['offline']['reuse_sources'] != [] or
            manifest['offline']['reused_window_count']!=0 or
            Path(manifest['completion']['attempt_ledger']) != root/'index-attempts.jsonl' or
            content_hash(manifest)!=seal['manifest_hash']):
        raise ValueError('strict new physical no-reuse index required')
    return manifest

"""Privileged reservation, diagnostic projection and new index setup."""
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import numpy as np

from ..assets import verify_assets
from ..data_runtime import DocumentStore
from ..followup.clock import continuous_ns, clock_identity, boot_identity
from ..followup.study import all_strings, build_new_index
from ..generation import ANSWER_SYSTEM, offline_network
from ..reader_probe.study import inventory, environment_identity
from ..storage import canonical_bytes, content_hash, read_jsonl, append_jsonl
from .reservations import eligible_ids,preparation_reservations
from .study import read, identity, publish, verify, GROUP_ARMS, READER, make_schedule


def _rows(path,values):
    with Path(path).open('xb') as stream:
        for value in values:
            stream.write(canonical_bytes(value)+b'\n')


def prepare(root,config_path, *, selection_from=None, deny_roots=()):
    root,config_path = Path(root).resolve(),Path(config_path).resolve()
    if root.exists():
        raise ValueError('new recovery root must not exist; never overwrite/rebind')
    config = read(config_path)
    if content_hash(config['reader']) != content_hash(READER):
        raise ValueError('unchanged reader recipe required for diagnosis')
    historical = Path(config['historical_checkout']).resolve()
    source = Path(__file__).resolve().parents[3]
    additional = preparation_reservations(source,config['protocol_id'])
    if root.is_relative_to(historical) or historical.is_relative_to(root) or root == source:
        raise ValueError('fresh root must be outside retained checkout')
    if (config['protocol_id']!='reader-recovery-v1' or config['arms']!=[a for v in GROUP_ARMS.values() for a in v] or
            config['repetitions']!=1 or config['semantic_retries']!=0 or config['cache_mode']!='none' or config['reuse_indexes']!=[]):
        raise ValueError('unsupported recovery diagnostic protocol')
    for key in ('diagnosis_n','validation_reserved_n','evaluation_reserved_n'):
        if type(config[key]) is not int or config[key] <= 0:
            raise ValueError('positive finite cohort sizes required')
    if datetime.now(timezone.utc) >= datetime.fromisoformat(config['deadline_utc']):
        raise ValueError('new research execution window expired')
    prepared = historical/'data/prepared'
    meta = read(prepared/'manifest.json')
    names = ('tasks.jsonl','documents.jsonl','duplicate-membership.jsonl','development-reservations.json')
    inputs = {str(prepared/name):identity(prepared/name) for name in names}
    if any(inputs[str(prepared/name)]!=meta['files'][name] for name in names):
        raise ValueError('prepared metadata identities changed')
    tasks = list(read_jsonl(prepared/'tasks.jsonl'))
    by_id = {t['task_id']:t for t in tasks}
    membership = list(read_jsonl(prepared/'duplicate-membership.jsonl'))
    training = {i for g in membership if g['source']=='train' for i in g['member_ids']}
    prior_config = read(historical/'configs/reader-quality-comparison.json')
    old = set()
    for name in prior_config['old_metadata']:
        p = historical/name
        old |= set(all_strings(read(p))) & training
        inputs[str(p)] = identity(p)
    declared = read(prepared/'development-reservations.json')
    old |= set(declared['pilot']+declared['fit']+declared['tune'])
    families = {'original':old}
    followup = set()
    for name in prior_config['prior_cohorts']:
        p = historical/name
        cohort = read(p)
        followup |= {i for key in ('diagnosis','calibration_reserved','calibration','headroom') for i in cohort[key]}
        inputs[str(p)] = identity(p)
    families['followup'] = followup
    for family,name,keys in (
        ('citation',prior_config['citation_cohorts'],('diagnosis','comparison')),
        ('reader','artifacts/runs/reader-quality-comparison-v1/cohorts.json',('development','confirmation'))):
        p = historical/name
        cohort = read(p)
        families[family] = {i for key in keys for i in cohort[key]} if family!='reader' else set(cohort['confirmation'])
        inputs[str(p)] = identity(p)
    expected = {'original':448,'followup':224,'citation':320,'reader':128}
    if {k:len(v) for k,v in families.items()} != expected:
        raise ValueError('historical reservation inventory incomplete or changed')
    union = set().union(*families.values())
    if len(union) != sum(expected.values()) or not union <= training:
        raise ValueError('historical reservation families overlap or leave training')
    inputs.update(additional['identities'])
    eligible = eligible_ids(tasks,membership,union|additional['reserved_ids'])
    count = sum(config[k] for k in ('diagnosis_n','validation_reserved_n','evaluation_reserved_n'))
    if len(eligible) < count:
        raise ValueError('insufficient independent fresh population')
    permutation = np.random.Generator(np.random.PCG64(config['seed'])).permutation(len(eligible))
    selected = [eligible[int(i)] for i in permutation[:count]]
    a,b = config['diagnosis_n'],config['validation_reserved_n']
    cohorts = {'diagnosis':selected[:a],'validation_reserved':selected[a:a+b],'evaluation_reserved':selected[a+b:],
               'eligibility_count':len(eligible),'eligible_ids_hash':content_hash(eligible),
               'historical_reservation_counts':expected,'historical_union_hash':content_hash(sorted(union)),
               'generator':{'algorithm':'numpy.Generator(PCG64)','seed':config['seed'],'numpy':np.__version__}}
    parent_setup = None
    if selection_from is not None:
        parent = Path(selection_from).resolve()
        previous = read(parent/'plan.json')
        if (previous['plan_hash']!=content_hash({k:v for k,v in previous.items() if k!='plan_hash'}) or
                previous['config']!=config or read(parent/'cohorts.json')!=cohorts or (parent/'jobs').exists()):
            raise ValueError('selection handoff must preserve identical pre-outcome reservations')
        parent_setup = {'root':str(parent),'plan':identity(parent/'plan.json'),'cohorts':identity(parent/'cohorts.json'),
                        'scope':'same reservations after software-only setup hardening; zero prior assigned generations'}
    root.mkdir(parents=True)
    publish(root/'cohorts.json',cohorts)
    # Close all reservations before Gold is opened. Reserved future task text is
    # never exported to this serving root.
    publish(root/'selection-frozen.json',{'config':identity(config_path),'cohorts':identity(root/'cohorts.json'),
                                         'inputs':inputs,'before_gold':True})
    selected_tasks = [by_id[i] for i in cohorts['diagnosis']]
    _rows(root/'tasks.jsonl',selected_tasks)
    documents = DocumentStore(prepared/'documents.jsonl')
    doc_ids = sorted({d for t in selected_tasks for d in t['candidate_ids']})
    _rows(root/'documents.jsonl',(asdict(documents.get(d)) for d in doc_ids))
    view = {}
    gold_path = prepared/'gold/gold.jsonl'
    if identity(gold_path) != meta['files']['gold/gold.jsonl']:
        raise ValueError('Gold identity changed')
    for row in read_jsonl(gold_path):
        if row['task_id'] not in cohorts['diagnosis']:
            continue
        if row['task_id'] in view:
            raise ValueError('duplicate assigned Gold')
        candidates = [documents.get(d) for d in by_id[row['task_id']]['candidate_ids']]
        mapped = {}
        for title,index in row['supporting_facts']:
            matches = [d for d in candidates if d.title==title]
            if len(matches)!=1 or type(index) is not int or not 0<=index<len(matches[0].sentences):
                raise ValueError('ambiguous original supporting sentence mapping')
            mapped.setdefault(matches[0].doc_id,set()).add(index)
        if not mapped:
            raise ValueError('empty annotated support projection')
        view[row['task_id']] = {d:sorted(indices) for d,indices in mapped.items()}
    if set(view) != set(cohorts['diagnosis']):
        raise ValueError('assigned Gold incomplete')
    publish(root/'support-view.json',view)
    basic = read(historical/'artifacts/provenance/asset-manifest.json')
    assets = {'required':['reader','encoder'],'assets':{r:basic['assets'][r] for r in ('reader','encoder')}}
    verify_assets(assets)
    if (assets['assets']['reader']['revision']!=config['reader']['revision'] or
            assets['assets']['encoder']['revision']!=config['encoder_revision']):
        raise ValueError('asset revision mismatch')
    publish(root/'assets.json',assets)
    shutil.copyfile(config_path,root/'config.json')
    for p in sorted((source/'src/outcome_poc').rglob('*.py')) + [source/'requirements.lock',source/'pyproject.toml']:
        target = root/'source'/p.relative_to(source)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)
    (root/'source.diff').write_bytes(subprocess.check_output(['git','diff','--binary'],cwd=source))
    publish(root/'schedule.json',make_schedule(config,cohorts))
    denied = [str(historical/'data'),str(historical/'artifacts'),str(historical/'models/pinned/data'),
              str(historical/'src'),str(source/'src'),str(root/'scores')]
    probes = [str(gold_path),str(historical/'models/pinned/data/hotpot_dev_distractor_v1.json'),
              str(historical/'models/pinned/data/hotpot_train_v1.1.json'),str(source/'src/outcome_poc/scoring.py')]
    for prior in deny_roots:
        prior = Path(prior).resolve(strict=True)
        if root.is_relative_to(prior) or prior.is_relative_to(root):
            raise ValueError('denied prior root overlaps the new serving root')
        denied.append(str(prior))
        for name in ('support-view.json','documents.jsonl','tasks.jsonl'):
            if (prior/name).is_file():probes.append(str(prior/name))
    plan = {'root':str(root),'config':config,'config_identity':identity(config_path),'parent_setup':parent_setup,
            'freeze':{'boot_id':boot_identity(),'clock':clock_identity(),'settings':{'reader':config['reader']}},
            'gold_input':{'path':str(gold_path),'identity':identity(gold_path)},'denied_paths':denied,'denied_probes':probes,
            'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),
            'environment':environment_identity(),'prompt_hash':content_hash(ANSWER_SYSTEM),'files':inventory(root)}
    plan['plan_hash'] = content_hash(plan)
    publish(root/'plan.json',plan)
    verify(root)
    return plan


def index(root):
    from ..retrieval import EncoderBackend
    root = Path(root).resolve()
    verify(root)
    directory = root/'index-setup'
    if directory.exists():
        raise ValueError('index setup parent must be new; preserve all previous attempts')
    directory.mkdir()
    start = continuous_ns()
    try:
        with offline_network():
            assets = read(root/'assets.json')['assets']
            encoder = EncoderBackend(Path(assets['encoder']['local_path']))
            if encoder.identity != {k:assets['encoder'][k] for k in ('revision','snapshot_hash')}:
                raise ValueError('loaded encoder identity mismatch')
            docs = DocumentStore(root/'documents.jsonl')
            return build_new_index(directory,(docs.get(i) for i in sorted(docs.offsets)),encoder)
    finally:
        append_jsonl(root/'setup-attempts.jsonl',{'kind':'index_setup_envelope','start_ns':start,'stop_ns':continuous_ns(),
                         'clock_domain':'mach_continuous_time','includes':'encoder acquisition and nested physical index build'})

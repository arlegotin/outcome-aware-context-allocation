"""NEW privileged, single-use v3 preparation. No serving imports or inference."""
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import json,shutil,subprocess
import numpy as np

from ..assets import verify_assets
from ..data_runtime import DocumentStore
from ..followup.clock import boot_identity,clock_identity
from ..reader_probe.study import inventory,environment_identity
from ..schemas import Document
from ..storage import canonical_bytes,content_hash,read_jsonl,atomic_json
from .study import read,publish,identity,verify,make_schedule,READER,verify_files
from .study_v3 import is_scientific
from .prompts import registry
from .action_study_v4 import is_action
from .learning_study_v5 import is_learning
from .fresh import authenticated_reservations,historical_frame,retained_locations,validate_output_locations


def unused_id(path,protocol_id):
    if any(r['protocol_id']==protocol_id for r in read(path)['protocols']):
        raise ValueError('protocol identity already reserved; preserve every attempt')


def smoke_summary(root,plan_hash):
    directory=Path(root)/'scores';closure=read(directory/'closed.json')
    if closure['plan_hash']!=plan_hash or closure['assigned_jobs']!=4 or set(closure['files'])!={'scores.jsonl','summary.json'}:
        raise ValueError('native smoke score closure binding mismatch')
    verify_files({str(directory/name):value for name,value in closure['files'].items()})
    return read(directory/'summary.json')


def gate_locations(config):
    """Gate ancestry is mandatory; caller omissions cannot reopen retained roots."""
    fields=('reader_admission','action_headroom','native_smoke','asset_authority','historical_authority')
    roots=set();probes=set();bindings={};visited=set()
    pending=[config[k] for k in fields if config.get(k)]
    while pending:
        value=pending.pop()
        for proof in ('audit','resource_gate'):
            if proof not in value:continue
            audit=value[proof];path=Path(audit['path']).resolve(strict=True)
            if identity(path)!=audit['identity']:raise ValueError('gate audit/resource proof identity changed')
            roots.add(path.parent);probes.add(str(path))
            bindings.update({str(path.parent/name):expected for name,expected in inventory(path.parent).items()})
        root=Path(value['root']).resolve(strict=True)
        if root in visited:continue
        visited.add(root);plan=read(root/'plan.json')
        if plan['root']!=str(root) or plan['plan_hash']!=content_hash({k:v for k,v in plan.items() if k!='plan_hash'}):
            raise ValueError('gate plan root/identity mismatch')
        roots.add(root)
        # Bind closed gate evidence and its ancestry; serving skips these
        # privileged reads, while the launcher rechecks all bytes.
        bindings.update({str(root/name):expected for name,expected in inventory(root).items()})
        if 'gold_input' in plan:
            gold=Path(plan['gold_input']['path']).resolve();roots.add(gold.parent);probes.add(str(gold))
            # Preserve expected bytes without opening Gold before selection.
            bindings[str(gold)]=plan['gold_input']['identity']
        prior=plan.get('config',{})
        pending.extend(prior[k] for k in fields if prior.get(k))
    return sorted(roots),sorted(probes),bindings


def research_gate(config,source,N,eligible_hash):
    if config['purpose']=='authored-native-smoke':return
    if not {'precision','native_smoke','research_requirements'}<=config.keys():
        raise ValueError('prospective precision, research requirements and authenticated native smoke required')
    proposal=config['precision'];path=Path(proposal['path'])
    if identity(path)!=proposal['identity']:raise ValueError('prospective precision identity drift')
    forecast=read(path)
    target=next((r for r in forecast['research_target'] if r['n']==config['validation_n']),None)
    eligible=[r['n'] for r in forecast['research_target'] if r['monte_carlo_95_interval'][0]>=.80]
    req=config['research_requirements']
    if (not target or not eligible or min(eligible)!=config['validation_n'] or target['N']!=N or
            config.get('eligible_ids_hash')!=eligible_hash or
            req!={'strict_effect':.10,'answer_effect':.10,'joint_power_mc_lower_minimum':.80,
                  'quality_margin':0,'operational_requirements':None}):
        raise ValueError('prospective research effect/precision/frame mismatch')
    smoke=config['native_smoke'];root=Path(smoke['root'])
    if identity(root/'scores/closed.json')!=smoke['score_closure']:raise ValueError('native smoke closure identity drift')
    old=verify(root)
    from .scoring import closed_records
    closed_records(root)
    result=smoke_summary(root,old['plan_hash'])
    current={str(p.relative_to(source)):identity(p) for p in sorted((source/'src/outcome_poc').rglob('*.py'))+[source/'requirements.lock',source/'pyproject.toml']}
    if (old['config']['purpose']!='authored-native-smoke' or result['assigned_jobs']!=4 or
            any(a['strict_successes']!=2 for a in result['arms'].values()) or
            inventory(root/'source')!=current):
        raise ValueError('actual native known-answer smoke or tested source identity mismatch')


def _rows(path,rows):
    with Path(path).open('xb') as stream:
        for row in rows:stream.write(canonical_bytes(row)+b'\n')


def _authored(root,config,cohort_name='validation'):
    # Explicit invented known-answer documents; these are never benchmark cases.
    rows=[];gold=[];documents=[]
    for number,(name,answer) in enumerate((('Iris','violet'),('Lumen','amber'))):
        packet=[]
        for j in range(10):
            title=f'Authored {name} record {j}'
            sentence=f'{name} has the colour {answer}.' if j==0 else f'This is unrelated authored record {j} about stones.'
            doc=Document(content_hash([title,[sentence]]),title,[sentence],len(sentence));documents.append(asdict(doc));packet.append(doc.doc_id)
        i=f'authored-native-{name.lower()}'
        rows.append({'task_id':i,'split':'fit_extension','question':f'What colour does {name} have?','candidate_ids':packet})
        gold.append({'task_id':i,'answer':answer,'supporting_facts':[[f'Authored {name} record 0',0]]})
    if config.get('validation_n',config.get('development_n',config.get('fit_n',0)+config.get('holdout_n',0)))!=2:raise ValueError('authored smoke requires exactly two invented cases')
    _rows(root/'tasks.jsonl',rows);_rows(root/'documents.jsonl',documents)
    private=root.parent/(root.name+'-private-gold');private.mkdir(exist_ok=False)
    _rows(private/'gold.jsonl',gold)
    publish(root/'cohorts.json',{cohort_name:[r['task_id'] for r in rows],**({'learning_holdout':[]} if is_learning(config) else {}),'eligibility_count':2,
            'scope':'invented software smoke only; no benchmark or population claim'})
    return private/'gold.jsonl'


def prepare_scientific(root,config_path):
    # One repository-wide lock protects the complete read/select/append operation.
    # Never remove the lock inode: waiting preparers must see the same lock.
    import fcntl
    source=Path(__file__).resolve().parents[3]
    with (source/'experiments/.reservation-catalog.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:raise ValueError('reservation preparation already active') from error
        try:return _prepare_scientific(root,config_path)
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def _prepare_scientific(root,config_path):
    source=Path(__file__).resolve().parents[3];config_path=Path(config_path).resolve(strict=True)
    # Shared strict JSON loader forbids duplicate keys and nonfinite values.
    from ..data_runtime import _loads
    config=_loads(config_path.read_bytes());canonical_bytes(config)
    action=is_action(config);learning=is_learning(config)
    if not (is_scientific(config) or action or learning):raise ValueError('explicit scientific v3/v4 schema required')
    cohort_name='fit' if learning else 'development' if action else 'validation'
    n=config['fit_n']+config['holdout_n'] if learning else config['development_n' if action else 'validation_n']
    start=datetime.fromisoformat(config['started_utc']);deadline=datetime.fromisoformat(config['deadline_utc']);now=datetime.now(timezone.utc)
    reserve=config['reporting_reserve_seconds']
    if (start.tzinfo is None or deadline.tzinfo is None or not start<=now<deadline or
            type(reserve) not in (int,float) or reserve<=0 or
            (deadline-now).total_seconds()<config['native_budget_seconds']+reserve):
        raise ValueError('current execution window must cover frozen compute budget and reporting reserve')
    historical=Path(config['historical_checkout']).resolve(strict=True)
    catalog=source/'experiments/reservation-manifests.json';unused_id(catalog,config['protocol_id'])
    additional=authenticated_reservations(source,config['protocol_id'],config['reservation_catalog_identity'])
    gate_roots,gate_probes,gate_bindings=gate_locations(config)
    retained=retained_locations(source,historical,additional,[*config['retained_roots'],*gate_roots])
    root=validate_output_locations(root,retained)
    if root.exists():raise ValueError('new scientific root must not exist; preserve all attempts')
    inputs={};counts={};prepared=historical/'data/prepared'
    if config['purpose'] in {'reader-admission','action-headroom','routing-signal'}:
        prepared,tasks,eligible,inputs,counts=historical_frame(historical,additional,config['historical_reservation_identities'])
        if identity(prepared/'manifest.json')!=config['prepared_manifest_identity']:raise ValueError('prepared source manifest drift')
        if learning:
            from .learning_preparation_v5 import learning_gate
            learning_gate(config,source,len(eligible),content_hash(eligible))
        elif action:
            from .action_preparation_v4 import admission_gate
            admission_gate(config,source,len(eligible),content_hash(eligible))
        else:research_gate(config,source,len(eligible),content_hash(eligible))
        selected=np.random.Generator(np.random.PCG64(config['seed'])).permutation(len(eligible))[:n]
        if len(selected)!=n:raise ValueError('insufficient independent sampling frame')
        cohorts={cohort_name:[eligible[int(i)] for i in selected],'eligibility_count':len(eligible),
                'eligible_ids_hash':content_hash(eligible),'historical_reservation_counts':counts,
                'additional_reserved_ids':len(additional['reserved_ids']),
                'generator':{'algorithm':'numpy.Generator(PCG64)','seed':config['seed'],'numpy':np.__version__}}
        if learning:
            selected_ids=cohorts.pop(cohort_name)
            cohorts.update(fit=selected_ids[:config['fit_n']],learning_holdout=selected_ids[config['fit_n']:])
        root.mkdir(parents=True,exist_ok=False);publish(root/'cohorts.json',cohorts)
        # Append only. Never rewrite a historical record/status or reopen an ID.
        old=read(catalog);frozen=identity(catalog)
        publish(root/'reservation-catalog-before.json',old)
        record={'protocol_id':config['protocol_id'],'status':'reserved','cohorts_path':str(root/'cohorts.json'),
                'cohorts_identity':identity(root/'cohorts.json'),'groups':({'fit':config['fit_n'],'learning_holdout':config['holdout_n']} if learning else {cohort_name:n})}
        if identity(catalog)!=frozen:raise ValueError('concurrent reservation catalog changed')
        atomic_json(catalog,{**old,'protocols':[*old['protocols'],record]})
        publish(root/'reservation-catalog-after.json',read(catalog))
        inputs.pop(str(catalog),None)  # Frozen copies above permit future append-only reservations.
        publish(root/'selection-frozen.json',{'config':identity(config_path),'cohorts':identity(root/'cohorts.json'),
                'inputs':inputs,'before_gold':True,'assigned_generations':0})
        chosen=set(cohorts['fit']+cohorts['learning_holdout'] if learning else cohorts[cohort_name]);active=[t for t in tasks if t['task_id'] in chosen]
        if any(t['split']!='fit_extension' for t in active):raise ValueError('fresh cohort split mismatch')
        _rows(root/'tasks.jsonl',active);documents=DocumentStore(prepared/'documents.jsonl')
        _rows(root/'documents.jsonl',(asdict(documents.get(d)) for d in sorted({d for t in active for d in t['candidate_ids']})))
        gold_path=prepared/'gold/gold.jsonl'
        if identity(gold_path)!=read(prepared/'manifest.json')['files']['gold/gold.jsonl']:raise ValueError('Gold identity mismatch')
    else:
        if learning:
            from .learning_preparation_v5 import learning_gate
            learning_gate(config,source,2,None)
        elif action:
            from .action_preparation_v4 import admission_gate
            admission_gate(config,source,2,None)
        root.mkdir(parents=True,exist_ok=False);gold_path=_authored(root,config,cohort_name)
    basic_path=historical/'artifacts/provenance/asset-manifest.json';basic=read(basic_path)
    assets={'required':['reader','encoder'],'assets':{k:basic['assets'][k] for k in ('reader','encoder')}}
    authority=config['asset_authority'];archive=Path(authority['root']);prior_plan=read(archive/'plan.json')
    if (prior_plan['plan_hash']!=authority['plan_hash'] or
            prior_plan['plan_hash']!=content_hash({k:v for k,v in prior_plan.items() if k!='plan_hash'}) or
            identity(archive/'assets.json')!=prior_plan['files']['assets.json'] or
            read(archive/'assets.json')!=assets):
        raise ValueError('independently authenticated pinned asset bindings changed')
    if config['purpose'] in {'reader-admission','action-headroom','routing-signal'} and read(Path(config['native_smoke']['root'])/'assets.json')!=assets:
        raise ValueError('native smoke cannot admit different asset/template/tokenizer bytes')
    if (action or learning) and read(Path(config['reader_admission']['root'])/'assets.json')!=assets:
        raise ValueError('action study cannot change the admitted reader/encoder assets')
    verify_assets(assets)
    if assets['assets']['reader']['revision']!=READER['revision'] or assets['assets']['encoder']['revision']!='5c38ec7c405ec4b44b94cc5a9bb96e735b38267a':raise ValueError('pinned asset revision mismatch')
    publish(root/'assets.json',assets);publish(root/'support-view.json',{});publish(root/'prompt-conditions.json',registry())
    shutil.copyfile(config_path,root/'config.json')
    for path in sorted((source/'src/outcome_poc').rglob('*.py'))+[source/'requirements.lock',source/'pyproject.toml']:
        target=root/'source'/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    (root/'source.diff').write_bytes(subprocess.check_output(['git','diff','--binary'],cwd=source))
    publish(root/'schedule.json',make_schedule(config,read(root/'cohorts.json')))
    denied={str(source),str(historical/'src'),str(historical/'data'),str(historical/'artifacts'),
            str(historical/'models/pinned/data'),str(root/'scores'),str(gold_path.parent)}
    denied.update(str(r) for r in retained if r!=historical)
    probes={str(gold_path),str(source/'src/outcome_poc/scoring.py'),str(historical/'data/prepared/tasks.jsonl'),
            str(historical/'models/pinned/data/hotpot_train_v1.1.json'),str(historical/'models/pinned/data/hotpot_dev_distractor_v1.json')}
    for prior in retained:
        for name in ('support-view.json','scores/scores.jsonl','source/src/outcome_poc/scoring.py','src/outcome_poc/scoring.py'):
            if (prior/name).is_file() and prior!=historical:probes.add(str(prior/name))
    probes.update(gate_probes)
    inputs.update(gate_bindings)
    if learning:
        for field in ('precision','analysis_protocol'):
            value=config[field];inputs[str(Path(value['path']).resolve(strict=True))]=value['identity']
    inputs[str(basic_path)]=identity(basic_path)
    plan={'root':str(root),'config':config,'config_identity':identity(config_path),
          'freeze':{'boot_id':boot_identity(),'clock':clock_identity(),'settings':{'reader':config['reader']}},
          'gold_input':{'path':str(gold_path),'identity':identity(gold_path)},
          'denied_paths':sorted(denied),'denied_probes':sorted(probes),'input_identities':inputs,
          'prompt_conditions':registry(),'source_snapshot_hash':content_hash(inventory(root/'source')),
          'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip(),
          'environment':environment_identity(),'files':inventory(root)}
    plan['plan_hash']=content_hash(plan);publish(root/'plan.json',plan);verify(root)
    return {'root':str(root),'plan_hash':plan['plan_hash'],'assigned_jobs':len(make_schedule(config,read(root/'cohorts.json'))),'source_snapshot_hash':plan['source_snapshot_hash']}


def index_bounded(root):
    """NEW v4 setup: enclose validation, process ownership, index and durable receipt."""
    import os
    from ..followup.clock import continuous_ns
    from ..followup.study import verify_index
    from .allocation_study import run_bounded_process
    from .index_budget import validate_index_budget
    start=continuous_ns();root=Path(root).resolve(strict=True)
    plan=verify(root)
    if not (is_action(plan['config']) or is_learning(plan['config'])):raise ValueError('bounded index command requires explicit v4/v5 study')
    if boot_identity()!=plan['freeze']['boot_id'] or clock_identity()!=plan['freeze']['clock']:
        raise ValueError('bounded index clock/boot changed')
    cap=plan['config']['index_budget_seconds']
    control=root/'index-supervision';control.mkdir(exist_ok=False)
    command=[plan['config']['native_interpreter'],'-B','-m','outcome_poc.reader_recovery','index','--root',str(root)]
    publish(control/'started.json',{'plan_hash':plan['plan_hash'],'boot_id':boot_identity(),'clock':clock_identity(),
            'start_ns':start,'budget_seconds':cap,'command':command})
    remaining=cap-(continuous_ns()-start)/1e9
    if remaining<=0:raise TimeoutError('index validation exhausted setup cap')
    process=run_bounded_process(command,{**os.environ,'PYTHONPATH':str(root/'source/src'),
            'PYTHONDONTWRITEBYTECODE':'1','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'},control,remaining)
    if process.returncode:raise RuntimeError('bounded index subprocess failed; evidence retained')
    verify_index(root/'index-setup')
    publish(control/'receipt.json',{'plan_hash':plan['plan_hash'],'index_seal':identity(root/'index-setup/index-seal.json'),
            'parent_closure':identity(control/'native-parent-closure.json')})
    stop=continuous_ns()
    publish(control/'complete.json',{'start_ns':start,'stop_ns':stop,'seconds':(stop-start)/1e9,
            'receipt':identity(control/'receipt.json')})
    validate_index_budget(root,plan)
    return {'status':'bounded index complete','seconds':(stop-start)/1e9,'cap_seconds':cap}

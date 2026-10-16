"""NEW authored software fixtures; these are not benchmark observations."""
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from outcome_poc.storage import content_hash


def test_unknown_protocol_cannot_fall_through_to_diagnosis_schedule():
    from outcome_poc.reader_recovery.study import make_schedule
    with pytest.raises(ValueError, match='protocol'):
        make_schedule({'protocol_id':'renamed-reader-study','seed':7}, {'diagnosis':['a']})


def test_fresh_schedule_has_its_own_schema_and_balanced_assignment():
    from outcome_poc.reader_recovery.study import make_schedule, group_arms
    config={'protocol_id':'authored-independent-01','study_kind':'independent-reader-validation-v2',
            'schema_version':2,'seed':7,'validation_n':4,'repetitions':1,
            'arms':['baseline','evidence-first']}
    cohorts={'validation':['a','b','c','d']}
    roster=make_schedule(config,cohorts)
    assert group_arms(config)=={'natural':('baseline','evidence-first')}
    assert len(roster)==8 and len({j['job_id'] for j in roster})==8
    assert sorted(j['arm'] for j in roster[::2])==['baseline']*2+['evidence-first']*2
    for a,b in zip(roster[::2],roster[1::2]):
        assert a['task_id']==b['task_id'] and {a['arm'],b['arm']}=={'baseline','evidence-first'}
        assert a['budget']==b['budget']==10
    changed={**config,'protocol_id':'authored-independent-02'}
    assert {j['job_id'] for j in make_schedule(changed,cohorts)}.isdisjoint(j['job_id'] for j in roster)
    for bad in ({**config,'schema_version':1},{**config,'study_kind':'renamed'},
                {**config,'protocol_id':'reader-recovery-v1'}):
        with pytest.raises(ValueError):make_schedule(bad,cohorts)
    for ids in (['a','a','b','c'],['a','b']):
        with pytest.raises(ValueError):make_schedule(config,{'validation':ids})


def test_allocation_renderer_uses_exact_existing_candidate_and_preserves_legacy():
    from outcome_poc.generation import render_prompt
    from outcome_poc.reader_recovery.prompts import render_condition
    from test_reader_recovery import Template
    from retrieval_helpers import document
    doc=document('Authored badge',['Noise.','The badge is violet.'])
    args=('Badge colour?',[doc],{'D8':doc.doc_id},Template())
    baseline=render_prompt(*args)
    assert render_prompt(*args,recipe='baseline-v1')==baseline
    assert render_prompt(*args,recipe='evidence-first-v1')==render_condition(*args,{doc.doc_id:[0,1]},'evidence-first')
    with pytest.raises(ValueError):render_prompt(*args,recipe='unregistered')


@pytest.mark.parametrize('budget',[2,5,10])
def test_forecast_renders_only_the_assigned_budget(budget):
    from outcome_poc.reader_recovery.runtime import forecast_prompts
    from outcome_poc.generation import render_prompt,prompt_identity
    from test_reader_recovery import Template
    from retrieval_helpers import document
    docs=[document(f'Authored {i}',[f'Sentence {i}.']) for i in range(10)]
    class Tokens(Template):
        def encode(self,text,**kwargs):
            assert kwargs=={'add_special_tokens':False}
            return list(text.encode())
    tokenizer=Tokens();ranking=[SimpleNamespace(doc_id=d.doc_id) for d in docs]
    tasks={'a':{'question':'Which?','candidate_ids':[d.doc_id for d in docs]}}
    roster=[dict(job_id='j',task_id='a',reader_condition='evidence-first',budget=budget)]
    forecast=forecast_prompts(roster,tasks,SimpleNamespace(get=lambda i:next(d for d in docs if d.doc_id==i)),
                              SimpleNamespace(rank=lambda *args:ranking),tokenizer,20000,256)
    prompt=render_prompt('Which?',docs[:budget],{f'D{i}':d.doc_id for i,d in enumerate(docs)},tokenizer,recipe='evidence-first-v1')
    assert forecast['jobs']['j']=={'prompt_hash':prompt_identity(prompt,tokenizer),'prompt_tokens':len(prompt.encode())}


def test_paid_serving_and_prefix_targets_bind_recipe(tmp_path):
    from outcome_poc import runner
    from outcome_poc.policies import PostOutcomePolicy
    from outcome_poc.reader_recovery.prompts import EVIDENCE_FIRST_SYSTEM
    from serving_helpers import fixture_runtime
    runtime,job,_=fixture_runtime(tmp_path)
    runtime.config={**runtime.config,'reader_recipe':'evidence-first-v1'}
    from test_reader_recovery import Template
    runtime.reader.backend.tokenizer=Template()
    original=runtime.reader.backend.generate;paid=[]
    def generate(prompt,request,*,rendered=False,prefix_cache=None):
        assert json.loads(prompt)[0]['content']==EVIDENCE_FIRST_SYSTEM
        assert request.prompt_hash==content_hash({'prompt':prompt,'chat_template':runtime.reader.backend.tokenizer.chat_template})
        assert json.loads(prefix_cache['target_prompt'])[0]['content']==EVIDENCE_FIRST_SYSTEM
        paid.append(request)
        return original(prompt,replace(request,cache_mode='none'),rendered=rendered)
    runtime.reader.backend.generate=generate
    policy=PostOutcomePolicy(None,{'threshold_mode':'always_ten','threshold':None})
    prediction=runner.execute_job({**job,'policy':policy,'cache_mode':'within_query_prefix'},runtime,tmp_path/'run')
    assert prediction.generation_calls==len(paid)==2
    assert len([e for e in runner.load_events(tmp_path/'run') if e.role.startswith('generation:')])==2
    ids=prediction.evidence_ids
    candidate=runner._bound_action_signature(job['task'],runtime,ids)
    runtime.config={k:v for k,v in runtime.config.items() if k!='reader_recipe'}
    assert runner._bound_action_signature(job['task'],runtime,ids)!=candidate


def test_fresh_preparation_rejects_output_and_ledger_parent_aliases(tmp_path):
    from outcome_poc.reader_recovery.fresh import validate_output_locations
    source=tmp_path/'source';source.mkdir()
    retained=tmp_path/'retained';retained.mkdir()
    alias=tmp_path/'alias';alias.symlink_to(retained,target_is_directory=True)
    validate_output_locations(tmp_path/'new-run',[source,retained])
    for root in (source/'run',retained/'run',alias/'run',tmp_path):
        with pytest.raises(ValueError,match='overlap'):
            validate_output_locations(root,[source,retained])
    with pytest.raises(ValueError,match='overlap'):
        validate_output_locations(tmp_path/'new-run',[source,retained],ledger_parents=[alias])


def test_fresh_catalog_authentication_cannot_accept_empty_or_changed_exclusions(tmp_path):
    from outcome_poc.reader_recovery.fresh import authenticated_reservations
    from outcome_poc.followup.study import publish,identity
    path=tmp_path/'experiments/reservation-manifests.json'
    publish(path,{'format_version':1,'protocols':[]})
    with pytest.raises(ValueError,match='reservation'):
        authenticated_reservations(tmp_path,'authored-new',identity(path))
    with pytest.raises(ValueError,match='identity'):
        authenticated_reservations(tmp_path,'authored-new',{'sha256':'0'*64,'bytes':0})


def test_native_allocation_refuses_candidate_before_complete_timing_integration():
    from outcome_poc.reader_recipes import require_native_allocation_support
    require_native_allocation_support({})
    require_native_allocation_support({'reader_recipe':'baseline-v1'})
    with pytest.raises(ValueError,match='continuous.*timing'):
        require_native_allocation_support({'reader_recipe':'evidence-first-v1'})


@pytest.mark.parametrize('stage',['collection','tuning'])
def test_recipe_reaches_every_paid_development_call(tmp_path,stage):
    from outcome_poc.reader_recovery.prompts import EVIDENCE_FIRST_SYSTEM
    from outcome_poc.generation import SUFFICIENCY_SYSTEM
    from serving_helpers import fixture_runtime
    from test_reader_recovery import Template
    runtime,job,_=fixture_runtime(tmp_path)
    runtime.config={**runtime.config,'reader_recipe':'evidence-first-v1'}
    runtime.reader.backend.tokenizer=Template()
    paid=[];original=runtime.reader.backend.generate
    def generate(prompt,request,*,rendered=False):
        system=json.loads(prompt)[0]['content']
        assert system==(SUFFICIENCY_SYSTEM if request.role=='judge' else EVIDENCE_FIRST_SYSTEM)
        paid.append(request)
        return original(prompt,request,rendered=rendered)
    runtime.reader.backend.generate=generate
    task=replace(job['task'],split='fit' if stage=='collection' else 'tune')
    config={'assigned_ids':[task.task_id],'run_dir':str(tmp_path/stage)}
    if stage=='collection':
        from outcome_poc.collection import collect_raw_pairs
        result=collect_raw_pairs([task],runtime,config)
        assert len(paid)==2
    else:
        from outcome_poc.select import tune
        result=tune({**config,'tasks':[task],'models':{},'test_fixture':True},runtime)
        assert len(paid)==14 and sum(p.role=='judge' for p in paid)==1
    assert (tmp_path/stage/'predictions.closed.json').is_file()
    assert result['generation_calls']==len(paid)


def fresh_fixture(tmp_path,monkeypatch):
    """A complete metadata world made only of invented questions/documents."""
    from datetime import datetime,timedelta,timezone
    from outcome_poc.reader_recovery import fresh
    from outcome_poc.reader_recovery.study import READER,FRESH_KIND
    from outcome_poc.followup.study import publish,identity
    from outcome_poc.storage import append_jsonl
    from retrieval_helpers import document
    history=tmp_path/'history';prepared=history/'data/prepared'
    prepared.mkdir(parents=True)
    ids=[f'authored-{i:04}' for i in range(1130)]
    docs=[document(f'Invented {i}',[f'Invented note {i}.']) for i in range(10)]
    for i in ids:
        question=f'Invented question {i}?'
        append_jsonl(prepared/'tasks.jsonl',dict(task_id=i,split='fit_extension',question=question,candidate_ids=[d.doc_id for d in docs]))
        append_jsonl(prepared/'duplicate-membership.jsonl',dict(source='train',member_ids=[i],representative_id=i,
            disposition='retained',group_key_hash=content_hash(question.casefold())))
    for doc in docs:append_jsonl(prepared/'documents.jsonl',doc)
    publish(prepared/'development-reservations.json',{'pilot':ids[:448],'fit':[],'tune':[]})
    names=('tasks.jsonl','documents.jsonl','duplicate-membership.jsonl','development-reservations.json')
    publish(prepared/'manifest.json',{'files':{n:identity(prepared/n) for n in names}})
    publish(history/'configs/reader-quality-comparison.json',{'old_metadata':[],'prior_cohorts':['followup.json'],
                                                            'citation_cohorts':'citation.json'})
    publish(history/'followup.json',{'diagnosis':ids[448:512],'calibration_reserved':ids[512:544],
                                    'calibration':ids[512:520],'headroom':ids[544:672]})
    publish(history/'citation.json',{'diagnosis':ids[672:736],'comparison':ids[736:992]})
    publish(history/'artifacts/runs/reader-quality-comparison-v1/cohorts.json',{'confirmation':ids[992:1120]})
    public=tmp_path/'public';records=[]
    for offset,protocol in enumerate(('reader-recovery-v1','reader-evidence-first-v1')):
        cohort=tmp_path/f'retained-{offset}'/'cohorts.json'
        publish(cohort,{'consumed':[ids[1120+2*offset]],'reserved':[ids[1121+2*offset]]})
        records.append({'protocol_id':protocol,'status':'complete','cohorts_path':str(cohort),
                        'cohorts_identity':identity(cohort),'groups':{'consumed':1,'reserved':1}})
    catalog=public/'experiments/reservation-manifests.json'
    publish(catalog,{'format_version':1,'protocols':records})
    actual=fresh.authenticated_reservations
    monkeypatch.setattr(fresh,'authenticated_reservations',lambda source,protocol,expected:actual(public,protocol,expected))
    assets={}
    for role,revision in (('reader',READER['revision']),('encoder','5c38ec7c405ec4b44b94cc5a9bb96e735b38267a')):
        local=history/'assets'/role;local.mkdir(parents=True);(local/'LICENSE').write_text('MIT license, authored fixture')
        assets[role]={'status':'ok','kind':'model','license':'mit','revision':revision,'local_path':str(local),
                      'files':{'LICENSE':identity(local/'LICENSE')}}
    publish(history/'artifacts/provenance/asset-manifest.json',{'required':['reader','encoder'],'assets':assets})
    now=datetime.now(timezone.utc)
    config={'schema_version':2,'study_kind':FRESH_KIND,'protocol_id':'authored-independent-01','seed':11,
            'validation_n':4,'repetitions':1,'arms':['baseline','evidence-first'],'reader':READER,
            'execution_mode':'preparation-only','native_generation_calls':0,'semantic_retries':0,
            'cache_mode':'none','reuse_indexes':[],'historical_checkout':str(history),'retained_roots':[],
            'reservation_catalog_identity':identity(catalog),'prepared_manifest_identity':identity(prepared/'manifest.json'),
            'started_utc':(now-timedelta(minutes=1)).isoformat(),'deadline_utc':(now+timedelta(minutes=30)).isoformat(),
            'reporting_reserve_seconds':60,
            'historical_reservation_identities':{str(history/n):identity(history/n) for n in (
                'configs/reader-quality-comparison.json','followup.json','citation.json',
                'artifacts/runs/reader-quality-comparison-v1/cohorts.json')}}
    path=tmp_path/'config.json';publish(path,config)
    return config,path,prepared,catalog,records


def test_fresh_preparation_authenticates_frame_freezes_split_and_refuses_native(tmp_path,monkeypatch):
    from outcome_poc.reader_recovery.fresh import prepare_fresh_validation
    from outcome_poc.reader_recovery.study import verify
    from outcome_poc.reader_recovery.runtime import launch
    from outcome_poc.followup.study import read
    config,path,prepared,catalog,records=fresh_fixture(tmp_path,monkeypatch)
    root=tmp_path/'fresh-run';result=prepare_fresh_validation(root,path)
    assert result['eligible_N']==6 and result['assigned_jobs']==8 and result['native_generation_calls']==0
    assert result['scientific_execution'] is False
    cohorts=read(root/'cohorts.json')
    assert set(cohorts['validation'])<=set(f'authored-{i:04}' for i in range(1124,1130))
    assert all(t['split']=='fit_extension' for t in [json.loads(s) for s in (root/'tasks.jsonl').read_text().splitlines()])
    assert not (root/'gold').exists() and read(root/'support-view.json')=={}
    verify(root)
    with pytest.raises(ValueError,match='preparation-only'):launch(root,'natural')
    assert not (root/'stages').exists()
    (root/'schedule.json').write_text('[]')
    with pytest.raises(ValueError,match='schedule'):verify(root)


@pytest.mark.parametrize('corruption',['missing_private','private_bytes','catalog_bytes','prepared_bytes','output_alias','expired','manifest_identity','historical_cohort'])
def test_fresh_preparation_negative_controls_preserve_original_metadata(tmp_path,monkeypatch,corruption):
    from outcome_poc.reader_recovery.fresh import prepare_fresh_validation
    config,path,prepared,catalog,records=fresh_fixture(tmp_path,monkeypatch)
    root=tmp_path/'fresh-run'
    if corruption=='missing_private':__import__('pathlib').Path(records[0]['cohorts_path']).unlink()
    if corruption=='private_bytes':__import__('pathlib').Path(records[0]['cohorts_path']).write_text('{}')
    if corruption=='catalog_bytes':catalog.write_text('{}')
    if corruption=='prepared_bytes':(prepared/'tasks.jsonl').write_text('')
    if corruption=='output_alias':
        root=tmp_path/'alias';root.symlink_to(prepared.parent,target_is_directory=True)
    if corruption=='expired':
        config['deadline_utc']='2020-01-01T00:00:00+00:00';path.write_text(json.dumps(config))
    if corruption=='historical_cohort':
        prior=__import__('pathlib').Path(config['historical_checkout'])/'followup.json'
        cohort=json.loads(prior.read_text());cohort['diagnosis'][0]='authored-1124';prior.write_text(json.dumps(cohort))
    if corruption=='manifest_identity':
        config['prepared_manifest_identity']={'sha256':'0'*64,'bytes':0};path.write_text(json.dumps(config))
    with pytest.raises((ValueError,OSError)):prepare_fresh_validation(root,path)
    if corruption!='output_alias':assert not root.exists()


def test_same_recipe_name_with_changed_system_cannot_resume_a_cached_job(tmp_path,monkeypatch):
    from outcome_poc import runner,reader_recipes
    from serving_helpers import fixture_runtime
    runtime,job,_=fixture_runtime(tmp_path)
    runtime.config={**runtime.config,'reader_recipe':'evidence-first-v1'}
    runner.execute_job(job,runtime,tmp_path/'run')
    recipe=reader_recipes.reader_recipe('evidence-first-v1')
    monkeypatch.setattr(reader_recipes,'_RECIPES',{'evidence-first-v1':replace(recipe,system=recipe.system+' Changed source.')})
    with pytest.raises(ValueError,match='identity changed'):
        runner.execute_job(job,runtime,tmp_path/'run')


def test_public_retention_archives_also_protect_output_parents(tmp_path):
    from outcome_poc.reader_recovery.fresh import retained_locations,validate_output_locations
    from outcome_poc.followup.study import publish
    source=tmp_path/'source';history=tmp_path/'history';history.mkdir()
    archived=tmp_path/'archived-checkout';archive=archived/'artifacts/runs/private.tar.gz'
    archive.parent.mkdir(parents=True);archive.write_bytes(b'authored private archive')
    earlier=tmp_path/'earlier-study';earlier.mkdir()
    publish(source/'experiments/old/evidence/retention.json',{'private_archive_path':str(archive),'source_roots':[str(earlier)]})
    locations=retained_locations(source,history,{'identities':{}},[])
    for output in (archived/'new-run',earlier/'child',archive.parent):
        with pytest.raises(ValueError,match='overlap'):validate_output_locations(output,locations)


def test_rescore_output_cannot_mutate_other_retained_evidence(tmp_path):
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('read_only_recovery_audit',Path(__file__).resolve().parents[1]/'tools/audit_recovery_run.py')
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    root=tmp_path/'run';root.mkdir()
    historical=tmp_path/'history';historical.mkdir()
    (root/'plan.json').write_text(json.dumps({'config':{'historical_checkout':str(historical)},'denied_paths':[],
        'gold_input':{'path':str(historical/'data/prepared/gold/gold.jsonl')}}))
    output=historical/'new-audit'
    with pytest.raises(ValueError,match='overlap'):tool.audit(root,output)
    assert not output.exists()


def test_legacy_native_entrypoints_refuse_ignored_continuous_clock_flag():
    from outcome_poc.reader_recipes import require_native_allocation_support
    with pytest.raises(ValueError,match='continuous|timing|fresh'):
        require_native_allocation_support({'reader_recipe':'baseline-v1','request_timing':'complete-continuous-v3'})

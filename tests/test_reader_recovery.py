"""Authored fixtures for the new diagnostic path; never benchmark results."""
from dataclasses import replace
import json

import pytest

from outcome_poc.generation import parse_answer
from outcome_poc.schemas import ReaderResult
from retrieval_helpers import document


class Template:
    chat_template = 'authored template'
    def apply_chat_template(self, messages, **kwargs):
        assert kwargs == {'tokenize':False,'add_generation_prompt':True}
        self.messages = messages
        return json.dumps(messages)


def test_sentence_projection_preserves_original_identity_indices_and_aliases():
    from outcome_poc.reader_recovery.evidence import render_view, parse_view
    doc = document('Invented vessel', ['Noise.', 'Its name is Iris.', 'More noise.', 'Iris is violet.'])
    alias = {'D7':doc.doc_id}
    tokenizer = Template()
    rendered = render_view('What color is the vessel?', [doc], alias, tokenizer, {doc.doc_id:[1,3]})
    assert '[1] Its name is Iris.' in rendered and '[3] Iris is violet.' in rendered
    assert '[0]' not in rendered and '[2]' not in rendered and 'D7 | Invented vessel' in rendered
    assert doc.sentences == ['Noise.', 'Its name is Iris.', 'More noise.', 'Iris is violet.']
    raw = '{"citations":[{"doc_id":"D7","sentence_index":3}],"answer":"violet"}'
    result = ReaderResult(raw,None,[],'ok',1,1,[1],[2],'stop')
    assert parse_view(result,[doc],alias,{doc.doc_id:[1,3]}).citations == [(doc.doc_id,3)]
    bad = replace(result,raw_output=raw.replace('index":3','index":0'))
    assert parse_view(bad,[doc],alias,{doc.doc_id:[1,3]}).status == 'invalid_citation'


@pytest.mark.parametrize('view', [{}, {'unknown':[0]}, None, 'bad', {'placeholder':[]}, {'placeholder':[True]}, {'placeholder':[0,0]}, {'placeholder':[99]}])
def test_malformed_sentence_views_fail_before_rendering(view):
    from outcome_poc.reader_recovery.evidence import render_view
    doc = document('Authored', ['One.'])
    if isinstance(view,dict) and 'placeholder' in view:
        view = {doc.doc_id:view['placeholder']}
    with pytest.raises(ValueError):
        render_view('Question?', [doc], {'D4':doc.doc_id}, Template(), view)


def test_natural_view_is_byte_identical_to_original_renderer():
    from outcome_poc.reader_recovery.evidence import render_view
    from outcome_poc.generation import render_prompt
    doc = document('Authored', ['One.', 'Two.'])
    assert render_view('Question?', [doc], {'D4':doc.doc_id}, Template(), {doc.doc_id:[0,1]}) == render_prompt('Question?', [doc], {'D4':doc.doc_id}, Template())


def test_reservations_exclude_latest_unexecuted_and_normalized_duplicate_closure():
    from outcome_poc.reader_recovery.reservations import eligible_ids
    from outcome_poc.storage import content_hash
    from outcome_poc.followup.study import normalized
    def task(i,q):return {'task_id':i,'question':q,'split':'fit_extension'}
    tasks = [task('a','One'),task('b','Two'),task('c',' THREE '),task('d','four')]
    membership = [dict(source='train',member_ids=[t['task_id']],representative_id=t['task_id'],
                       disposition='retained',group_key_hash=content_hash(normalized(t['question']))) for t in tasks]
    membership.append(dict(source='train',member_ids=['unexecuted','alias'],representative_id='alias',
                           disposition='excluded',group_key_hash=content_hash(normalized('three'))))
    assert eligible_ids(tasks,membership,{'a','unexecuted'}) == ['b','d']


def test_diagnostic_summary_all_zero_and_noop_cannot_claim_efficiency():
    from outcome_poc.reader_recovery.analysis import summarize
    rows = [dict(task_id=str(i),arm='2',joint_em=0,answer_em=0,seconds=1.,status='abstain') for i in range(3)]
    result = summarize(rows)
    assert result['arms']['2']['Q'] == 0 and result['arms']['2']['mean_T'] == 1
    assert result['arms']['2']['R'] is None and result['arms']['2']['R_reason'] == 'zero_successes'
    assert result['claims'] == {'reader_improvement':False,'allocation_improvement':False,'operational_usefulness':False}
    with pytest.raises(ValueError):summarize([])


@pytest.mark.parametrize('protocol_id',['reader-recovery-v1','reader-evidence-first-v1'])
def test_real_diagnostic_transactions_complete_before_gold_and_fresh_scoring(tmp_path,monkeypatch,protocol_id):
    from pathlib import Path
    import shutil
    from outcome_poc.reader_recovery import runtime,scoring
    from outcome_poc.reader_recovery.study import GROUP_ARMS,READER,make_schedule,group_arms
    from outcome_poc.storage import canonical_bytes,content_hash,append_jsonl
    from outcome_poc.followup.study import publish,identity
    from outcome_poc.reader_probe.study import inventory
    from outcome_poc.followup.runtime import session_accounting
    from outcome_poc.retrieval import Retrieval
    from outcome_poc.followup.study import build_new_index
    from retrieval_helpers import Encoder,store
    from followup_helpers import Backend
    root = tmp_path/'authored-run'
    root.mkdir()
    docs = [document(f'Authored {i}',['Iris is violet.','Unused sentence.']) for i in range(10)]
    documents = store(root,docs)
    task = dict(task_id='authored',split='fit_extension',question='What color is Iris?',candidate_ids=[d.doc_id for d in docs])
    (root/'tasks.jsonl').write_bytes(canonical_bytes(task)+b'\n')
    setup = root/'index-setup'
    index_start = runtime.continuous_ns()
    setup.mkdir()
    build_new_index(setup,docs,Encoder())
    append_jsonl(root/'setup-attempts.jsonl',{'start_ns':index_start,'stop_ns':runtime.continuous_ns()})
    retrieval = Retrieval(setup/'index',documents,Encoder())
    first = retrieval.rank(task['question'],task['candidate_ids'])[0].doc_id
    publish(root/'support-view.json',{'authored':{first:[0]}})
    publish(root/'assets.json',{'assets':{'reader':{'revision':'authored','snapshot_hash':'authored'}}})
    validation = protocol_id=='reader-evidence-first-v1'
    cohorts = ({'validation':['authored'],'prior_diagnosis':['exposed-diagnosis']} if validation else
               {'diagnosis':['authored'],'validation_reserved':['untouched-validation']})
    publish(root/'cohorts.json',{**cohorts,'evaluation_reserved':['untouched-evaluation'],'eligibility_count':100})
    gold = tmp_path/'authored-gold.jsonl'
    gold.write_bytes(canonical_bytes({'task_id':'authored','answer':'violet','supporting_facts':[[documents.get(first).title,0]]})+b'\n')
    settings = dict(READER)
    config = {'protocol_id':protocol_id,'reader':settings,'diagnosis_n':1,'validation_reserved_n':1,
              'validation_n':1,'prior_diagnosis_n':1,
              'evaluation_reserved_n':1,'seed':20261015}
    publish(root/'schedule.json',make_schedule(config,json.loads((root/'cohorts.json').read_text())))
    plan = {'root':str(root),'config':config,
        'freeze':{'boot_id':'authored'},
        # Real preparation freezes inputs before the separate physical index
        # stage. Its seal must be checked separately before opening Gold.
        'files':{k:v for k,v in inventory(root).items() if not k.startswith('index-setup/') and k!='setup-attempts.jsonl'},
        'gold_input':{'path':str(gold),'identity':identity(gold)},'source_commit':'authored'}
    if validation:
        from outcome_poc.reader_recovery.prompts import registry
        plan['prompt_conditions'] = registry()
    plan['plan_hash'] = content_hash(plan)
    publish(root/'plan.json',plan)
    import outcome_poc
    shutil.copytree(Path(outcome_poc.__file__).parent,root/'source/src/outcome_poc',ignore=shutil.ignore_patterns('__pycache__'))
    roster = json.loads((root/'schedule.json').read_text())
    monkeypatch.setattr(runtime,'boot_identity',lambda:'authored')
    admission_ticks = {}
    for group in group_arms(config):
        stage = root/'stages'/group
        stage.mkdir(parents=True)
        start = runtime.continuous_ns()
        state = {'session':group,'plan_hash':plan['plan_hash'],'boot_id':'authored','start_ns':start}
        state_path = stage/f'session-start-{group}.json'
        publish(state_path,state)
        if validation:
            class FixtureTokenizer(type(Backend.tokenizer)):
                def encode(self,text,**kwargs):return [1,2]
            forecast_start = runtime.continuous_ns()
            forecast = runtime.forecast_prompts([j for j in roster if j['group']==group],
                {'authored':task},documents,retrieval,FixtureTokenizer(),8192,256)
            publish(stage/'render-forecast.json',{**forecast,'start_ns':forecast_start,'stop_ns':runtime.continuous_ns(),
                    'boot_id':'authored','clock_domain':'mach_continuous_time'})
        for job in roster:
            if job['group']==group:
                def admission():
                    assert (root/'jobs'/job['job_id']/'started.json').is_file()
                    admission_ticks[job['job_id']] = runtime.continuous_ns()
                runtime.execute(root,plan,job,task,documents,retrieval,Backend(),'authored-session',
                                admission=admission if validation else None)
        stop = runtime.continuous_ns()
        publish(stage/f'session-accounting-{group}.json',{'session':group,'plan_hash':plan['plan_hash'],'boot_id':'authored',
            'start_identity':identity(state_path),'start_ns':start,'stop_ns':stop,'stop_lower_bound_ns':stop,
            'stop_upper_bound_ns':stop,'timing_status':'exact'})
    # Even complete individual jobs cannot open Gold before both group seals.
    moved = gold.with_suffix('.hidden')
    gold.rename(moved)
    with pytest.raises(FileNotFoundError):scoring.score(root)
    assert not (root/'scores').exists()
    moved.rename(gold)
    for group in group_arms(config):
        stage = root/'stages'/group
        selected = [j for j in roster if j['group']==group]
        publish(stage/'closed.json',{'plan_hash':plan['plan_hash'],'assigned_jobs':len(selected),
            'job_ids_hash':content_hash([j['job_id'] for j in selected]),'session_accounting':session_accounting(root,group,plan,require_closed=True),
            'jobs':{j['job_id']:inventory(root/'jobs'/j['job_id']) for j in selected},'stage_files':inventory(stage)})
    result = scoring.score(root)
    assert result['assigned_jobs'] == (2 if validation else 5) and result['assigned_questions'] == 1
    assert all(r['strict_successes']==1 and r['answer_successes']==1 and r['R']>0 for r in result['arms'].values())
    before = (root/'scores/scores.jsonl').read_bytes()
    assert scoring.score(root) == result
    assert (root/'scores/scores.jsonl').read_bytes() == before
    if validation:
        assert result['reader_validation']['admitted'] is False
        for job in roster:
            boundary=json.loads((root/'stages/natural/requests'/f"{job['job_id']}.json").read_text())
            assert boundary['start_ns']<=admission_ticks[job['job_id']]<=boundary['stop_ns']
        # Even a newly sealed stage cannot authenticate a forecast that differs
        # from the paid prompt. Reject before trying to open missing Gold.
        forecast_path=root/'stages/natural/render-forecast.json'
        closure_path=root/'stages/natural/closed.json'
        original_forecast,original_closure=forecast_path.read_bytes(),closure_path.read_bytes()
        altered=json.loads(original_forecast)
        altered['jobs'][roster[0]['job_id']]['prompt_hash']='0'*64
        forecast_path.write_bytes(canonical_bytes(altered))
        closure=json.loads(original_closure)
        closure['stage_files']={k:v for k,v in inventory(root/'stages/natural').items() if k!='closed.json'}
        closure_path.write_bytes(canonical_bytes(closure))
        missing=gold.with_suffix('.hidden');gold.rename(missing)
        with pytest.raises(ValueError,match='forecast'):scoring.score(root)
        missing.rename(gold)
        forecast_path.write_bytes(original_forecast);closure_path.write_bytes(original_closure)
    # Authentic job closure does not authorize Gold if the actual index changed.
    vectors = setup/'index/vectors.f32'
    original_vectors = vectors.read_bytes()
    vectors.write_bytes(original_vectors+b'tampered')
    moved = gold.with_suffix('.hidden')
    gold.rename(moved)
    with pytest.raises(ValueError,match='(identity|hash|index)'):
        scoring.score(root)
    moved.rename(gold)
    vectors.write_bytes(original_vectors)
    frozen_scorer = root/'source/src/outcome_poc/reader_recovery/scoring.py'
    original = frozen_scorer.read_bytes()
    frozen_scorer.write_bytes(original+b'\n# authored drift\n')
    with pytest.raises(ValueError,match='source drift'):scoring.score(root)
    frozen_scorer.write_bytes(original)
    (root/'stages/natural/extra').write_text('unbound telemetry')
    with pytest.raises(ValueError,match='telemetry'):scoring.score(root)
    # A newly hashed but semantically truncated assignment is still invalid.
    from outcome_poc.reader_recovery.study import verify
    (root/'schedule.json').write_text('[]')
    altered = json.loads((root/'plan.json').read_text())
    altered['files']['schedule.json'] = identity(root/'schedule.json')
    altered['plan_hash'] = content_hash({k:v for k,v in altered.items() if k!='plan_hash'})
    (root/'plan.json').write_bytes(canonical_bytes(altered))
    with pytest.raises(ValueError,match='schedule'):verify(root)


def test_expired_window_precedes_launcher_writes_and_paid_acquisition(tmp_path,monkeypatch):
    from outcome_poc.reader_recovery import runtime
    monkeypatch.setattr(runtime,'verify',lambda root:{'config':{'deadline_utc':'2000-01-01T00:00:00+00:00'}})
    root = tmp_path/'unstarted'
    with pytest.raises(TimeoutError,match='window'):runtime.launch(root,'natural')
    assert not root.exists()


def test_paid_boundary_rechecks_after_rendering_and_reserves_post_sync():
    from datetime import datetime,timedelta,timezone
    from types import SimpleNamespace
    from outcome_poc.reader_recovery.runtime import WindowedBackend
    class Uncalled:
        startup_timeout = 120.
        def generate(self,*a,**k):raise AssertionError('paid call admitted without full remaining bounds')
    deadline = (datetime.now(timezone.utc)+timedelta(seconds=180)).isoformat()
    backend = WindowedBackend(Uncalled(),{'config':{'deadline_utc':deadline}})
    with pytest.raises(TimeoutError):backend.generate('authored prompt',SimpleNamespace(timeout_seconds=120.))

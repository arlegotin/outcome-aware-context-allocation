"""Official metric and finite-population checks with authored observations."""
import pytest
from test_reader_study_preparation import prepared_study
from test_reader_study_runtime import ready,Counters
from outcome_poc.followup.study import read,identity


def test_complete_scores_seal_and_fresh_process_reproduce(ready):
    import subprocess,sys
    from outcome_poc.reader_study import runtime,scoring
    root,_,encoder=ready
    runtime.run_stage(root,'development',backend_factory=lambda _:Counters(),encoder_factory=encoder)
    rows=scoring.score_stage(root,'development')
    assert len(rows)==96 and sum(r['calls'] for r in rows)==96
    assert all(r['reader_id'] in {'qwen4b-instruct','qwen14b-nonthinking'} for r in rows)
    score=identity(root/'scores/development/scores.jsonl')
    process=subprocess.run([sys.executable,'-m','outcome_poc.reader_study','score','--root',str(root),'--stage','development'],capture_output=True,text=True)
    assert process.returncode==0,process.stderr
    assert identity(root/'scores/development/scores.jsonl')==score
    assert scoring.admit(root)['decision']=='defer'
    assert not (root/'confirmation-admission.json').exists()
    report=scoring.report(root)
    assert report['stages']['confirmation']['status']=='reserved_unexecuted'
    assert report['stages']['development']['assigned_observations']==96


def test_missing_stage_never_opens_gold(tmp_path,monkeypatch):
    from outcome_poc.reader_study import scoring
    monkeypatch.setattr(scoring,'read_jsonl',lambda _:pytest.fail('Gold opened'))
    with pytest.raises(ValueError,match='incomplete'):scoring.score_stage(tmp_path,'development')


@pytest.mark.parametrize('mutation',['prediction','gold','scorer'])
def test_score_seal_rejects_changed_inputs(ready,mutation,monkeypatch):
    from outcome_poc.reader_study import runtime,scoring
    root,plan,encoder=ready
    runtime.run_stage(root,'development',backend_factory=lambda _:Counters(),encoder_factory=encoder)
    scoring.score_stage(root,'development')
    if mutation=='prediction':next((root/'leaves/development').glob('*/jobs/*/terminal.json')).write_text('{}')
    elif mutation=='gold':__import__('pathlib').Path(plan['gold_input']['path']).write_text('{}')
    else:monkeypatch.setattr(scoring,'scorer_identity',lambda:{'changed':True})
    with pytest.raises(ValueError):scoring.score_stage(root,'development')


def authored_rows():
    rows=[]
    for i in range(4):
        for reader in ('qwen4b-instruct','qwen14b-nonthinking'):
            for arm in ('2','10'):
                success=int(i<2 if reader=='qwen4b-instruct' else i<3)
                rows.append(dict(task_id=str(i),reader_id=reader,scientific_stage='confirmation',arm=arm,repetition=0,
                    ordinal=len(rows),status='ok',answer_em=success,joint_em=success,support_em=success,
                    answer_f1=success,joint_f1=success,support_f1=success,support_precision=success,support_recall=success,
                    seconds=2.,active_seconds=2.,drift_seconds=0.,calls=1,prompt_tokens=5,generated_tokens=2,empty=False,truncated=False))
    return rows


def test_paired_orientation_zero_harm_and_census_and_complete_denominators():
    from outcome_poc.reader_study.scoring import summarize
    rows=authored_rows();result=summarize(rows,'confirmation',88587)
    pair=result['paired']['10']['joint_em']
    assert pair['rescue_count']==1 and pair['harm_count']==0 and pair['difference']==.25
    assert pair['harm_bounds'][1]>0 and pair['tail_alpha']==.0125
    assert result['paired']['2']['answer_em']['tail_alpha']==.00625
    census=summarize(rows,'confirmation',4)['paired']['10']['joint_em']
    assert census['ci']==[.25,.25]
    assert result['cells']['qwen4b-instruct/10']['total_seconds']==8
    assert result['oracle']['qwen14b-nonthinking']['union_success']==3
    with pytest.raises(ValueError):summarize(rows[:-1],'confirmation',88587)
    with pytest.raises(ValueError):summarize(rows+[rows[0]],'confirmation',88587)


def test_asymmetric_reader_scores_invalid_citations_and_frozen_screen(ready,monkeypatch):
    import json,re
    from dataclasses import replace
    from outcome_poc.reader_study import runtime,scoring
    root,_,encoder=ready
    class Answers(Counters):
        def __init__(self,reader):super().__init__();self.reader=reader
        def generate(self,prompt,request,**kwargs):
            result=super().generate(prompt,request,**kwargs)
            text=json.loads(prompt)[1]['content']
            match=re.search(r'(D\d+) \| Invented lantern 0\n',text)
            raw={'answer':'authored violet','citations':[{'doc_id':match[1] if match else 'D999','sentence_index':0}]}
            if self.reader=='qwen4b-instruct':raw['citations'][0]['sentence_index']=999
            return replace(result,raw_output=json.dumps(raw))
    runtime.run_stage(root,'development',backend_factory=lambda f:Answers(f.reader_id),encoder_factory=encoder)
    rows=scoring.score_stage(root,'development');by={r: [x for x in rows if x['reader_id']==r] for r in ('qwen4b-instruct','qwen14b-nonthinking')}
    assert all(r['joint_em']==0 for r in by['qwen4b-instruct'])
    assert any(r['status']=='invalid_citation' for r in by['qwen4b-instruct'])
    assert sum(r['joint_em'] for r in by['qwen14b-nonthinking'] if r['arm']=='10')==16
    assert sum(r['answer_em'] for r in by['qwen4b-instruct'])==48
    # Authored in-process execution never masquerades as native healthy admission.
    assert scoring.admit(root)['decision']=='defer'
    forged={'decision':'admit'}
    (root/'confirmation-admission.json').write_text(json.dumps(forged))
    with pytest.raises(ValueError,match='admission'):runtime.validate_admission(root)

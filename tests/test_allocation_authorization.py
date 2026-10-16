"""NEW exact fresh-stage authorization, with original task splits preserved."""
from dataclasses import replace
import pytest
from serving_helpers import fixture_runtime


def test_frozen_fresh_assignment_authorizes_only_exact_task_policy_recipe_and_stage(tmp_path):
    from outcome_poc.allocation_authorization import FrozenStage,authorize_job
    runtime,job,_=fixture_runtime(tmp_path)
    task=replace(job['task'],split='fit_extension')
    job={**job,'task':task,'attempt':1,'_run_dir':tmp_path/'run',
         '_attempt_dir':tmp_path/'run/jobs/job/attempt-1','stage':'fit'}
    job['_attempt_dir'].mkdir(parents=True);(job['_attempt_dir']/'started.json').write_text('{}')
    session=FrozenStage.bind('plan','fit',[job],runtime.config)
    runtime._fresh_execution=session
    authorize_job(task,job['policy'],runtime,job)
    for changed in ({**job,'stage':'tune'},{**job,'job_id':'other'},
                    {**job,'task':replace(task,question='Changed?')},
                    {**job,'task':replace(task,split='fit')}):
        with pytest.raises(ValueError):authorize_job(changed['task'],changed['policy'],runtime,changed)
    runtime.config={**runtime.config,'reader_recipe':'evidence-first-v1'}
    with pytest.raises(ValueError):authorize_job(task,job['policy'],runtime,job)
    assert task.split=='fit_extension'


def test_fresh_authorization_cannot_replace_protected_confirmation(tmp_path):
    from outcome_poc.allocation_authorization import FrozenStage
    runtime,job,_=fixture_runtime(tmp_path)
    job={**job,'stage':'confirmation','task':replace(job['task'],split='protected')}
    with pytest.raises(ValueError,match='protected|stage'):
        FrozenStage.bind('plan','confirmation',[job],runtime.config)

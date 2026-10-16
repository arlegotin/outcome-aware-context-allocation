"""Annotation-free, immutable authorization for separately frozen fresh stages."""
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .storage import content_hash
from .reader_recipes import recipe_settings


def _job_hash(job):
    policy=job['policy']
    return content_hash({'task':job['task'],'policy_id':policy.policy_id,
        'policy_config':getattr(policy,'config',None),'k':getattr(policy,'k',None),
        'requires_draft':getattr(policy,'requires_draft',False),'requires_judge':getattr(policy,'requires_judge',False),
        **{k:job.get(k) for k in ('job_id','stage','run_id','protocol_hash','mode','cache_mode','caller_cap','repetition_id')}})


@dataclass(frozen=True)
class FrozenStage:
    plan_hash: str
    stage: str
    jobs: object
    config_hash: str

    @classmethod
    def bind(cls,plan_hash,stage,jobs,config):
        ids=[j['job_id'] for j in jobs]
        if not plan_hash or stage not in {'natural','pilot','fit','tune','headroom'} or not ids or len(ids)!=len(set(ids)):
            raise ValueError('invalid fresh frozen stage assignment')
        # Protected confirmation keeps its existing independently verified Execution.
        split='fit_extension'
        if any(j['stage']!=stage or j['task'].split!=split for j in jobs):
            raise ValueError('fresh stage requires its actual original Task.split')
        return cls(plan_hash,stage,MappingProxyType({j['job_id']:_job_hash(j) for j in jobs}),
                   content_hash({**config,**recipe_settings(config)}))


def authorize_job(task,policy,runtime,job):
    session=getattr(runtime,'_fresh_execution',None)
    if not isinstance(session,FrozenStage):raise ValueError('verified fresh stage required')
    if (job.get('stage')!=session.stage or job.get('task')!=task or job.get('policy') is not policy or
            session.jobs.get(job.get('job_id'))!=_job_hash(job) or
            content_hash({**runtime.config,**recipe_settings(runtime.config)})!=session.config_hash):
        raise ValueError('fresh exact assignment/policy/recipe/stage authorization mismatch')
    root=Path(job.get('_run_dir','/nonexistent')).resolve()
    attempt=job.get('attempt')
    if type(attempt) is not int or attempt<1:raise ValueError('fresh durable assigned attempt required')
    expected=root/'jobs'/job['job_id']/f'attempt-{attempt}'
    if (Path(job.get('_attempt_dir','/nonexistent')).resolve()!=expected or
            not (expected/'started.json').is_file() or (root/'predictions.closed.json').exists()):
        raise ValueError('fresh durable assigned attempt required')

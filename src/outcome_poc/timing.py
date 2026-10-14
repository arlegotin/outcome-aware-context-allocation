"""Synchronized enclosing service and nested component events, never additive twice."""
from contextlib import contextmanager
import time

from .schemas import CostEvent, validate_record
from .storage import content_hash


class TimingLedger:
    def __init__(self, job: dict, policy_id: str, clock=time.perf_counter_ns):
        self.job, self.policy_id, self.clock = job, policy_id, clock
        self.events = []

    def event(self, role, start, stop, *, status='ok', result=None, source=None, resources=None):
        event = CostEvent(content_hash([self.job['job_id'], self.job.get('attempt',1),
                                      len(self.events), role]),
                          self.job['run_id'], self.job['task'].task_id, self.policy_id,
                          role, start, stop, (stop-start)/1e9,
                          result.prompt_tokens if result else 0,
                          result.generated_tokens if result else 0,
                          self.job.get('cache_mode','none'), source,
                          (resources or {}).get('peak_mlx_bytes'),
                          (resources or {}).get('rss_bytes'),
                          (resources or {}).get('swap_used_bytes'),self.job.get('attempt',1),status,
                          result.telemetry.get('clean_prefill_seconds',0.) if result else 0.)
        validate_record(event)
        self.events.append(event)
        return event

    @contextmanager
    def component(self, role):
        start = self.clock()
        try:
            yield
        except BaseException:
            self.event(role,start,self.clock(),status='infra_error')
            raise
        else:
            self.event(role,start,self.clock())

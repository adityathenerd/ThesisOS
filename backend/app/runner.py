from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from .errors import ServiceError


class JobRunner(Protocol):
    def submit(self, task_id: str) -> None: ...
    def close(self) -> None: ...


class InProcessRunner:
    """One local worker. Persisted status is durable; execution itself is not.

    Startup marks unfinished jobs failed. A mandate rerun deduplicates cases.
    Use a durable worker adapter later without changing HTTP task contracts.
    """

    def __init__(self, state, provider, assessments, max_cases):
        self.state, self.provider, self.assessments = state, provider, assessments
        self.max_cases = max_cases
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="thesisos")

    def submit(self, task_id):
        try:
            self.executor.submit(self._execute, task_id)
        except RuntimeError:
            self.state.fail_task(task_id, "Local runner is shutting down. Retry after restart.")
            raise ServiceError("provider_unavailable", "Local runner is unavailable", 503, True)

    def _execute(self, task_id):
        try:
            task = self.state.start_task(task_id)
            mandate = self.state.mandate(task.mandate_id)
            candidates = self.provider.discover(mandate, self.max_cases, task_id=task.id)
            if len(candidates) > self.max_cases:
                raise ServiceError("provider_unavailable", "Provider exceeded the bounded candidate limit", 502)
            self.assessments.complete_discovery(task_id, candidates)
        except ServiceError as error:
            self.state.fail_task(task_id, error.message)
        except Exception:
            # Do not retain exception/provider payloads in user-visible task errors.
            self.state.fail_task(task_id, "Local task failed. Saved candidates/observations and accepted assessments remain; rerun to retry pending work.")

    def close(self):
        self.executor.shutdown(wait=True)

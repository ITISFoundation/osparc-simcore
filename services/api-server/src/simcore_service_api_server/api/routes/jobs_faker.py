import asyncio
import functools
import hashlib
import random
import uuid as uuidlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from faker import Faker

from ...models.schemas.solvers import JobInput, JobOutput, JobState, TaskStates

fake = Faker()


@dataclass
class JobsFaker:
    # Fakes jobs managements for a given user
    #
    # TODO: preload JobsFaker configuration emulating a particular scenario (e.g. all jobs failed, ...)
    #

    job_info: Dict[UUID, Dict[str, Any]] = field(
        default_factory=dict
    )  # solver_id, inputs_sha, job_id

    job_states: Dict[UUID, JobState] = field(default_factory=dict)
    job_inputs: Dict[UUID, List[JobInput]] = field(default_factory=dict)
    job_tasks: Dict[UUID, asyncio.Future] = field(default_factory=dict)
    job_outputs: Dict[UUID, List[JobOutput]] = field(default_factory=dict)

    def iter_jobs(self, solver_id: Optional[UUID] = None):
        if solver_id:
            for job in self.job_info.values():
                if job["solver_id"] == str(solver_id):
                    yield job
        else:
            for job in self.job_info.values():
                yield job

    def create_job(self, solver_id: UUID, inputs: List[JobInput]) -> Dict:
        sha = hashlib.sha256(
            " ".join(input.json() for input in inputs).encode("utf-8")
        ).hexdigest()

        # TODO: check if job exists already?? Do not consider date??
        job_id = compose_job_id(solver_id, sha, datetime.utcnow())

        job = dict(
            job_id=str(job_id),
            inputs_sha=sha,
            solver_id=str(solver_id),
        )
        self.job_info[job_id] = job
        self.job_inputs[job_id] = inputs
        return job

    def start_job(self, job_id: UUID) -> JobState:
        # why not getting inputs from here?
        inputs = self.job_inputs[job_id]

        state = self.job_states.get(job_id)
        if not state:
            state = JobState(
                status=TaskStates.UNDEFINED, progress=0, submitted_at=datetime.now()
            )
            task = asyncio.ensure_future(self._start_job_task(job_id, state, inputs))
            self.job_tasks[job_id] = task

        return state

    async def _start_job_task(self, job_id, job_state, inputs):
        # TODO: this should feel like a
        # TODO: how to cancel?
        try:
            self.job_states[job_id] = job_state
            await asyncio.sleep(random.randint(1, 10))

            job_state.status = TaskStates.PENDING
            await asyncio.sleep(random.randint(1, 10))

            job_state.status = TaskStates.RUNNING
            print("running with ", inputs)
            job_state.started_at = datetime.now()
            await asyncio.sleep(random.randint(1, 10))

            job_state.status = random.choice([TaskStates.SUCCESS, TaskStates.FAILED])
            job_state.progress = 100
            job_state.stopped_at = datetime.now()

            if job_state.status == TaskStates.SUCCESS:
                print("produced outputs")

                # TODO: return it
                # if file, upload
                return []
        except asyncio.CancelledError:
            if job_state.status != TaskStates.SUCCESS:
                job_state.status = TaskStates.FAILED
                return None

    def stop_job(self, job_id) -> Dict:
        job = self.job_info[job_id]
        task = self.job_tasks[job_id]
        task.cancel()  # not sure it will actually task.cancelling
        return job


the_fake_impl = JobsFaker()


# HELPERS ------------

NAMESPACE_JOB_KEY = uuidlib.UUID("ca7bdfc4-08e8-11eb-935a-ac9e17b76a71")


@functools.lru_cache()
def compose_job_id(solver_id: UUID, inputs_sha: str, created_at: str) -> UUID:
    # FIXME: this is a temporary solution. Should be image id

    return uuidlib.uuid3(NAMESPACE_JOB_KEY, f"{solver_id}:{inputs_sha}:{created_at}")

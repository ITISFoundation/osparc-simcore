import asyncio
import functools
import hashlib
import logging
import random
import uuid as uuidlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from ...models.schemas.solvers import JobInput, JobOutput, JobStatus, TaskStates

logger = logging.getLogger(__name__)

NAMESPACE_JOB_KEY = uuidlib.UUID("ca7bdfc4-08e8-11eb-935a-ac9e17b76a71")


@functools.lru_cache()
def compose_job_id(solver_id: UUID, inputs_sha: str, created_at: str) -> UUID:
    # FIXME: this is a temporary solution. Should be image id

    return uuidlib.uuid3(NAMESPACE_JOB_KEY, f"{solver_id}:{inputs_sha}:{created_at}")


@dataclass
class JobsFaker:
    # Fakes jobs managements for a given user
    #
    # TODO: preload JobsFaker configuration emulating a particular scenario (e.g. all jobs failed, ...)
    #

    job_info: Dict[UUID, Dict[str, Any]] = field(
        default_factory=dict
    )  # solver_id, inputs_sha, job_id

    job_status: Dict[UUID, JobStatus] = field(default_factory=dict)
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
        # TODO: validate inputs against solver definition

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

    def start_job(self, job_id: UUID) -> JobStatus:
        # why not getting inputs from here?
        inputs = self.job_inputs[job_id]

        job_status = self.job_status.get(job_id)
        if not job_status:
            job_status = JobStatus(
                job_id=job_id,
                state=TaskStates.UNDEFINED,
                progress=0,
                submitted_at=datetime.utcnow(),
            )
            self.job_status[job_id] = job_status
            self.job_tasks[job_id] = asyncio.ensure_future(
                self._start_job_task(job_id, inputs)
            )

        return self.job_status[job_id]

    async def _start_job_task(self, job_id, inputs):
        MOCK_PULLING_TIME = 1, 2
        MOCK_PENDING_TIME = 1, 3
        MOCK_RUNNING_TIME = 1, 5 + len(inputs)

        # TODO: this should feel like a
        # TODO: how to cancel?

        job_status = self.job_status[job_id]

        try:
            await asyncio.sleep(random.randint(*MOCK_PULLING_TIME))

            job_status.state = TaskStates.PENDING
            logger.info(job_status)

            await asyncio.sleep(random.randint(*MOCK_PENDING_TIME))

            # -------------------------------------------------
            job_status.state = TaskStates.RUNNING
            job_status.timestamp("started")
            logger.info(job_status)

            job_status.progress = 0
            for n in range(100):
                await asyncio.sleep(random.randint(*MOCK_RUNNING_TIME) / 100.0)
                job_status.progress = n + 1

            # NOTE: types of solvers
            #  - all outputs at once or output completion
            #  - can pause and resume or not
            #

            # -------------------------------------------------
            job_status.state = random.choice([TaskStates.SUCCESS, TaskStates.FAILED])
            job_status.progress = 100
            job_status.timestamp("stopped")
            logger.info(job_status)

            if job_status.state == TaskStates.SUCCESS:
                # TODO: return it
                # if file, upload
                self.job_outputs[job_id] = []
        except asyncio.CancelledError:
            if job_status.state != TaskStates.SUCCESS:
                job_status.state = TaskStates.FAILED
                job_status.timestamp("stopped")
                self.job_outputs.pop(job_id, None)

    def stop_job(self, job_id) -> Dict:
        job = self.job_info[job_id]
        task = self.job_tasks[job_id]
        task.cancel()  # not sure it will actually task.cancelling
        return job


the_fake_impl = JobsFaker()

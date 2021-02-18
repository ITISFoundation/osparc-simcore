"""
    Fakes the implementation of some some kind of queueing and
    scheduling of jobs

"""
import asyncio
import hashlib
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterator, List
from uuid import UUID

from ...models.schemas.jobs import Job, JobInput, JobOutput, JobStatus, TaskStates

logger = logging.getLogger(__name__)


@dataclass
class JobsFaker:
    # Fakes jobs managements for a given user
    #
    # TODO: preload JobsFaker configuration emulating a particular scenario (e.g. all jobs failed, ...)
    #

    jobs: Dict[UUID, Job] = field(default_factory=dict)
    job_status: Dict[UUID, JobStatus] = field(default_factory=dict)
    job_inputs: Dict[UUID, List[JobInput]] = field(default_factory=dict)
    job_tasks: Dict[UUID, asyncio.Future] = field(default_factory=dict)
    job_outputs: Dict[UUID, List[JobOutput]] = field(default_factory=dict)

    def job_values(self, solver_id: str = None) -> Iterator[Job]:
        if solver_id:
            for job in self.jobs.values():
                if job.runner_name == solver_id:
                    yield job
        else:
            for job in self.jobs.values():
                yield job

    def create_job(self, solver_id: str, inputs: List[JobInput]) -> Job:
        # TODO: validate inputs against solver definition
        inputs_checksum = hashlib.sha256(
            " ".join(input.json() for input in inputs).encode("utf-8")
        ).hexdigest()

        # TODO: check if job exists already?? Do not consider date??
        job = Job.create_now(solver_id, inputs_checksum)

        self.jobs[job.id] = job
        self.job_inputs[job.id] = inputs
        return job

    def start_job(self, job_id: UUID) -> JobStatus:
        # check job was created?
        job = self.jobs[job_id]

        # why not getting inputs from here?
        inputs = self.job_inputs[job.id]

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
            await asyncio.sleep(random.randint(*MOCK_PULLING_TIME))  # nosec

            job_status.state = TaskStates.PENDING
            logger.info(job_status)

            await asyncio.sleep(random.randint(*MOCK_PENDING_TIME))  # nosec

            # -------------------------------------------------
            job_status.state = TaskStates.RUNNING
            job_status.timestamp("started")
            logger.info(job_status)

            job_status.progress = 0
            for n in range(100):
                await asyncio.sleep(random.randint(*MOCK_RUNNING_TIME) / 100.0)  # nosec
                job_status.progress = n + 1

            # NOTE: types of solvers
            #  - all outputs at once or output completion
            #  - can pause and resume or not
            #

            # -------------------------------------------------
            done_states = [TaskStates.SUCCESS, TaskStates.FAILED]
            job_status.state = random.choice(done_states)  # nosec
            job_status.progress = 100
            job_status.timestamp("stopped")
            logger.info(job_status)

            # TODO: temporary A fixed output MOCK
            # TODO: temporary writes error in value!
            if job_status.state == TaskStates.SUCCESS:
                self.job_outputs[job_id] = [
                    JobOutput(
                        name="Temp",
                        type="number",
                        title="Resulting Temperature",
                        value=33,
                        job_id=job_id,
                    ),
                ]
            else:
                # TODO: some kind of error
                self.job_outputs[job_id] = [
                    JobOutput(
                        name="Temp",
                        type="string",
                        title="Resulting Temperature",
                        value="ERROR: simulation diverged",
                        job_id=job_id,
                    )
                ]

        except asyncio.CancelledError:

            logging.debug("Task for job %s was cancelled", job_id)
            job_status.state = TaskStates.FAILED
            job_status.timestamp("stopped")
            self.job_outputs[job_id] = [
                JobOutput(
                    name="Temp",
                    type="string",
                    title="Resulting Temperature",
                    value="ERROR: Cancelled",
                    job_id=job_id,
                )
            ]

    def stop_job(self, job_id) -> Job:
        job = self.jobs[job_id]
        try:
            task = self.job_tasks[job_id]
            task.cancel()  # not sure it will actually task.cancelling
        except KeyError:
            logger.debug("Stopping job {job_id} that was never started")
        return job


the_fake_impl = JobsFaker()

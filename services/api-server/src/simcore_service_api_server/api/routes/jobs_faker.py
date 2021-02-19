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
from typing import Callable, Dict, Iterator, List
from uuid import UUID

from fastapi import HTTPException
from starlette import status

from ...models.api_resources import RelativeResourceName
from ...models.schemas.jobs import Job, JobInput, JobOutput, JobStatus, TaskStates
from ...models.schemas.solvers import SolverKeyId, VersionStr

logger = logging.getLogger(__name__)


JobName = RelativeResourceName


@dataclass
class JobsFaker:
    # Fakes jobs managements for a given user
    #
    # TODO: preload JobsFaker configuration emulating a particular scenario (e.g. all jobs failed, ...)
    #

    jobs: Dict[JobName, Job] = field(default_factory=dict)
    job_status: Dict[UUID, JobStatus] = field(default_factory=dict)
    job_inputs: Dict[UUID, List[JobInput]] = field(default_factory=dict)
    job_tasks: Dict[UUID, asyncio.Future] = field(default_factory=dict)
    job_outputs: Dict[UUID, List[JobOutput]] = field(default_factory=dict)

    def job_values(self, solver_name: str = None) -> Iterator[Job]:
        if solver_name:
            for job in self.jobs.values():
                if job.runner_name == solver_name:
                    yield job
        else:
            for job in self.jobs.values():
                yield job

    def create_job(self, solver_name: str, inputs: List[JobInput]) -> Job:
        # TODO: validate inputs against solver definition
        inputs_checksum = hashlib.sha256(
            " ".join(input.json() for input in inputs).encode("utf-8")
        ).hexdigest()

        # TODO: check if job exists already?? Do not consider date??
        job = Job.create_now(solver_name, inputs_checksum)

        self.jobs[job.mame] = job
        self.job_inputs[job.id] = inputs
        return job

    def start_job(self, job_name: JobName) -> JobStatus:
        # check job was created?
        job = self.jobs[job_name]

        # why not getting inputs from here?
        inputs = self.job_inputs[job.id]

        job_status = self.job_status.get(job.id)
        if not job_status:
            job_status = JobStatus(
                job_id=job.id,
                state=TaskStates.UNDEFINED,
                progress=0,
                submitted_at=datetime.utcnow(),
            )
            self.job_status[job.id] = job_status
            self.job_tasks[job.id] = asyncio.ensure_future(
                self._start_job_task(job.id, inputs)
            )

        return self.job_status[job.id]

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

    def stop_job(self, job_name) -> Job:
        job = self.jobs[job_name]
        try:
            task = self.job_tasks[job.id]
            task.cancel()  # not sure it will actually task.cancelling
        except KeyError:
            logger.debug("Stopping job {job_id} that was never started")
        return job


the_fake_impl = JobsFaker()


# */jobs/*  API fake implementations


async def list_all_jobs_impl(
    url_for: Callable,
):
    """ List of all jobs created by user """
    return [
        job.copy(
            update={
                "url": url_for("get_job", job_id=job.id),
                "solver_url": url_for(
                    "get_solver_release",
                    solver_key=job.solver_key,
                    version=job.solver_version,
                ),
                "outputs_url": url_for("list_job_outputs", job_id=job.id),
            }
        )
        for job in the_fake_impl.job_values()
    ]


async def list_jobs_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    url_for: Callable,
):
    solver_resource_name = f"solvers/{solver_key}/releases/{version}"
    return [
        job.copy(
            update={
                "url": url_for("get_job", job_id=job.id),
                "solver_url": url_for(
                    "get_solver_release", solver_key=solver_key, version=version
                ),
                "outputs_url": url_for("list_job_outputs", job_id=job.id),
            }
        )
        for job in the_fake_impl.job_values(solver_resource_name)
    ]


async def create_job_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    inputs: List[JobInput],
    url_for: Callable,
):
    """Creates a job for a solver with given inputs.

    NOTE: This operation does **not** start the job
    """
    # TODO: validate inputs against solver specs
    # TODO: create a unique identifier of job based on solver_id and inputs

    job = the_fake_impl.create_job(f"solvers/{solver_key}/releases/{version}", inputs)
    return job.copy(
        update={
            "url": url_for("get_job", job_id=job.id),
            "solver_url": url_for(
                "get_solver_release", solver_key=solver_key, version=version
            ),
            "outputs_url": url_for("list_job_outputs", job_id=job.id),
        }
    )


async def get_job_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    url_for: Callable,
):
    try:
        job = the_fake_impl.jobs[job_id]
        return job.copy(
            update={
                "url": url_for("get_job", job_id=job.id),
                "solver_url": url_for(
                    "get_solver_release",
                    solver_key=solver_key,
                    version=version,
                ),
                "outputs_url": url_for("list_job_outputs", job_id=job.id),
            }
        )

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job {job_id} does not exists"
        ) from err


async def start_job_impl(solver_key: SolverKeyId, version: VersionStr, job_id: UUID):
    try:
        job_state = the_fake_impl.start_job(job_id)
        return job_state

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job {job_id} does not exists"
        ) from err


async def stop_job_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    url_for: Callable,
):
    try:
        job = the_fake_impl.stop_job(job_id)
        return job.copy(
            update={
                "url": url_for("get_job", job_id=job.id),
                "solver_url": url_for(
                    "get_solver_release",
                    solver_key=solver_key,
                    version=version,
                ),
                "outputs_url": url_for("list_job_outputs", job_id=job.id),
            }
        )

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job {job_id} does not exists"
        ) from err


async def inspect_job_impl(solver_key: SolverKeyId, version: VersionStr, job_id: UUID):
    try:
        state = the_fake_impl.job_status[job_id]
        return state

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job {job_id} does not exists"
        ) from err


async def list_job_outputs_impl(
    solver_key: SolverKeyId, version: VersionStr, job_id: UUID
):
    try:
        outputs = the_fake_impl.job_outputs[job_id]
        return outputs

    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No outputs found in job '{job_id}'",
        ) from err


async def get_job_output_impl(
    solver_key: SolverKeyId, version: VersionStr, job_id: UUID, output_name: str
):
    try:
        outputs = the_fake_impl.job_outputs[job_id]
        return next(output for output in outputs if output.name == output_name)

    except (KeyError, StopIteration) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No output '{output_name}' was not found in job {job_id}",
        ) from err

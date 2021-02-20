"""
    Fakes the implementation of some some kind of queueing and
    scheduling of jobs

"""
import asyncio
import hashlib
import logging
import random
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Iterator
from uuid import UUID

from fastapi import HTTPException
from starlette import status

from ...models.api_resources import RelativeResourceName, compose_resource_name
from ...models.schemas.files import File
from ...models.schemas.jobs import Job, JobInputs, JobOutputs, JobStatus, TaskStates
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
    job_inputs: Dict[UUID, JobInputs] = field(default_factory=dict)
    job_tasks: Dict[UUID, asyncio.Future] = field(default_factory=dict)
    job_outputs: Dict[UUID, JobOutputs] = field(default_factory=dict)

    def job_values(self, solver_name: str = None) -> Iterator[Job]:
        if solver_name:
            for job in self.jobs.values():
                if job.runner_name == solver_name:
                    yield job
        else:
            for job in self.jobs.values():
                yield job

    def create_job(self, solver_name: str, inputs: JobInputs) -> Job:
        # TODO: validate inputs against solver definition
        # NOTE: how can be sure that inputs.json() will be identical everytime? str
        # representation might truncate e.g. a number which does not guarantee
        # in all cases that is the same!?
        inputs_checksum = hashlib.sha256(
            " ".join(inputs.json()).encode("utf-8")
        ).hexdigest()

        # TODO: check if job exists already?? Do not consider date??
        job = Job.create_now(solver_name, inputs_checksum)

        self.jobs[job.name] = job
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
            job_status.snapshot("started")
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
            job_status.snapshot("stopped")
            logger.info(job_status)

            # TODO: temporary A fixed output MOCK
            # TODO: temporary writes error in value!
            results = self.create_job_results(job_id)
            if job_status.state == TaskStates.SUCCESS:
                self.job_outputs[job_id] = results
            else:
                failed = random.choice(list(results.outputs.keys()))
                results.outputs[failed] = None
                # TODO: some kind of error ckass results.error = ResultError(loc, field, message) .. . similar to ValidatinError? For one field or generic job error?
                self.job_outputs[job_id] = results

        except asyncio.CancelledError:
            logging.debug("Task for job %s was cancelled", job_id)
            job_status.state = TaskStates.FAILED
            job_status.snapshot("stopped")

            # TODO: an error with the job state??
            # TODO: logs??
            results = self.create_job_results(job_id, {})
            self.job_outputs[job_id] = results

    def stop_job(self, job_name) -> Job:
        job = self.jobs[job_name]
        try:
            task = self.job_tasks[job.id]
            task.cancel()  # not sure it will actually task.cancelling
        except KeyError:
            logger.debug("Stopping job {job_id} that was never started")
        return job

    def create_job_results(jid, res=None):
        # These are outputs by sleeper service
        results = JobOutputs.parse_obj(
            job_id=jid,
            results=res
            if res is not None
            else {
                "output_1": File(
                    filename="file_with_int.txt",
                    id="1460b7c8-70d7-42ee-9eb2-e2de2a9b7b37",
                ),
                "output_2": 42,
            },
        )
        return results


the_fake_impl = JobsFaker()


# */jobs/*  API fake implementations ---------------------


@contextmanager
def job_context(solver_key, version, job_id):
    job_name = compose_resource_name(
        "solvers", solver_key, "releases", version, "jobs", job_id
    )
    try:
        yield job_name
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_name} does not exists",
        ) from err


def _copy_n_update(job: Job, url_for, solver_key, version):
    return job.copy(
        update={
            "url": url_for(
                "get_job", solver_key=solver_key, version=version, job_id=job.id
            ),
            "runner_url": url_for(
                "get_solver_release",
                solver_key=solver_key,
                version=version,
            ),
            "outputs_url": url_for(
                "get_job_results",
                solver_key=solver_key,
                version=version,
                job_id=job.id,
            ),
        }
    )


async def list_jobs_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    url_for: Callable,
):
    solver_resource_name = f"solvers/{solver_key}/releases/{version}"
    return [
        _copy_n_update(job, url_for, solver_key, version)
        for job in the_fake_impl.job_values(solver_resource_name)
    ]


async def create_job_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    inputs: JobInputs,
    url_for: Callable,
):
    """Creates a job for a solver with given inputs.

    NOTE: This operation does **not** start the job
    """
    # TODO: validate inputs against solver specs
    # TODO: create a unique identifier of job based on solver_id and inputs
    solver_name = compose_resource_name("solvers", solver_key, "releases", version)
    job = the_fake_impl.create_job(solver_name, inputs)
    return _copy_n_update(job, url_for, solver_key, version)


async def get_job_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    url_for: Callable,
):
    with job_context(solver_key, version, job_id) as job_name:
        job = the_fake_impl.jobs[job_name]
        return _copy_n_update(job, url_for, solver_key, version)


async def start_job_impl(solver_key: SolverKeyId, version: VersionStr, job_id: UUID):
    with job_context(solver_key, version, job_id) as job_name:
        job_state = the_fake_impl.start_job(job_name)
        return job_state


async def stop_job_impl(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    url_for: Callable,
):
    with job_context(solver_key, version, job_id) as job_name:
        job = the_fake_impl.stop_job(job_name)
        return _copy_n_update(job, url_for, solver_key, version)


async def inspect_job_impl(solver_key: SolverKeyId, version: VersionStr, job_id: UUID):
    job_name = compose_resource_name(
        "solvers", solver_key, "releases", version, "jobs", job_id
    )
    with job_context(solver_key, version, job_id):
        # here we should use job_name ..
        state = the_fake_impl.job_status[job_id]
        return state


async def get_job_outputs_impl(
    solver_key: SolverKeyId, version: VersionStr, job_id: UUID
):
    with job_context(solver_key, version, job_id) as job_name:
        outputs = the_fake_impl.job_outputs[job_id]
        return outputs


async def get_job_output_impl(
    solver_key: SolverKeyId, version: VersionStr, job_id: UUID, output_key: str
):
    output_name = compose_resource_name(
        "solvers",
        solver_key,
        "releases",
        version,
        "jobs",
        job_id,
        "outputs",
        output_key,
    )

    try:
        outputs = the_fake_impl.job_outputs[job_id]
        return next(output for output in outputs if output.name == output_key)

    except (KeyError, StopIteration) as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No output '{output_name}' was not found",
        ) from err

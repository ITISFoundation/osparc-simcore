import logging
from typing import Callable, List
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic.types import PositiveInt

from ...models.api_resources import compose_resource_name
from ...models.domain.projects import NewProjectIn, Project
from ...models.schemas.jobs import (
    Job,
    JobInputs,
    JobOutputs,
    JobStatus,
    KeywordArguments,
)
from ...models.schemas.solvers import SolverKeyId, VersionStr
from ...modules.catalog import CatalogApi
from ...modules.director_v2 import DirectorV2Api
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.authentication import get_current_user_id
from ..dependencies.database import Engine, get_db_engine
from ..dependencies.services import get_api_client
from ..dependencies.webserver import AuthSession, get_webserver_session
from .jobs_faker import the_fake_impl

logger = logging.getLogger(__name__)

router = APIRouter()


# pylint: disable=unused-variable


## JOBS ---------------
#
# - Similar to docker container's API design (container = job and image = solver)
# - TODO: solvers_router.post("/{solver_id}/jobs:run", response_model=JobStatus) disabled since MAG is not convinced it is necessary for now
#
# @router.get("/releases/jobs", response_model=List[Job])


@router.get(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=List[Job],
)
async def list_jobs(
    solver_key: SolverKeyId,
    version: str,
    user_id: PositiveInt = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ List of all jobs in a specific released solver """

    async def _fake_impl():
        from .jobs_faker import list_jobs_impl

        solver = await catalog_client.get_solver(user_id, solver_key, version)
        return await list_jobs_impl(solver.id, solver.version, url_for)

    async def _draft_impl():
        # TODO: create in director list all computations with matching field regex?
        solver = await catalog_client.get_solver(user_id, solver_key, version)

    return await _fake_impl()


@router.post(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=Job,
)
async def create_job(
    solver_key: SolverKeyId,
    version: str,
    inputs: JobInputs,
    user_id: PositiveInt = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    webserver_api: AuthSession = Depends(get_webserver_session),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Creates a job in a specific release with given inputs.

    NOTE: This operation does **not** start the job
    """

    async def _fake_impl():
        from .jobs_faker import create_job_impl

        solver = await catalog_client.get_solver(user_id, solver_key, version)
        return await create_job_impl(solver.id, solver.version, inputs, url_for)

    async def _draft_impl():
        from ...utils.models_creators import create_project_model_for_job
        from .jobs_faker import _copy_n_update

        solver = await catalog_client.get_solver(user_id, solver_key, version)

        #   -> catalog
        # TODO: validate inputs against solver input schema

        job = Job.create_from_solver(solver.id, solver.version, inputs)

        #   -> webserver:  job = project
        project_in: NewProjectIn = create_project_model_for_job(solver, job, inputs)
        new_project: Project = await webserver_api.create_project(project_in)
        assert new_project
        assert new_project.uuid == job.id

        #   -> director2:  job-status = computation_task
        computation_task = await director2_api.create_computation(job.id, user_id)
        assert computation_task.id == job.id

        job = _copy_n_update(job, url_for, solver.id, solver.version)

        # FIXME: keeps local cache??
        the_fake_impl.jobs[job.name] = job

        return job

    return await _draft_impl()


@router.get("/{solver_key:path}/releases/{version}/jobs/{job_id}", response_model=Job)
async def get_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    webserver_api: AuthSession = Depends(get_webserver_session),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """ Gets job of a given solver """

    async def _fake_impl():
        from .jobs_faker import get_job_impl

        return await get_job_impl(solver_key, version, job_id, url_for)

    async def _draft_impl():
        from models_library.projects_nodes import Node

        from .jobs_faker import _copy_n_update

        job_name = compose_resource_name(solver_key, version, job_id)
        logger.debug("Getting Job %s", job_name)

        project = await webserver_api.get_project(project_id=job_id)

        assert len(project.workbench) == 1
        node_id = list(project.workbench.keys())[0]
        node: Node = project.workbench[node_id]

        job = Job.create_from_solver(
            solver_key, version, JobInputs(values=node.inputs.dict())
        )
        # job.created_at = project.creation_date # TODO: parase
        job = _copy_n_update(job, url_for, solver_key, version)

        return job

    return await _draft_impl()


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:start",
    response_model=JobStatus,
)
async def start_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    user_id: PositiveInt = Depends(get_current_user_id),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
):
    async def _fake_impl():
        from .jobs_faker import start_job_impl

        return await start_job_impl(solver_key, version, job_id)

    async def _draft_impl():
        job_name = compose_resource_name(solver_key, version, job_id)
        logger.debug("Start Job %s", job_name)

        computation_task = await director2_api.start_computation(job_id, user_id)
        job_status = computation_task.as_jobstatus()
        return job_status

    return await _draft_impl()


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:stop", response_model=Job
)
async def stop_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    user_id: PositiveInt = Depends(get_current_user_id),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    async def _fake_impl():
        from .jobs_faker import stop_job_impl

        return await stop_job_impl(solver_key, version, job_id, url_for)

    async def _draft_impl():
        job_name = compose_resource_name(solver_key, version, job_id)
        logger.debug("Stopping Job %s", job_name)

        await director2_api.stop_computation(job_id, user_id)

        computation_task = await director2_api.get_computation(job_id, user_id)
        job_status = computation_task.as_jobstatus()
        return job_status

    return await _draft_impl()


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}:inspect",
    response_model=JobStatus,
)
async def inspect_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    user_id: PositiveInt = Depends(get_current_user_id),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
):
    async def _fake_impl():
        from .jobs_faker import inspect_job_impl

        return await inspect_job_impl(solver_key, version, job_id)

    async def _draft_impl():
        job_name = compose_resource_name(solver_key, version, job_id)
        logger.debug("Inspecting Job %s", job_name)

        computation_task = await director2_api.get_computation(job_id, user_id)
        job_status = computation_task.as_jobstatus()
        return job_status

    return await _draft_impl()


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id}/outputs",
    response_model=JobOutputs,
)
async def get_job_outputs(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    user_id: PositiveInt = Depends(get_current_user_id),
    db_engine: Engine = Depends(get_db_engine),
    webserver_api: AuthSession = Depends(get_webserver_session),
):
    async def _fake_impl():
        from .jobs_faker import get_job_outputs_impl

        return await get_job_outputs_impl(solver_key, version, job_id)

    async def _draft_impl():
        from ...utils.solver_job_outputs import get_solver_output_results

        job_name = compose_resource_name(solver_key, version, job_id)
        logger.debug("Get Job outputs %s", job_name)

        project = await webserver_api.get_project(project_id=job_id)
        node_ids = list(project.workbench.keys())
        assert len(node_ids) == 1

        results: KeywordArguments = await get_solver_output_results(
            user_id=user_id,
            project_uuid=job_id,
            node_uuid=UUID(node_ids[0]),
            db_engine=db_engine,
        )
        return JobOutputs(job_id=job_id, results=results)

    return await _draft_impl()

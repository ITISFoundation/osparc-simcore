# pylint: disable=too-many-arguments
# TODO: user_id should be injected every request in api instances, i.e. a new api-instance per request

import logging
from collections import deque
from typing import Callable, Union
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from models_library.projects_nodes_io import BaseFileLink
from pydantic.types import PositiveInt

from ...models.domain.projects import NewProjectIn, Project
from ...models.schemas.files import File
from ...models.schemas.jobs import ArgumentType, Job, JobInputs, JobOutputs, JobStatus
from ...models.schemas.solvers import Solver, SolverKeyId, VersionStr
from ...modules.catalog import CatalogApi
from ...modules.director_v2 import (
    ComputationTaskGet,
    DirectorV2Api,
    DownloadLink,
    NodeName,
)
from ...modules.storage import StorageApi, to_file_api_model
from ...utils.solver_job_models_converters import (
    create_job_from_project,
    create_jobstatus_from_task,
    create_new_project_for_job,
)
from ...utils.solver_job_outputs import get_solver_output_results
from ..dependencies.application import get_product_name, get_reverse_url_mapper
from ..dependencies.authentication import get_current_user_id
from ..dependencies.database import Engine, get_db_engine
from ..dependencies.services import get_api_client
from ..dependencies.webserver import AuthSession, get_webserver_session

logger = logging.getLogger(__name__)

router = APIRouter()


def _compose_job_resource_name(solver_key, solver_version, job_id) -> str:
    """Creates a unique resource name for solver's jobs"""
    return Job.compose_resource_name(
        parent_name=Solver.compose_resource_name(solver_key, solver_version),
        job_id=job_id,
    )


## JOBS ---------------
#
# - Similar to docker container's API design (container = job and image = solver)
#


@router.get(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=list[Job],
)
async def list_jobs(
    solver_key: SolverKeyId,
    version: str,
    user_id: PositiveInt = Depends(get_current_user_id),
    catalog_client: CatalogApi = Depends(get_api_client(CatalogApi)),
    webserver_api: AuthSession = Depends(get_webserver_session),
    url_for: Callable = Depends(get_reverse_url_mapper),
    product_name: str = Depends(get_product_name),
):
    """List of all jobs in a specific released solver"""

    solver = await catalog_client.get_solver(
        user_id=user_id,
        name=solver_key,
        version=version,
        product_name=product_name,
    )
    logger.debug("Listing Jobs in Solver '%s'", solver.name)

    projects: list[Project] = await webserver_api.list_projects(solver.name)
    jobs: deque[Job] = deque()
    for prj in projects:
        job = create_job_from_project(solver_key, version, prj, url_for)
        assert job.id == prj.uuid  # nosec
        assert job.name == prj.name  # nosec

        jobs.append(job)

    return list(jobs)


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
    product_name: str = Depends(get_product_name),
):
    """Creates a job in a specific release with given inputs.

    NOTE: This operation does **not** start the job
    """

    # ensures user has access to solver
    solver = await catalog_client.get_solver(
        user_id=user_id,
        name=solver_key,
        version=version,
        product_name=product_name,
    )

    # creates NEW job as prototype
    pre_job = Job.create_solver_job(solver=solver, inputs=inputs)
    logger.debug("Creating Job '%s'", pre_job.name)

    # -> catalog
    # TODO: validate inputs against solver input schema

    #   -> webserver:  NewProjectIn = Job
    project_in: NewProjectIn = create_new_project_for_job(solver, pre_job, inputs)
    new_project: Project = await webserver_api.create_project(project_in)
    assert new_project  # nosec
    assert new_project.uuid == pre_job.id  # nosec

    # for consistency, it rebuild job
    job = create_job_from_project(
        solver_key=solver.id,
        solver_version=solver.version,
        project=new_project,
        url_for=url_for,
    )
    assert job.id == pre_job.id  # nosec
    assert job.name == pre_job.name  # nosec
    assert job.name == _compose_job_resource_name(solver_key, version, job.id)  # nosec

    # -> director2:   ComputationTaskOut = JobStatus
    # consistency check
    task: ComputationTaskGet = await director2_api.create_computation(job.id, user_id)
    assert task.id == job.id  # nosec

    job_status: JobStatus = create_jobstatus_from_task(task)
    assert job.id == job_status.job_id  # nosec

    return job


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}", response_model=Job
)
async def get_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    webserver_api: AuthSession = Depends(get_webserver_session),
    url_for: Callable = Depends(get_reverse_url_mapper),
):
    """Gets job of a given solver"""

    job_name = _compose_job_resource_name(solver_key, version, job_id)
    logger.debug("Getting Job '%s'", job_name)

    project: Project = await webserver_api.get_project(project_id=job_id)

    job = create_job_from_project(solver_key, version, project, url_for)
    assert job.id == job_id  # nosec
    return job  # nosec


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}:start",
    response_model=JobStatus,
)
async def start_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    user_id: PositiveInt = Depends(get_current_user_id),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
    product_name: str = Depends(get_product_name),
):

    job_name = _compose_job_resource_name(solver_key, version, job_id)
    logger.debug("Start Job '%s'", job_name)

    task = await director2_api.start_computation(
        project_id=job_id,
        user_id=user_id,
        product_name=product_name,
    )
    job_status: JobStatus = create_jobstatus_from_task(task)
    return job_status


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}:stop", response_model=Job
)
async def stop_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    user_id: PositiveInt = Depends(get_current_user_id),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
):

    job_name = _compose_job_resource_name(solver_key, version, job_id)
    logger.debug("Stopping Job '%s'", job_name)

    await director2_api.stop_computation(job_id, user_id)

    task = await director2_api.get_computation(job_id, user_id)
    job_status: JobStatus = create_jobstatus_from_task(task)
    return job_status


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}:inspect",
    response_model=JobStatus,
)
async def inspect_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    user_id: PositiveInt = Depends(get_current_user_id),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
):

    job_name = _compose_job_resource_name(solver_key, version, job_id)
    logger.debug("Inspecting Job '%s'", job_name)

    task = await director2_api.get_computation(job_id, user_id)
    job_status: JobStatus = create_jobstatus_from_task(task)
    return job_status


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/outputs",
    response_model=JobOutputs,
)
async def get_job_outputs(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    user_id: PositiveInt = Depends(get_current_user_id),
    db_engine: Engine = Depends(get_db_engine),
    webserver_api: AuthSession = Depends(get_webserver_session),
    storage_client: StorageApi = Depends(get_api_client(StorageApi)),
):

    job_name = _compose_job_resource_name(solver_key, version, job_id)
    logger.debug("Get Job '%s' outputs", job_name)

    project: Project = await webserver_api.get_project(project_id=job_id)
    node_ids = list(project.workbench.keys())
    assert len(node_ids) == 1  # nosec

    outputs: dict[
        str, Union[float, int, bool, BaseFileLink, str, None]
    ] = await get_solver_output_results(
        user_id=user_id,
        project_uuid=job_id,
        node_uuid=UUID(node_ids[0]),
        db_engine=db_engine,
    )

    results: dict[str, ArgumentType] = {}
    for name, value in outputs.items():
        if isinstance(value, BaseFileLink):
            # TODO: value.path exists??
            file_id: UUID = File.create_id(*value.path.split("/"))

            # TODO: acquire_soft_link will halve calls
            found = await storage_client.search_files(user_id, file_id)
            if found:
                assert len(found) == 1  # nosec
                results[name] = to_file_api_model(found[0])
            else:
                api_file: File = await storage_client.create_soft_link(
                    user_id, value.path, file_id
                )
                results[name] = api_file
        else:
            # TODO: cast against catalog's output port specs
            results[name] = value

    job_outputs = JobOutputs(job_id=job_id, results=results)
    return job_outputs


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/outputs/logfile",
    response_class=RedirectResponse,
    responses={
        status.HTTP_200_OK: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                },
                "application/zip": {"schema": {"type": "string", "format": "binary"}},
                "text/plain": {"schema": {"type": "string"}},
            },
            "description": "Returns a log file",
        },
        status.HTTP_404_NOT_FOUND: {"description": "Log not found"},
    },
)
async def get_job_output_logfile(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: UUID,
    user_id: PositiveInt = Depends(get_current_user_id),
    director2_api: DirectorV2Api = Depends(get_api_client(DirectorV2Api)),
):
    """Special extra output with persistent logs file for the solver run.

    NOTE: this is not a log stream but a predefined output that is only
    available after the job is done.

    New in *version 0.4*
    """

    logs_urls: dict[NodeName, DownloadLink] = await director2_api.get_computation_logs(
        user_id=user_id, project_id=job_id
    )

    # if more than one node? should rezip all of them??
    assert len(logs_urls) <= 1, "Current version only supports one node per solver"
    for presigned_download_link in logs_urls.values():
        logger.info(
            "Redirecting '%s' to %s ...",
            f"{solver_key}/releases/{version}/jobs/{job_id}/outputs/logfile",
            presigned_download_link,
        )
        return RedirectResponse(presigned_download_link)

    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail=f"Log for {solver_key}/releases/{version}/jobs/{job_id} not found."
        "Note that these logs are only available after the job is completed.",
    )

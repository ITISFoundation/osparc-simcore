# pylint: disable=too-many-arguments

import logging
from collections import deque
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from fastapi_pagination.api import create_page
from models_library.api_schemas_webserver.projects import ProjectCreateNew, ProjectGet
from models_library.clusters import ClusterID
from models_library.projects_nodes_io import BaseFileLink
from pydantic.types import PositiveInt

from ...models.basic_types import VersionStr
from ...models.pagination import Page, PaginationParams
from ...models.schemas.files import File
from ...models.schemas.jobs import (
    ArgumentTypes,
    Job,
    JobID,
    JobInputs,
    JobMetadata,
    JobMetadataUpdate,
    JobOutputs,
    JobStatus,
)
from ...models.schemas.solvers import Solver, SolverKeyId
from ...services.catalog import CatalogApi
from ...services.director_v2 import DirectorV2Api, DownloadLink, NodeName
from ...services.storage import StorageApi, to_file_api_model
from ...utils.solver_job_models_converters import (
    create_job_from_project,
    create_jobstatus_from_task,
    create_new_project_for_job,
)
from ...utils.solver_job_outputs import ResultsTypes, get_solver_output_results
from ..dependencies.application import get_product_name, get_reverse_url_mapper
from ..dependencies.authentication import get_current_user_id
from ..dependencies.database import Engine, get_db_engine
from ..dependencies.services import get_api_client
from ..dependencies.webserver import AuthSession, get_webserver_session
from ..errors.http_error import ErrorGet, create_error_json_response
from ._common import API_SERVER_DEV_FEATURES_ENABLED, job_output_logfile_responses

_logger = logging.getLogger(__name__)

router = APIRouter()


def _compose_job_resource_name(solver_key, solver_version, job_id) -> str:
    """Creates a unique resource name for solver's jobs"""
    return Job.compose_resource_name(
        parent_name=Solver.compose_resource_name(solver_key, solver_version),  # type: ignore
        job_id=job_id,
    )


# JOBS ---------------
#
# - Similar to docker container's API design (container = job and image = solver)
#

_common_error_responses = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Job not found",
        "model": ErrorGet,
    },
}


@router.get(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=list[Job],
)
async def list_jobs(
    solver_key: SolverKeyId,
    version: VersionStr,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
):
    """List of jobs in a specific released solver (limited to 20 jobs)

    SEE get_jobs_page for paginated version of this function
    """

    solver = await catalog_client.get_service(
        user_id=user_id,
        name=solver_key,
        version=version,
        product_name=product_name,
    )
    _logger.debug("Listing Jobs in Solver '%s'", solver.name)

    projects_page = await webserver_api.list_projects(solver.name, limit=20, offset=0)

    jobs: deque[Job] = deque()
    for prj in projects_page.data:
        job = create_job_from_project(solver_key, version, prj, url_for)
        assert job.id == prj.uuid  # nosec
        assert job.name == prj.name  # nosec

        jobs.append(job)

    return list(jobs)


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/page",
    response_model=Page[Job],
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_jobs_page(
    solver_key: SolverKeyId,
    version: VersionStr,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    page_params: Annotated[PaginationParams, Depends()],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
):
    """List of jobs on a specific released solver (includes pagination)


    Breaking change in *version 0.5*: response model changed from list[Job] to pagination Page[Job].
    """

    # NOTE: Different entry to keep backwards compatibility with list_jobs.
    # Eventually use a header with agent version to switch to new interface

    solver = await catalog_client.get_service(
        user_id=user_id,
        name=solver_key,
        version=version,
        product_name=product_name,
    )
    _logger.debug("Listing Jobs in Solver '%s'", solver.name)

    projects_page = await webserver_api.list_projects(
        solver.name, limit=page_params.limit, offset=page_params.offset
    )

    jobs: list[Job] = [
        create_job_from_project(solver_key, version, prj, url_for)
        for prj in projects_page.data
    ]

    return create_page(
        jobs,
        total=projects_page.meta.total,
        params=page_params,
    )


@router.post(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=Job,
)
async def create_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    inputs: JobInputs,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    catalog_client: Annotated[CatalogApi, Depends(get_api_client(CatalogApi))],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
    product_name: Annotated[str, Depends(get_product_name)],
):
    """Creates a job in a specific release with given inputs.

    NOTE: This operation does **not** start the job
    """

    # ensures user has access to solver
    solver = await catalog_client.get_service(
        user_id=user_id,
        name=solver_key,
        version=version,
        product_name=product_name,
    )

    # creates NEW job as prototype
    pre_job = Job.create_solver_job(solver=solver, inputs=inputs)
    _logger.debug("Creating Job '%s'", pre_job.name)

    project_in: ProjectCreateNew = create_new_project_for_job(solver, pre_job, inputs)
    new_project: ProjectGet = await webserver_api.create_project(project_in)
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

    return job


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}", response_model=Job
)
async def get_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    """Gets job of a given solver"""
    _logger.debug(
        "Getting Job '%s'", _compose_job_resource_name(solver_key, version, job_id)
    )

    project: ProjectGet = await webserver_api.get_project(project_id=job_id)

    job = create_job_from_project(solver_key, version, project, url_for)
    assert job.id == job_id  # nosec
    return job  # nosec


@router.delete(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorGet}},
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def delete_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    """Deletes an existing solver job

    New in *version 0.5*
    """
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Deleting Job '%s'", job_name)

    try:
        await webserver_api.delete_project(project_id=job_id)

    except HTTPException as err:
        if err.status_code == status.HTTP_404_NOT_FOUND:
            return create_error_json_response(
                f"Cannot find job={job_name} to delete",
                status_code=status.HTTP_404_NOT_FOUND,
            )


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}:start",
    response_model=JobStatus,
)
async def start_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    product_name: Annotated[str, Depends(get_product_name)],
    cluster_id: ClusterID | None = None,
):
    """Starts job job_id created with the solver solver_key:version

    New in *version 0.4.3*: cluster_id
    """

    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Start Job '%s'", job_name)

    task = await director2_api.start_computation(
        project_id=job_id,
        user_id=user_id,
        product_name=product_name,
        cluster_id=cluster_id,
    )
    job_status: JobStatus = create_jobstatus_from_task(task)
    return job_status


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}:stop",
    response_model=Job,
)
async def stop_job(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
):
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Stopping Job '%s'", job_name)

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
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
) -> JobStatus:
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Inspecting Job '%s'", job_name)

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
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    db_engine: Annotated[Engine, Depends(get_db_engine)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    storage_client: Annotated[StorageApi, Depends(get_api_client(StorageApi))],
):
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Get Job '%s' outputs", job_name)

    project: ProjectGet = await webserver_api.get_project(project_id=job_id)
    node_ids = list(project.workbench.keys())
    assert len(node_ids) == 1  # nosec

    outputs: dict[str, ResultsTypes] = await get_solver_output_results(
        user_id=user_id,
        project_uuid=job_id,
        node_uuid=UUID(node_ids[0]),
        db_engine=db_engine,
    )

    results: dict[str, ArgumentTypes] = {}
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

    return JobOutputs(job_id=job_id, results=results)


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/outputs/logfile",
    response_class=RedirectResponse,
    responses=job_output_logfile_responses,
)
async def get_job_output_logfile(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
):
    """Special extra output with persistent logs file for the solver run.

    NOTE: this is not a log stream but a predefined output that is only
    available after the job is done.

    New in *version 0.4.0*
    """
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Get Job '%s' outputs logfile", job_name)

    project_id = job_id

    logs_urls: dict[NodeName, DownloadLink] = await director2_api.get_computation_logs(
        user_id=user_id, project_id=project_id
    )

    _logger.debug(
        "Found %d logfiles for %s %s: %s",
        len(logs_urls),
        f"{project_id=}",
        f"{user_id=}",
        list(logs_urls.keys()),
    )

    # if more than one node? should rezip all of them??
    assert (  # nosec
        len(logs_urls) <= 1
    ), "Current version only supports one node per solver"

    for presigned_download_link in logs_urls.values():
        _logger.info(
            "Redirecting '%s' to %s ...",
            f"{solver_key}/releases/{version}/jobs/{job_id}/outputs/logfile",
            presigned_download_link,
        )
        return RedirectResponse(presigned_download_link)

    # No log found !
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail=f"Log for {solver_key}/releases/{version}/jobs/{job_id} not found."
        "Note that these logs are only available after the job is completed.",
    )


@router.get(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/metadata",
    response_model=JobMetadata,
    responses={**_common_error_responses},
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_job_custom_metadata(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    """Gets custom metadata from a job

    New in *version 0.5*
    """
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Custom metadata for '%s'", job_name)

    try:
        project_metadata = await webserver_api.get_project_metadata(project_id=job_id)
        return JobMetadata(
            job_id=job_id,
            metadata=project_metadata.custom,
            url=url_for(
                "get_job_custom_metadata",
                solver_key=solver_key,
                version=version,
                job_id=job_id,
            ),
        )

    except HTTPException as err:
        if err.status_code == status.HTTP_404_NOT_FOUND:
            return create_error_json_response(
                f"Cannot find job={job_name} ",
                status_code=status.HTTP_404_NOT_FOUND,
            )


@router.patch(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/metadata",
    response_model=JobMetadata,
    responses={**_common_error_responses},
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def replace_job_custom_metadata(
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    update: JobMetadataUpdate,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    url_for: Annotated[Callable, Depends(get_reverse_url_mapper)],
):
    """Updates custom metadata from a job

    New in *version 0.5*
    """
    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Custom metadata for '%s'", job_name)

    try:
        project_metadata = await webserver_api.update_project_metadata(
            project_id=job_id, metadata=update.metadata
        )
        return JobMetadata(
            job_id=job_id,
            metadata=project_metadata.custom,
            url=url_for(
                "replace_job_custom_metadata",
                solver_key=solver_key,
                version=version,
                job_id=job_id,
            ),
        )

    except HTTPException as err:
        if err.status_code == status.HTTP_404_NOT_FOUND:
            return create_error_json_response(
                f"Cannot find job={job_name} ",
                status_code=status.HTTP_404_NOT_FOUND,
            )

# pylint: disable=too-many-arguments

import logging
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import HTTPException
from models_library.api_schemas_webserver.projects import ProjectCreateNew, ProjectGet
from models_library.clusters import ClusterID
from pydantic.types import PositiveInt
from servicelib.logging_utils import log_context
from simcore_service_api_server.models.schemas.errors import ErrorGet
from simcore_service_api_server.services.service_exception_handling import (
    DEFAULT_BACKEND_SERVICE_STATUS_CODES,
)

from ...models.basic_types import VersionStr
from ...models.schemas.jobs import (
    Job,
    JobID,
    JobInputs,
    JobMetadata,
    JobMetadataUpdate,
    JobPricingSpecification,
    JobStatus,
)
from ...models.schemas.solvers import Solver, SolverKeyId
from ...services.catalog import CatalogApi
from ...services.director_v2 import DirectorV2Api
from ...services.solver_job_models_converters import (
    create_job_from_project,
    create_jobstatus_from_task,
    create_new_project_for_job,
)
from ..dependencies.application import get_reverse_url_mapper
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.services import get_api_client
from ..dependencies.webserver import AuthSession, get_webserver_session
from ..errors.http_error import create_error_json_response
from ._common import API_SERVER_DEV_FEATURES_ENABLED

_logger = logging.getLogger(__name__)

router = APIRouter()


def _compose_job_resource_name(solver_key, solver_version, job_id) -> str:
    """Creates a unique resource name for solver's jobs"""
    return Job.compose_resource_name(
        parent_name=Solver.compose_resource_name(solver_key, solver_version),  # type: ignore
        job_id=job_id,
    )


def _raise_if_job_not_associated_with_solver(
    solver_key: SolverKeyId, version: VersionStr, project: ProjectGet
) -> None:
    expected_job_name: str = _compose_job_resource_name(
        solver_key, version, project.uuid
    )
    if expected_job_name != project.name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"job {project.uuid} is not associated with solver {solver_key} and version {version}",
        )


# JOBS ---------------
#
# - Similar to docker container's API design (container = job and image = solver)
#
METADATA_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Metadata not found",
        "model": ErrorGet,
    }
} | DEFAULT_BACKEND_SERVICE_STATUS_CODES

JOBS_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_402_PAYMENT_REQUIRED: {
        "description": "Payment required",
        "model": ErrorGet,
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "Job not found",
        "model": ErrorGet,
    },
} | DEFAULT_BACKEND_SERVICE_STATUS_CODES


@router.post(
    "/{solver_key:path}/releases/{version}/jobs",
    response_model=Job,
    status_code=status.HTTP_201_CREATED,
    responses=JOBS_STATUS_CODES,
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


@router.delete(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=JOBS_STATUS_CODES,
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

    await webserver_api.delete_project(project_id=job_id)


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}:start",
    response_model=JobStatus,
    responses=JOBS_STATUS_CODES,
)
async def start_job(
    request: Request,
    solver_key: SolverKeyId,
    version: VersionStr,
    job_id: JobID,
    user_id: Annotated[PositiveInt, Depends(get_current_user_id)],
    director2_api: Annotated[DirectorV2Api, Depends(get_api_client(DirectorV2Api))],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    cluster_id: ClusterID | None = None,
):
    """Starts job job_id created with the solver solver_key:version

    New in *version 0.4.3*: cluster_id
    """

    job_name = _compose_job_resource_name(solver_key, version, job_id)
    _logger.debug("Start Job '%s'", job_name)

    if pricing_spec := JobPricingSpecification.create_from_headers(request.headers):
        with log_context(_logger, logging.DEBUG, "Set pricing plan and unit"):
            project: ProjectGet = await webserver_api.get_project(project_id=job_id)
            _raise_if_job_not_associated_with_solver(solver_key, version, project)
            node_ids = list(project.workbench.keys())
            assert len(node_ids) == 1  # nosec
            await webserver_api.connect_pricing_unit_to_project_node(
                project_id=job_id,
                node_id=UUID(node_ids[0]),
                pricing_plan=pricing_spec.pricing_plan,
                pricing_unit=pricing_spec.pricing_unit,
            )

    with log_context(_logger, logging.DEBUG, "Starting job"):
        await webserver_api.start_project(project_id=job_id, cluster_id=cluster_id)
        return await inspect_job(
            solver_key=solver_key,
            version=version,
            job_id=job_id,
            user_id=user_id,
            director2_api=director2_api,
        )


@router.post(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}:stop",
    response_model=JobStatus,
    responses=JOBS_STATUS_CODES,
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
    responses=JOBS_STATUS_CODES,
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


@router.patch(
    "/{solver_key:path}/releases/{version}/jobs/{job_id:uuid}/metadata",
    response_model=JobMetadata,
    responses=METADATA_STATUS_CODES,
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

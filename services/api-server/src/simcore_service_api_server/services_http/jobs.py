import logging
from uuid import UUID

from models_library.api_schemas_webserver.projects import ProjectGet
from pydantic import HttpUrl, PositiveInt
from servicelib.logging_utils import log_context

from ..exceptions.backend_errors import InvalidInputError
from ..models.schemas.jobs import (
    JobID,
    JobMetadata,
    JobMetadataUpdate,
    JobPricingSpecification,
    JobStatus,
)
from .director_v2 import DirectorV2Api
from .solver_job_models_converters import create_jobstatus_from_task
from .webserver import AuthSession

_logger = logging.getLogger(__name__)


def raise_if_job_not_associated_with_solver(
    expected_project_name: str, project: ProjectGet
) -> None:
    if expected_project_name != project.name:
        raise InvalidInputError()


async def start_project(
    *,
    job_id: JobID,
    expected_job_name: str,
    pricing_spec: JobPricingSpecification | None,
    webserver_api: AuthSession,
) -> None:
    if pricing_spec is not None:
        with log_context(_logger, logging.DEBUG, "Set pricing plan and unit"):
            project: ProjectGet = await webserver_api.get_project(project_id=job_id)
            raise_if_job_not_associated_with_solver(expected_job_name, project)
            node_ids = list(project.workbench.keys())
            assert len(node_ids) == 1  # nosec
            await webserver_api.connect_pricing_unit_to_project_node(
                project_id=job_id,
                node_id=UUID(node_ids[0]),
                pricing_plan=pricing_spec.pricing_plan,
                pricing_unit=pricing_spec.pricing_unit,
            )
    with log_context(_logger, logging.DEBUG, "Starting job"):
        await webserver_api.start_project(project_id=job_id)


async def stop_project(
    *,
    job_id: JobID,
    user_id: PositiveInt,
    director2_api: DirectorV2Api,
) -> JobStatus:
    await director2_api.stop_computation(project_id=job_id, user_id=user_id)

    task = await director2_api.get_computation(project_id=job_id, user_id=user_id)
    job_status: JobStatus = create_jobstatus_from_task(task)
    return job_status


async def get_custom_metadata(
    *,
    job_name: str,
    job_id: JobID,
    webserver_api: AuthSession,
    self_url: HttpUrl,
):
    assert job_name  # nosec
    project_metadata = await webserver_api.get_project_metadata(project_id=job_id)
    return JobMetadata(
        job_id=job_id,
        metadata=project_metadata.custom,
        url=self_url,
    )


async def replace_custom_metadata(
    *,
    job_name: str,
    job_id: JobID,
    update: JobMetadataUpdate,
    webserver_api: AuthSession,
    self_url: HttpUrl,
):
    assert job_name  # nosec
    project_metadata = await webserver_api.update_project_metadata(
        project_id=job_id, metadata=update.metadata
    )
    return JobMetadata(
        job_id=job_id,
        metadata=project_metadata.custom,
        url=self_url,
    )

import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.clusters import ClusterID
from servicelib.logging_utils import log_context
from simcore_service_api_server.api.dependencies.webserver import get_webserver_session
from simcore_service_api_server.models.schemas.jobs import (
    JobID,
    JobPricingSpecification,
)
from simcore_service_api_server.services.webserver import AuthSession

_logger = logging.getLogger(__name__)


def raise_if_job_not_associated_with_solver(
    expected_project_name: str, project: ProjectGet
) -> None:
    if expected_project_name != project.name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid input data for job {project.uuid}",
        )


async def start_project(
    *,
    request: Request,
    job_id: JobID,
    expected_job_name: str,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
    cluster_id: ClusterID | None = None,
) -> None:
    if pricing_spec := JobPricingSpecification.create_from_headers(request.headers):
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
        await webserver_api.start_project(project_id=job_id, cluster_id=cluster_id)

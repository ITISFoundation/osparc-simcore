import logging
from typing import Annotated

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import AfterValidator, validate_call
from simcore_service_webserver.projects.models import ProjectJobDBGet

from ._access_rights_service import check_user_project_permission
from ._jobs_repository import ProjectJobsRepository

_logger = logging.getLogger(__name__)


def _validate_job_parent_resource_name(value: str) -> str:
    if value and not value.startswith("/") and not value.endswith("/") and "/" in value:
        return value
    msg = "Invalid format: must contain '/' but cannot start or end with '/'"
    raise ValueError(msg)


@validate_call(config={"arbitrary_types_allowed": True})
async def set_project_as_job(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    job_parent_resource_name: Annotated[
        str, AfterValidator(_validate_job_parent_resource_name)
    ],
) -> None:

    await check_user_project_permission(
        app,
        project_id=project_uuid,
        user_id=user_id,
        product_name=product_name,
        permission="write",
    )

    repo = ProjectJobsRepository.create_from_app(app)

    await repo.set_project_as_job(
        project_uuid=project_uuid, job_parent_resource_name=job_parent_resource_name
    )


@validate_call(config={"arbitrary_types_allowed": True})
async def list_my_projects_marked_as_jobs(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    offset: int = 0,
    limit: int = 10,
    job_parent_resource_name_filter: str | None = None,
) -> tuple[int, list[ProjectJobDBGet]]:
    """
    Lists paginated projects marked as jobs for the given user and product.
    Optionally filters by job_parent_resource_name using SQL-like wildcard patterns.
    """
    repo = ProjectJobsRepository.create_from_app(app)
    return await repo.list_projects_marked_as_jobs(
        user_id=user_id,
        product_name=product_name,
        offset=offset,
        limit=limit,
        job_parent_resource_name_filter=job_parent_resource_name_filter,
    )

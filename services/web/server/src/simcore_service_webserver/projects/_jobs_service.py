import logging
from typing import Annotated

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import AfterValidator, validate_call

from ._access_rights_service import check_user_project_permission
from ._jobs_repository import ProjectJobsRepository
from .exceptions import ProjectNotFoundError
from .models import ProjectJobDBGet

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
    storage_assets_deleted: bool,
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
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
        storage_assets_deleted=storage_assets_deleted,
    )


@validate_call(config={"arbitrary_types_allowed": True})
async def list_my_projects_marked_as_jobs(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    pagination_offset: int = 0,
    pagination_limit: int = 10,
    filter_by_job_parent_resource_name_prefix: str | None = None,
    filter_any_custom_metadata: list[tuple[str, str]] | None = None,
) -> tuple[int, list[ProjectJobDBGet]]:
    """
    Lists paginated projects marked as jobs for the given user and product.

    Keyword Arguments:
        filter_by_job_parent_resource_name_prefix -- Optionally filters by job_parent_resource_name using SQL-like wildcard patterns. (default: {None})
        filter_any_custom_metadata -- is a list of dictionaries with key-pattern pairs for custom metadata fields (OR logic). (default: {None})

    Returns:
        A tuple containing the total number of projects and a list of ProjectJobDBGet objects for this page.
    """
    repo = ProjectJobsRepository.create_from_app(app)
    return await repo.list_projects_marked_as_jobs(
        user_id=user_id,
        product_name=product_name,
        pagination_offset=pagination_offset,
        pagination_limit=pagination_limit,
        filter_by_job_parent_resource_name_prefix=filter_by_job_parent_resource_name_prefix,
        filter_any_custom_metadata=filter_any_custom_metadata,
    )


@validate_call(config={"arbitrary_types_allowed": True})
async def get_project_marked_as_job(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    job_parent_resource_name: Annotated[
        str, AfterValidator(_validate_job_parent_resource_name)
    ],
) -> ProjectJobDBGet:
    """
    Retrieves the project associated with the given project_uuid and job_parent_resource_name.
    Raises:
        web.HTTPNotFound: if no project is found.
    """
    await check_user_project_permission(
        app,
        project_id=project_uuid,
        user_id=user_id,
        product_name=product_name,
        permission="read",
    )
    repo = ProjectJobsRepository.create_from_app(app)
    project_id = await repo.get_project_marked_as_job(
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )
    if not project_id:
        raise ProjectNotFoundError(
            project_uuid=project_uuid,
        )
    return project_id

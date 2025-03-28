import logging
from typing import Annotated

from aiohttp import web
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import AfterValidator, validate_call

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

    projects_to_jobs_id = await repo.set_project_as_job(
        project_uuid=project_uuid, job_parent_resource_name=job_parent_resource_name
    )
    assert projects_to_jobs_id  # nosec

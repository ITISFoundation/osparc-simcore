from aiohttp import web
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_pagination import PageLimitInt, PageOffsetInt
from models_library.rpc.webserver.projects import (
    ListProjectsMarkedAsJobRpcFilters,
    PageRpcProjectJobRpcGet,
    ProjectJobRpcGet,
)
from models_library.users import UserID
from pydantic import ValidationError, validate_call
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import (
    ProjectForbiddenRpcError,
    ProjectNotFoundRpcError,
)

from ...rabbitmq import get_rabbitmq_rpc_server
from .. import _jobs_service
from ..exceptions import ProjectInvalidRightsError, ProjectNotFoundError

router = RPCRouter()


@router.expose(
    reraise_if_error_type=(
        ProjectForbiddenRpcError,
        ProjectNotFoundRpcError,
        ValidationError,
    )
)
@validate_call(config={"arbitrary_types_allowed": True})
async def mark_project_as_job(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    job_parent_resource_name: str,
    storage_assets_deleted: bool,
) -> None:

    try:

        await _jobs_service.set_project_as_job(
            app,
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            job_parent_resource_name=job_parent_resource_name,
            storage_assets_deleted=storage_assets_deleted,
        )
    except ProjectInvalidRightsError as err:
        raise ProjectForbiddenRpcError.from_domain_error(err) from err

    except ProjectNotFoundError as err:
        raise ProjectNotFoundRpcError.from_domain_error(err) from err


@router.expose(reraise_if_error_type=(ValidationError,))
@validate_call(config={"arbitrary_types_allowed": True})
async def list_projects_marked_as_jobs(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    # pagination
    offset: PageOffsetInt,
    limit: PageLimitInt,
    filters: ListProjectsMarkedAsJobRpcFilters | None = None,
) -> PageRpcProjectJobRpcGet:

    total, projects = await _jobs_service.list_my_projects_marked_as_jobs(
        app,
        product_name=product_name,
        user_id=user_id,
        pagination_offset=offset,
        pagination_limit=limit,
        filter_by_job_parent_resource_name_prefix=(
            filters.job_parent_resource_name_prefix if filters else None
        ),
        filter_any_custom_metadata=(
            [
                (custom_metadata.name, custom_metadata.pattern)
                for custom_metadata in filters.any_custom_metadata
            ]
            if filters and filters.any_custom_metadata
            else None
        ),
    )

    job_projects = [
        ProjectJobRpcGet(
            uuid=project.uuid,
            name=project.name,
            description=project.description,
            workbench=project.workbench,
            created_at=project.creation_date,
            modified_at=project.last_change_date,
            job_parent_resource_name=project.job_parent_resource_name,
            storage_assets_deleted=project.storage_assets_deleted,
        )
        for project in projects
    ]

    page: PageRpcProjectJobRpcGet = PageRpcProjectJobRpcGet.create(
        job_projects,
        total=total,
        limit=limit,
        offset=offset,
    )

    return page


@router.expose(
    reraise_if_error_type=(
        ValidationError,
        ProjectForbiddenRpcError,
        ProjectNotFoundRpcError,
    )
)
@validate_call(config={"arbitrary_types_allowed": True})
async def get_project_marked_as_job(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    job_parent_resource_name: str,
) -> ProjectJobRpcGet:

    try:
        project = await _jobs_service.get_project_marked_as_job(
            app,
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            job_parent_resource_name=job_parent_resource_name,
        )
    except ProjectInvalidRightsError as err:
        raise ProjectForbiddenRpcError.from_domain_error(err) from err

    except ProjectNotFoundError as err:
        raise ProjectNotFoundRpcError.from_domain_error(err) from err

    return ProjectJobRpcGet(
        uuid=project.uuid,
        name=project.name,
        description=project.description,
        workbench=project.workbench,
        created_at=project.creation_date,
        modified_at=project.last_change_date,
        job_parent_resource_name=project.job_parent_resource_name,
        storage_assets_deleted=project.storage_assets_deleted,
    )


async def register_rpc_routes_on_startup(app: web.Application):
    rpc_server = get_rabbitmq_rpc_server(app)
    # FIXME: should depend on the webserver instance!
    await rpc_server.register_router(router, WEBSERVER_RPC_NAMESPACE, app)

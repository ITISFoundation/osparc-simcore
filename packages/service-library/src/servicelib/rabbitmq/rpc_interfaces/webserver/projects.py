import logging
import warnings
from typing import cast

from models_library.api_schemas_webserver import DEFAULT_WEBSERVER_RPC_NAMESPACE
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rest_pagination import PageOffsetInt
from models_library.rpc.webserver.projects import (
    ListProjectsMarkedAsJobRpcFilters,
    PageRpcProjectJobRpcGet,
    ProjectJobRpcGet,
)
from models_library.rpc_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
)
from models_library.users import UserID
from pydantic import TypeAdapter, validate_call

from ....logging_utils import log_decorator
from ....rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


warnings.warn(
    f"The '{__name__}' module is deprecated and will be removed in a future release. "
    "Please use 'rpc_interfaces.webserver.v1' instead.",
    DeprecationWarning,
    stacklevel=2,
)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def mark_project_as_job(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    job_parent_resource_name: str,
    storage_assets_deleted: bool,
) -> None:

    result = await rpc_client.request(
        DEFAULT_WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("mark_project_as_job"),
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
        storage_assets_deleted=storage_assets_deleted,
    )
    assert result is None


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def list_projects_marked_as_jobs(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    # pagination
    offset: PageOffsetInt = 0,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    filters: ListProjectsMarkedAsJobRpcFilters | None = None,
) -> PageRpcProjectJobRpcGet:
    result = await rpc_client.request(
        DEFAULT_WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_projects_marked_as_jobs"),
        product_name=product_name,
        user_id=user_id,
        offset=offset,
        limit=limit,
        filters=filters,
    )
    assert TypeAdapter(PageRpcProjectJobRpcGet).validate_python(result)  # nosec
    return cast(PageRpcProjectJobRpcGet, result)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def get_project_marked_as_job(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    job_parent_resource_name: str,
) -> ProjectJobRpcGet:
    result = await rpc_client.request(
        DEFAULT_WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_project_marked_as_job"),
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )
    assert TypeAdapter(ProjectJobRpcGet).validate_python(result)  # nosec
    return cast(ProjectJobRpcGet, result)

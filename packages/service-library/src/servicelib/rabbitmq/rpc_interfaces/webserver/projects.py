import logging
from typing import cast

from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rest_pagination import PageOffsetInt
from models_library.rpc.webserver.projects import PageRpcProjectJobRpcGet
from models_library.rpc_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
)
from models_library.users import UserID
from pydantic import TypeAdapter, validate_call
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


@log_decorator(_logger, level=logging.DEBUG)
@validate_call(config={"arbitrary_types_allowed": True})
async def mark_project_as_job(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    project_uuid: ProjectID,
    job_parent_resource_name: str,
) -> None:

    result = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("mark_project_as_job"),
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
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
    # filters
    job_parent_resource_name_prefix: str | None = None,
) -> PageRpcProjectJobRpcGet:
    result = await rpc_client.request(
        WEBSERVER_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_projects_marked_as_jobs"),
        product_name=product_name,
        user_id=user_id,
        offset=offset,
        limit=limit,
        job_parent_resource_name_prefix=job_parent_resource_name_prefix,
    )
    assert TypeAdapter(PageRpcProjectJobRpcGet).validate_python(result)  # nosec
    return cast(PageRpcProjectJobRpcGet, result)

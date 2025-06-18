"""RPC client-side for the RPC server at the payments service

In this interface (and all belows), the context of the caller is passed in the following arguments:
- `user_id` is intended for the caller's identifer. Do not add other user_id that is not the callers!.
    - Ideally this could be injected by an authentication layer (as in the rest API)
        but  for now we are passing it as an argument.
- `product_name` is the name of the product at the caller's context as well

"""

import logging
from typing import cast

from models_library.api_schemas_catalog import CATALOG_RPC_NAMESPACE
from models_library.api_schemas_catalog.services import (
    LatestServiceGet,
    MyServiceGet,
    PageRpcLatestServiceGet,
    PageRpcServiceRelease,
    PageRpcServiceSummary,
    ServiceGetV2,
    ServiceListFilters,
    ServiceRelease,
    ServiceSummary,
    ServiceUpdateV2,
)
from models_library.api_schemas_catalog.services_ports import ServicePortGet
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rest_pagination import PageOffsetInt
from models_library.rpc_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
    PageRpc,
)
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import TypeAdapter, validate_call

from ....logging_utils import log_decorator
from ..._client_rpc import RabbitMQRPCClient
from ..._constants import RPC_REQUEST_DEFAULT_TIMEOUT_S

_logger = logging.getLogger(__name__)


@validate_call(config={"arbitrary_types_allowed": True})
async def list_services_paginated(  # pylint: disable=too-many-arguments
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: PageOffsetInt = 0,
    filters: ServiceListFilters | None = None,
) -> PageRpcLatestServiceGet:
    """
    Raises:
        ValidationError: on invalid arguments
        CatalogForbiddenError: no access-rights to list services
    """

    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("list_services_paginated"),
        product_name=product_name,
        user_id=user_id,
        limit=limit,
        offset=offset,
        filters=filters,
        timeout_s=40 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )

    assert (  # nosec
        TypeAdapter(PageRpc[LatestServiceGet]).validate_python(result) is not None
    )
    return cast(PageRpc[LatestServiceGet], result)


@validate_call(config={"arbitrary_types_allowed": True})
@log_decorator(_logger, level=logging.DEBUG)
async def get_service(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ServiceGetV2:
    """
    Raises:
        ValidationError: on invalid arguments
        CatalogItemNotFoundError: service not found in catalog
        CatalogForbiddenError: not access rights to read this service
    """
    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_service"),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        timeout_s=4 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )
    assert TypeAdapter(ServiceGetV2).validate_python(result) is not None  # nosec
    return cast(ServiceGetV2, result)


@validate_call(config={"arbitrary_types_allowed": True})
@log_decorator(_logger, level=logging.DEBUG)
async def update_service(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update: ServiceUpdateV2,
) -> ServiceGetV2:
    """Updates editable fields of a service

    Raises:
        ValidationError: on invalid arguments
        CatalogItemNotFoundError: service not found in catalog
        CatalogForbiddenError: not access rights to read this service
    """
    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("update_service"),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update=update,
    )
    assert TypeAdapter(ServiceGetV2).validate_python(result) is not None  # nosec
    return cast(ServiceGetV2, result)


@validate_call(config={"arbitrary_types_allowed": True})
@log_decorator(_logger, level=logging.DEBUG)
async def check_for_service(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> None:
    """

    Raises:
        ValidationError: on invalid arguments
        CatalogItemNotFoundError: service not found in catalog
        CatalogForbiddenError: not access rights to read this service
    """
    await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("check_for_service"),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )


@validate_call(config={"arbitrary_types_allowed": True})
@log_decorator(_logger, level=logging.DEBUG)
async def batch_get_my_services(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    ids: list[
        tuple[
            ServiceKey,
            ServiceVersion,
        ]
    ],
) -> list[MyServiceGet]:
    """
    Raises:
        ValidationError: on invalid arguments
        CatalogForbiddenError: no access-rights to list services
    """
    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("batch_get_my_services"),
        product_name=product_name,
        user_id=user_id,
        ids=ids,
        timeout_s=40 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )
    assert TypeAdapter(list[MyServiceGet]).validate_python(result) is not None  # nosec
    return cast(list[MyServiceGet], result)


@validate_call(config={"arbitrary_types_allowed": True})
async def list_my_service_history_latest_first(  # pylint: disable=too-many-arguments
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: PageOffsetInt = 0,
    filters: ServiceListFilters | None = None,
) -> PageRpcServiceRelease:
    """
    Sorts service releases by version (latest first)
    Raises:
        ValidationError: on invalid arguments
    """
    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python(
            "list_my_service_history_latest_first"
        ),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        limit=limit,
        offset=offset,
        filters=filters,
    )
    assert (  # nosec
        TypeAdapter(PageRpcServiceRelease).validate_python(result) is not None
    )
    return cast(PageRpc[ServiceRelease], result)


@validate_call(config={"arbitrary_types_allowed": True})
@log_decorator(_logger, level=logging.DEBUG)
async def get_service_ports(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> list[ServicePortGet]:
    """Gets service ports (inputs and outputs) for a specific service version

    Raises:
        ValidationError: on invalid arguments
        CatalogItemNotFoundError: service not found in catalog
        CatalogForbiddenError: not access rights to read this service
    """
    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_service_ports"),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert (
        TypeAdapter(list[ServicePortGet]).validate_python(result) is not None
    )  # nosec
    return cast(list[ServicePortGet], result)


@validate_call(config={"arbitrary_types_allowed": True})
async def list_all_services_summaries_paginated(  # pylint: disable=too-many-arguments
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: PageOffsetInt = 0,
    filters: ServiceListFilters | None = None,
) -> PageRpcServiceSummary:
    """Lists all services with pagination, including all versions of each service.

    Returns a lightweight summary view of services for better performance.

    Args:
        rpc_client: RPC client instance
        product_name: Product name
        user_id: User ID
        limit: Maximum number of items to return
        offset: Number of items to skip
        filters: Optional filters to apply

    Returns:
        Paginated list of all services as summaries

    Raises:
        ValidationError: on invalid arguments
        CatalogForbiddenError: no access-rights to list services
    """
    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python(
            list_all_services_summaries_paginated.__name__
        ),
        product_name=product_name,
        user_id=user_id,
        limit=limit,
        offset=offset,
        filters=filters,
        timeout_s=40 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )

    assert (
        TypeAdapter(PageRpc[ServiceSummary]).validate_python(result) is not None
    )  # nosec
    return cast(PageRpc[ServiceSummary], result)

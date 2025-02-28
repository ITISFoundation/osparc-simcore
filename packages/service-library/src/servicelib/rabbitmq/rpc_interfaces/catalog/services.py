"""RPC client-side for the RPC server at the payments service"""

import logging
from typing import Any, cast

from models_library.api_schemas_catalog import CATALOG_RPC_NAMESPACE
from models_library.api_schemas_catalog.services import (
    MyServiceGet,
    ServiceGetV2,
    ServiceItemList,
    ServiceUpdateV2,
)
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rpc_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
    PageRpc,
)
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import NonNegativeInt, TypeAdapter, validate_call
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq._constants import RPC_REQUEST_DEFAULT_TIMEOUT_S

from ..._client_rpc import RabbitMQRPCClient

_logger = logging.getLogger(__name__)


async def list_services_paginated(  # pylint: disable=too-many-arguments
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: NonNegativeInt = 0,
) -> PageRpc[ServiceItemList]:
    """
    Raises:
        ValidationError: on invalid arguments
        CatalogForbiddenError: no access-rights to list services
    """

    @validate_call()
    async def _call(
        product_name: ProductName,
        user_id: UserID,
        limit: PageLimitInt,
        offset: NonNegativeInt,
    ):
        return await rpc_client.request(
            CATALOG_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("list_services_paginated"),
            product_name=product_name,
            user_id=user_id,
            limit=limit,
            offset=offset,
            timeout_s=40 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
        )

    result = await _call(
        product_name=product_name, user_id=user_id, limit=limit, offset=offset
    )
    assert (  # nosec
        TypeAdapter(PageRpc[ServiceItemList]).validate_python(result) is not None
    )
    return cast(PageRpc[ServiceItemList], result)


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

    @validate_call()
    async def _call(
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> Any:
        return await rpc_client.request(
            CATALOG_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("get_service"),
            product_name=product_name,
            user_id=user_id,
            service_key=service_key,
            service_version=service_version,
            timeout_s=4 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
        )

    result = await _call(
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert TypeAdapter(ServiceGetV2).validate_python(result) is not None  # nosec
    return cast(ServiceGetV2, result)


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

    @validate_call()
    async def _call(
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
        update: ServiceUpdateV2,
    ):
        return await rpc_client.request(
            CATALOG_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("update_service"),
            product_name=product_name,
            user_id=user_id,
            service_key=service_key,
            service_version=service_version,
            update=update,
        )

    result = await _call(
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update=update,
    )
    assert TypeAdapter(ServiceGetV2).validate_python(result) is not None  # nosec
    return cast(ServiceGetV2, result)


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

    @validate_call()
    async def _call(
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ):
        return await rpc_client.request(
            CATALOG_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("check_for_service"),
            product_name=product_name,
            user_id=user_id,
            service_key=service_key,
            service_version=service_version,
        )

    await _call(
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )


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

    @validate_call()
    async def _call(
        product_name: ProductName,
        user_id: UserID,
        ids: list[tuple[ServiceKey, ServiceVersion]],
    ):
        return await rpc_client.request(
            CATALOG_RPC_NAMESPACE,
            TypeAdapter(RPCMethodName).validate_python("batch_get_my_services"),
            product_name=product_name,
            user_id=user_id,
            ids=ids,
            timeout_s=40 * RPC_REQUEST_DEFAULT_TIMEOUT_S,
        )

    result = await _call(product_name=product_name, user_id=user_id, ids=ids)
    assert TypeAdapter(list[MyServiceGet]).validate_python(result) is not None  # nosec
    return cast(list[MyServiceGet], result)

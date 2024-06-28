""" RPC client-side for the RPC server at the payments service

"""

import logging

from models_library.api_schemas_catalog import CATALOG_RPC_NAMESPACE
from models_library.api_schemas_catalog.services import DEVServiceGet, ServiceUpdate
from models_library.products import ProductName
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.rpc_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
    PageRpc,
)
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import Extra, NonNegativeInt, parse_obj_as, validate_arguments
from servicelib.logging_utils import log_decorator

from ..._client_rpc import RabbitMQRPCClient

_logger = logging.getLogger(__name__)
_config = {"arbitrary_types_allowed": True, "extra": Extra.ignore}


@log_decorator(_logger, level=logging.DEBUG)
@validate_arguments(config=_config)
async def list_services_paginated(  # pylint: disable=too-many-arguments
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: NonNegativeInt = 0,
) -> PageRpc[DEVServiceGet]:
    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "list_services_paginated"),
        product_name=product_name,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    assert parse_obj_as(PageRpc[DEVServiceGet], result) is not None  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
@validate_arguments(config=_config)
async def get_service(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> DEVServiceGet:

    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_service"),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert parse_obj_as(DEVServiceGet, result) is not None  # nosec
    return result


@log_decorator(_logger, level=logging.DEBUG)
@validate_arguments(config=_config)
async def update_service(
    rpc_client: RabbitMQRPCClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update: ServiceUpdate,
) -> DEVServiceGet:
    """Updates editable fields of a service"""
    result = await rpc_client.request(
        CATALOG_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "update_service"),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update=update,
    )
    assert parse_obj_as(DEVServiceGet, result) is not None  # nosec
    return result

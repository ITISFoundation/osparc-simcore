import logging

from fastapi import FastAPI
from models_library.api_schemas_catalog.services import (
    PageRpcServicesGetV2,
    ServiceGetV2,
    ServiceUpdate,
)
from models_library.products import ProductName
from models_library.rpc_pagination import DEFAULT_NUMBER_OF_ITEMS_PER_PAGE, PageLimitInt
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import NonNegativeInt, parse_obj_as
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RPCRouter

_logger = logging.getLogger(__name__)

router = RPCRouter()


@router.expose()
@log_decorator(_logger, level=logging.DEBUG)
async def list_services_paginated(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: NonNegativeInt = 0,
) -> PageRpcServicesGetV2:
    assert app  # nosec
    assert product_name  # nosec

    _logger.debug("Moking list_services_paginated for %s...", f"{user_id=}")
    items = parse_obj_as(
        list[ServiceGetV2], ServiceGetV2.Config.schema_extra["examples"]
    )
    total_count = len(items)

    return PageRpcServicesGetV2.create(
        items[offset : offset + limit],
        total=total_count,
        limit=limit,
        offset=offset,
    )


@router.expose()
@log_decorator(_logger, level=logging.DEBUG)
async def get_service(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ServiceGetV2:
    assert app  # nosec
    assert product_name  # nosec
    assert user_id  # nosec

    _logger.debug("Moking get_service for %s...", f"{user_id=}")
    got = parse_obj_as(ServiceGetV2, ServiceGetV2.Config.schema_extra["examples"][0])
    got.key = service_key
    got.version = service_version

    return got


@router.expose()
@log_decorator(_logger, level=logging.DEBUG)
async def update_service(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update: ServiceUpdate,
) -> ServiceGetV2:
    """Updates editable fields of a service"""

    assert app  # nosec
    assert product_name  # nosec
    assert user_id  # nosec

    _logger.debug("Moking update_service for %s...", f"{user_id=}")
    got = parse_obj_as(ServiceGetV2, ServiceGetV2.Config.schema_extra["examples"][0])
    got.key = service_key
    got.version = service_version
    return got.copy(update=update.dict(exclude_unset=True))

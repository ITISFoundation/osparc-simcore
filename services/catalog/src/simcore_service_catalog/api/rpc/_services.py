import logging

from fastapi import FastAPI
from models_library.api_schemas_catalog.services import DEVServiceGet, ServiceUpdate
from models_library.products import ProductName
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
    PageLimitInt,
)
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import NonNegativeInt, ValidationError, validate_arguments
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RPCRouter

_logger = logging.getLogger(__name__)

router = RPCRouter()


@router.expose(reraise_if_error_type=(ValidationError,))
@log_decorator(_logger, level=logging.DEBUG)
@validate_arguments
async def list_services_paginated(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: NonNegativeInt = 0,
) -> Page[DEVServiceGet]:
    # TODO: PageRPC
    # TODO: move body example here

    assert app  # nosec
    assert product_name  # nosec
    assert user_id  # nosec
    assert limit  # nosec
    assert offset  # nosec
    raise NotImplementedError


@router.expose(reraise_if_error_type=(ValidationError,))
@log_decorator(_logger, level=logging.DEBUG)
@validate_arguments
async def get_service(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> DEVServiceGet:
    assert app  # nosec
    assert product_name  # nosec
    assert user_id  # nosec
    assert service_key  # nosec
    assert service_version  # nosec

    raise NotImplementedError


@router.expose(reraise_if_error_type=(ValidationError,))
@log_decorator(_logger, level=logging.DEBUG)
@validate_arguments
async def update_service(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update: ServiceUpdate,
) -> DEVServiceGet:
    """Updates editable fields of a service"""

    assert app  # nosec
    assert product_name  # nosec
    assert user_id  # nosec
    assert service_key  # nosec
    assert service_version  # nosec
    assert update  # nosec

    raise NotImplementedError

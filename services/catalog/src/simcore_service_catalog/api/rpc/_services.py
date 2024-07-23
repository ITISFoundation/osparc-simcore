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
from pydantic import NonNegativeInt
from servicelib.logging_utils import log_decorator
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)

from ...db.repositories.services import ServicesRepository
from ...services import services_api
from ..dependencies.director import get_director_api

_logger = logging.getLogger(__name__)

router = RPCRouter()


@router.expose(reraise_if_error_type=(CatalogForbiddenError,))
@log_decorator(_logger, level=logging.DEBUG)
async def list_services_paginated(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: NonNegativeInt = 0,
) -> PageRpcServicesGetV2:
    assert app.state.engine  # nosec

    total_count, items = await services_api.list_services_paginated(
        repo=ServicesRepository(app.state.engine),
        director_api=get_director_api(app),
        product_name=product_name,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    assert len(items) <= total_count  # nosec
    assert len(items) <= limit  # nosec

    return PageRpcServicesGetV2.create(
        items,
        total=total_count,
        limit=limit,
        offset=offset,
    )


@router.expose(reraise_if_error_type=(CatalogItemNotFoundError, CatalogForbiddenError))
@log_decorator(_logger, level=logging.DEBUG)
async def get_service(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ServiceGetV2:
    assert app.state.engine  # nosec

    service = await services_api.get_service(
        repo=ServicesRepository(app.state.engine),
        director_api=get_director_api(app),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )

    assert service.key == service_key  # nosec
    assert service.version == service_version  # nosec

    return service


@router.expose(reraise_if_error_type=(CatalogItemNotFoundError, CatalogForbiddenError))
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

    assert app.state.engine  # nosec

    service = await services_api.update_service(
        repo=ServicesRepository(app.state.engine),
        director_api=get_director_api(app),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update=update,
    )

    assert service.key == service_key  # nosec
    assert service.version == service_version  # nosec

    return service


@router.expose(reraise_if_error_type=(CatalogItemNotFoundError, CatalogForbiddenError))
@log_decorator(_logger, level=logging.DEBUG)
async def check_for_service(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> None:
    """Checks whether service exists and can be accessed, otherwise it raise"""
    assert app.state.engine  # nosec

    await services_api.check_for_service(
        repo=ServicesRepository(app.state.engine),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )

import logging

from fastapi import FastAPI
from models_library.api_schemas_catalog.services import DEVServiceGet, ServiceUpdate
from models_library.products import ProductName
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
    PageLimitInt,
)
from models_library.rest_pagination_utils import paginate_data
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import NonNegativeInt, ValidationError, validate_arguments
from servicelib.rabbitmq import RPCRouter

from ...db.repositories.services import ServicesRepository
from ...services import services_catalog
from ..dependencies.database import get_repository

_logger = logging.getLogger(__name__)

router = RPCRouter()


@router.expose(reraise_if_error_type=(ValidationError,))
@validate_arguments
async def list_services_paginated(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    offset: NonNegativeInt = 0,
) -> Page[DEVServiceGet]:

    assert app.state.engine  # nosec

    total, services = await services_catalog.list_services_paginated(
        repo=get_repository(ServicesRepository)(engine=app.state.engine),
        product_name=product_name,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    # TODO: RPCPage ?
    #  no-limit?
    # PageLinks -> self=(offset), first=(offset, limit), next(first, limit+offset), etc SEE packages/models-library/src/models_library/rest_pagination_utils.py

    return Page[DEVServiceGet].parse_obj(
        paginate_data(
            services,
            request_url="https://invalid.io",
            total=total,
            limit=limit,
            offset=offset,
        )
    )


@router.expose(reraise_if_error_type=(ValidationError,))
@validate_arguments
async def get_service(
    app: FastAPI,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> DEVServiceGet:
    raise NotImplementedError


@router.expose(reraise_if_error_type=(ValidationError,))
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
    raise NotImplementedError

from typing import Final

from models_library.api_schemas_catalog.services import DEVServiceGet, ServiceUpdate
from models_library.products import ProductName
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    Page,
    PageLimitInt,
)
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import NonNegativeInt

LATEST_VERSION: Final = None


# TODO: RPCPage ?


async def get_page_of_services(
    product_name: ProductName,
    user_id: UserID,
    *,
    include_details: bool = True,
    offset: NonNegativeInt = 0,
    limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
) -> Page[DEVServiceGet]:

    raise NotImplementedError


async def get_service(
    product_name: ProductName,
    user_id: UserID,
    *,
    service_key: ServiceKey,
    service_version: ServiceVersion | None = LATEST_VERSION,
) -> DEVServiceGet:
    raise NotImplementedError


async def update_service(
    product_name: ProductName,
    user_id: UserID,
    *,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update: ServiceUpdate,
) -> DEVServiceGet:
    """Updates editable fields of a service"""
    raise NotImplementedError

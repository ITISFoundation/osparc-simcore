# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.api_schemas_webserver.licensed_items import (
    LicensedItemGet,
    LicensedItemGetPage,
)
from models_library.licensed_items import LicensedItemID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from pydantic import NonNegativeInt

from . import _licensed_items_db
from ._models import LicensedItemsBodyParams

_logger = logging.getLogger(__name__)


async def get_licensed_item(
    app: web.Application,
    *,
    licensed_item_id: LicensedItemID,
    product_name: ProductName,
) -> LicensedItemGet:

    licensed_item_db = await _licensed_items_db.get(
        app, licensed_item_id=licensed_item_id, product_name=product_name
    )
    return LicensedItemGet(
        licensed_item_id=licensed_item_db.licensed_item_id,
        name=licensed_item_db.name,
        licensed_resource_type=licensed_item_db.licensed_resource_type,
        pricing_plan_id=licensed_item_db.pricing_plan_id,
        created_at=licensed_item_db.created,
        modified_at=licensed_item_db.modified,
    )


async def list_licensed_items(
    app: web.Application,
    *,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> LicensedItemGetPage:
    total_count, licensed_item_db_list = await _licensed_items_db.list_(
        app, product_name=product_name, offset=offset, limit=limit, order_by=order_by
    )
    return LicensedItemGetPage(
        items=[
            LicensedItemGet(
                licensed_item_id=licensed_item_db.licensed_item_id,
                name=licensed_item_db.name,
                licensed_resource_type=licensed_item_db.licensed_resource_type,
                pricing_plan_id=licensed_item_db.pricing_plan_id,
                created_at=licensed_item_db.created,
                modified_at=licensed_item_db.modified,
            )
            for licensed_item_db in licensed_item_db_list
        ],
        total=total_count,
    )


async def purchase_licensed_item(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    licensed_item_id: LicensedItemID,
    body_params: LicensedItemsBodyParams,
) -> None:
    raise NotImplementedError

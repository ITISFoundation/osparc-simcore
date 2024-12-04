# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.api_schemas_webserver.license_goods import (
    LicenseGoodGet,
    LicenseGoodGetPage,
)
from models_library.license_goods import LicenseGoodID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.users import UserID
from pydantic import NonNegativeInt

from . import _license_goods_db
from ._models import LicenseGoodsBodyParams

_logger = logging.getLogger(__name__)


async def get_license_good(
    app: web.Application,
    *,
    license_good_id: LicenseGoodID,
    product_name: ProductName,
) -> LicenseGoodGet:

    license_good_db = await _license_goods_db.get(
        app, license_good_id=license_good_id, product_name=product_name
    )
    return LicenseGoodGet(
        license_good_id=license_good_db.license_good_id,
        name=license_good_db.name,
        license_resource_type=license_good_db.license_resource_type,
        pricing_plan_id=license_good_db.pricing_plan_id,
        created_at=license_good_db.created,
        modified_at=license_good_db.modified,
    )


async def list_license_goods(
    app: web.Application,
    *,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> LicenseGoodGetPage:
    total_count, license_good_db_list = await _license_goods_db.list_(
        app, product_name=product_name, offset=offset, limit=limit, order_by=order_by
    )
    return LicenseGoodGetPage(
        items=[
            LicenseGoodGet(
                license_good_id=license_good_db.license_good_id,
                name=license_good_db.name,
                license_resource_type=license_good_db.license_resource_type,
                pricing_plan_id=license_good_db.pricing_plan_id,
                created_at=license_good_db.created,
                modified_at=license_good_db.modified,
            )
            for license_good_db in license_good_db_list
        ],
        total=total_count,
    )


async def purchase_license_good(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    license_good_id: LicenseGoodID,
    body_params: LicenseGoodsBodyParams,
) -> None:
    raise NotImplementedError

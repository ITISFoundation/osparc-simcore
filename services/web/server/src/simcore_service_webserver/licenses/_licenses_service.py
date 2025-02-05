# pylint: disable=unused-argument

import logging

from aiohttp import web
from models_library.licenses import License, LicenseID
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from pydantic import NonNegativeInt

from . import _licenses_repository
from ._common.models import LicensePage

_logger = logging.getLogger(__name__)


async def get_license(
    app: web.Application,
    *,
    license_id: LicenseID,
    product_name: ProductName,
) -> License:
    return await _licenses_repository.get_license(
        app, license_id=license_id, product_name=product_name
    )


async def list_licenses(
    app: web.Application,
    *,
    product_name: ProductName,
    offset: NonNegativeInt,
    limit: int,
    order_by: OrderBy,
) -> LicensePage:
    total_count, items = await _licenses_repository.list_licenses(
        app,
        product_name=product_name,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )
    return LicensePage(
        items=items,
        total=total_count,
    )

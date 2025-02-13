""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends
from models_library.api_schemas_webserver.licensed_items import LicensedItemRestGet
from models_library.api_schemas_webserver.licensed_items_purchases import (
    LicensedItemPurchaseGet,
)
from models_library.rest_error import EnvelopedError
from models_library.rest_pagination import Page
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.licenses._common.exceptions_handlers import (
    _TO_HTTP_ERROR_MAP,
)
from simcore_service_webserver.licenses._common.models import (
    LicensedItemsBodyParams,
    LicensedItemsListQueryParams,
    LicensedItemsPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "licenses",
        "catalog",
    ],
    responses={
        i.status_code: {"model": EnvelopedError} for i in _TO_HTTP_ERROR_MAP.values()
    },
)


@router.get(
    "/catalog/licensed-items",
    response_model=Page[LicensedItemRestGet],
)
async def list_licensed_items(
    _query: Annotated[as_query(LicensedItemsListQueryParams), Depends()],
):
    ...


@router.post(
    "/catalog/licensed-items/{licensed_item_id}:purchase",
    response_model=LicensedItemPurchaseGet,
)
async def purchase_licensed_item(
    _path: Annotated[LicensedItemsPathParams, Depends()],
    _body: LicensedItemsBodyParams,
):
    ...

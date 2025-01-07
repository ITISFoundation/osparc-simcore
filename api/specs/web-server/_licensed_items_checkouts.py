""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends
from models_library.api_schemas_webserver.licensed_items_purchases import (
    LicensedItemPurchaseGet,
)
from models_library.generics import Envelope
from models_library.rest_error import EnvelopedError
from models_library.rest_pagination import Page
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.licenses._exceptions_handlers import _TO_HTTP_ERROR_MAP
from simcore_service_webserver.licenses._licensed_items_checkouts_models import (
    LicensedItemCheckoutPathParams,
    LicensedItemsCheckoutsListQueryParams,
)
from simcore_service_webserver.wallets._handlers import WalletsPathParams

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "licenses",
    ],
    responses={
        i.status_code: {"model": EnvelopedError} for i in _TO_HTTP_ERROR_MAP.values()
    },
)


@router.get(
    "/wallets/{wallet_id}/licensed-items-checkouts",
    response_model=Page[LicensedItemPurchaseGet],
    tags=["wallets"],
)
async def list_licensed_item_checkouts_for_wallet(
    _path: Annotated[WalletsPathParams, Depends()],
    _query: Annotated[as_query(LicensedItemsCheckoutsListQueryParams), Depends()],
):
    ...


@router.get(
    "/licensed-items-checkouts/{licensed_item_checkout_id}",
    response_model=Envelope[LicensedItemPurchaseGet],
)
async def get_licensed_item_checkout(
    _path: Annotated[LicensedItemCheckoutPathParams, Depends()],
):
    ...

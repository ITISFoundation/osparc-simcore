""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.licensed_items import LicensedItemGet
from models_library.generics import Envelope
from models_library.rest_error import EnvelopedError
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.licenses._exceptions_handlers import _TO_HTTP_ERROR_MAP
from simcore_service_webserver.licenses._models import (
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
    response_model=Envelope[list[LicensedItemGet]],
)
async def list_licensed_items(
    _query: Annotated[as_query(LicensedItemsListQueryParams), Depends()],
):
    ...


@router.get(
    "/catalog/licensed-items/{licensed_item_id}",
    response_model=Envelope[LicensedItemGet],
)
async def get_licensed_item(
    _path: Annotated[LicensedItemsPathParams, Depends()],
):
    ...


@router.post(
    "/catalog/licensed-items/{licensed_item_id}:purchase",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def purchase_licensed_item(
    _path: Annotated[LicensedItemsPathParams, Depends()],
    _body: LicensedItemsBodyParams,
):
    ...

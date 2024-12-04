""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.license_goods import LicenseGoodGet
from models_library.generics import Envelope
from models_library.rest_error import EnvelopedError
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.licenses._exceptions_handlers import _TO_HTTP_ERROR_MAP
from simcore_service_webserver.licenses._models import (
    LicenseGoodsBodyParams,
    LicenseGoodsListQueryParams,
    LicenseGoodsPathParams,
)

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
    "/license-goods",
    response_model=Envelope[list[LicenseGoodGet]],
)
async def list_workspaces(
    _query: Annotated[as_query(LicenseGoodsListQueryParams), Depends()],
):
    ...


@router.get(
    "/license-goods/{license_good_id}",
    response_model=Envelope[LicenseGoodGet],
)
async def get_workspace(
    _path: Annotated[LicenseGoodsPathParams, Depends()],
):
    ...


@router.post("/license-goods/{license_good_id}", status_code=status.HTTP_204_NO_CONTENT)
async def create_workspace_group(
    _path: Annotated[LicenseGoodsPathParams, Depends()],
    _body: LicenseGoodsBodyParams,
):
    ...

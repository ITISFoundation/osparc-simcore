# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_webserver.product import (
    GenerateInvitation,
    GetCreditPrice,
    GetProduct,
    InvitationGenerated,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.products._handlers import _ProductsRequestParams

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "products",
    ],
)


@router.get(
    "/credits-price",
    response_model=Envelope[GetCreditPrice],
)
async def get_current_product_price():
    ...


@router.get(
    "/products/{product_name}",
    response_model=Envelope[GetProduct],
)
async def get_product(_params: Annotated[_ProductsRequestParams, Depends()]):
    ...


@router.post(
    "/invitation:generate",
    response_model=Envelope[InvitationGenerated],
)
async def generate_invitation(_body: GenerateInvitation):
    ...

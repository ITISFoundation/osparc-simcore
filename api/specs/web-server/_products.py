# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from fastapi import APIRouter
from models_library.api_schemas_webserver.product import (
    CreditPriceGet,
    GenerateInvitation,
    InvitationGenerated,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "products",
    ],
)


@router.get(
    "/credits-price",
    response_model=Envelope[CreditPriceGet],
)
async def get_current_product_price():
    ...


@router.post(
    "/invitation:generate",
    response_model=Envelope[InvitationGenerated],
)
async def generate_invitation(_body: GenerateInvitation):
    ...

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.product import (
    GenerateInvitation,
    GetCreditPrice,
    InvitationGenerated,
    ProductGet,
    ProductUIGet,
    UpdateProductTemplate,
)
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.products._rest import (
    _ProductsRequestParams,
    _ProductTemplateParams,
)

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
    response_model=Envelope[ProductGet],
    description="NOTE: `/products/current` is used to define current project w/o naming it",
    tags=[
        "po",
    ],
)
async def get_product(_params: Annotated[_ProductsRequestParams, Depends()]):
    ...


@router.get(
    "/products/current/ui",
    response_model=Envelope[ProductUIGet],
)
async def get_current_product_ui():
    ...


@router.put(
    "/products/{product_name}/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=[
        "po",
    ],
)
async def update_product_template(
    _params: Annotated[_ProductTemplateParams, Depends()], _body: UpdateProductTemplate
):
    ...


@router.post(
    "/invitation:generate",
    response_model=Envelope[InvitationGenerated],
    tags=[
        "po",
    ],
)
async def generate_invitation(_body: GenerateInvitation):
    ...

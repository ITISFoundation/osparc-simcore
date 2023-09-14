# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from fastapi import APIRouter
from models_library.api_schemas_webserver.product import ProductPriceGet
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "products",
    ],
)


@router.get(
    "/price",
    response_model=Envelope[ProductPriceGet],
)
async def get_current_product_price():
    ...

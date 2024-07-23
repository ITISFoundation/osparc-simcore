from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.product import GetCreditPrice

from ..dependencies.webserver import AuthSession, get_webserver_session

router = APIRouter()


@router.get("/price", status_code=status.HTTP_200_OK, response_model=GetCreditPrice)
async def get_credits_price(
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    product_price = await webserver_api.get_product_price()
    return product_price

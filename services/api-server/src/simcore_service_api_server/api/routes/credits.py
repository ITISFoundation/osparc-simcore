from typing import Annotated

from fastapi import APIRouter, Depends, status

from ...models.schemas.model_adapter import GetCreditPriceLegacy
from ..dependencies.webserver_http import AuthSession, get_webserver_session
from ._constants import FMSG_CHANGELOG_NEW_IN_VERSION, create_route_description

router = APIRouter()


@router.get(
    "/price",
    status_code=status.HTTP_200_OK,
    response_model=GetCreditPriceLegacy,
    description=create_route_description(
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.6"),
        ]
    ),
)
async def get_credits_price(
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_product_price()

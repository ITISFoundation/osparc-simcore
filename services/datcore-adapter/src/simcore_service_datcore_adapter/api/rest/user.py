import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from servicelib.fastapi.requests_decorators import cancel_on_disconnect
from starlette import status

from ...models.user import Profile
from ...modules.pennsieve import PennsieveApiClient
from ..dependencies.pennsieve import get_pennsieve_api_client

router = APIRouter()
log = logging.getLogger(__file__)


@router.get(
    "/user/profile",
    summary="returns the user profile",
    status_code=status.HTTP_200_OK,
    response_model=Profile,
)
@cancel_on_disconnect
async def get_user_profile(
    request: Request,
    x_datcore_api_key: Annotated[str, Header(..., description="Datcore API Key")],
    x_datcore_api_secret: Annotated[str, Header(..., description="Datcore API Secret")],
    pennsieve_client: Annotated[PennsieveApiClient, Depends(get_pennsieve_api_client)],
):
    assert request  # nosec
    return await pennsieve_client.get_user_profile(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
    )

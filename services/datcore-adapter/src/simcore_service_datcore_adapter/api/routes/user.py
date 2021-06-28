import logging

from fastapi import APIRouter, Depends, Header
from starlette import status

from ...models.domains.user import Profile
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
async def get_user_profile(
    x_datcore_api_key: str = Header(..., description="Datcore API Key"),
    x_datcore_api_secret: str = Header(..., description="Datcore API Secret"),
    pennsieve_client: PennsieveApiClient = Depends(get_pennsieve_api_client),
):
    return await pennsieve_client.get_user_profile(
        api_key=x_datcore_api_key,
        api_secret=x_datcore_api_secret,
    )

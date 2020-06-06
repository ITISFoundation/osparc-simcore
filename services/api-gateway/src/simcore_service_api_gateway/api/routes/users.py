from fastapi import APIRouter, Depends, Security

from ...models.schemas.users import UserInResponse
from ..dependencies.authentication import get_active_user_id

router = APIRouter()


@router.get("", response_model=UserInResponse)
async def get_my_profile(user_id: int = Depends(get_active_user_id)):
    # TODO: Replace code by calls to web-server api
    return user_id


@router.patch("", response_model=UserInResponse)
async def update_my_profile(
    user_id: int = Security(get_active_user_id, scopes=["write"])
):
    # TODO: Replace code by calls to web-server api
    return user_id

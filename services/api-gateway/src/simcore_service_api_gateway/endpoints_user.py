from fastapi import APIRouter, Depends, Security

from .api_dependencies_auth import get_active_user_id
from .models.schemas.users import UserInResponse

router = APIRouter()


@router.get("/user", response_model=UserInResponse)
async def get_my_profile(user_id: int = Depends(get_active_user_id)):
    # TODO: Replace code by calls to web-server api
    return user_id


@router.patch("/user", response_model=UserInResponse)
async def update_my_profile(
    user_id: int = Security(get_active_user_id, scopes=["write"])
):
    # TODO: Replace code by calls to web-server api
    return user_id

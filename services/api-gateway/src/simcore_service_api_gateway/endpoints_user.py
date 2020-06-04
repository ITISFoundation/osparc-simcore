from fastapi import APIRouter, Depends, Security

from .auth import get_current_active_user
from .schemas import User

# from . import crud_users as crud

router = APIRouter()


@router.get("/user", response_model=User)
async def get_my_profile(current_user: User = Depends(get_current_active_user)):

    # TODO: conn??
    my_profile = current_user
    # my_profile = await crud.get_profile_by_userid(conn, current_user_id)
    return my_profile


@router.patch("/user", response_model=User)
async def update_my_profile(
    current_user: User = Security(get_current_active_user, scopes=["write"])
):
    return current_user

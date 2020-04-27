from fastapi import APIRouter, Depends, Security

from .auth import get_current_active_user
from .schemas import User

router = APIRouter()


@router.get("/user", response_model=User)
async def get_my_profile(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.patch("/user", response_model=User)
async def update_my_profile(current_user: User = Depends(get_current_active_user)):
    return current_user

from fastapi import APIRouter, Depends, Security

from .auth import get_current_active_user
from .schemas import User

router = APIRouter()


@router.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.get("/users/me/projects/")
async def list_own_projects(
    current_user: User = Security(get_current_active_user, scopes=["projects"])
):
    return [{"project_id": "Foo", "owner": current_user.username}]

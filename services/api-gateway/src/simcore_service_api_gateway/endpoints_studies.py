from fastapi import APIRouter, Security

from .auth import get_current_active_user
from .schemas import User

router = APIRouter()


@router.get("/studies")
async def list_studies(
    current_user: User = Security(get_current_active_user, scopes=["read"])
):
    return [{"project_id": "Foo", "owner": current_user.username}]


@router.get("/studies/{study_id}")
async def get_study(
    study_id: str,
    current_user: User = Security(get_current_active_user, scopes=["read"]),
):
    return [{"project_id": study_id, "owner": current_user.username}]


@router.post("/studies")
async def create_study(
    current_user: User = Security(get_current_active_user, scopes=["write"])
):
    return {"project_id": "Foo", "owner": current_user.username}


@router.put("/studies/{study_id}")
async def replace_study(
    study_id: str,
    current_user: User = Security(get_current_active_user, scopes=["write"]),
):
    return {"project_id": study_id, "owner": current_user.username}


@router.patch("/studies/{study_id}")
async def update_study(
    study_id: str,
    current_user: User = Security(get_current_active_user, scopes=["write"]),
):
    return {"project_id": study_id, "owner": current_user.username}


@router.delete("/studies/{study_id}")
async def delete_study(
    study_id: str,
    current_user: User = Security(get_current_active_user, scopes=["write"]),
):
    _data = {"project_id": study_id, "owner": current_user.username}
    return None

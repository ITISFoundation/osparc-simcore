from fastapi import APIRouter, Security

from .api_dependencies_auth import get_active_user_id

router = APIRouter()


@router.get("/studies")
async def list_studies(user_id: int = Security(get_active_user_id, scopes=["read"])):
    # TODO: Replace code by calls to web-server api
    return [{"project_id": "Foo", "owner": user_id}]


@router.get("/studies/{study_id}")
async def get_study(
    study_id: str, user_id: int = Security(get_active_user_id, scopes=["read"]),
):
    # TODO: Replace code by calls to web-server api
    return [{"project_id": study_id, "owner": user_id}]


@router.post("/studies")
async def create_study(user_id: int = Security(get_active_user_id, scopes=["write"])):
    # TODO: Replace code by calls to web-server api
    return {"project_id": "Foo", "owner": user_id}


@router.put("/studies/{study_id}")
async def replace_study(
    study_id: str, user_id: int = Security(get_active_user_id, scopes=["write"]),
):
    # TODO: Replace code by calls to web-server api
    return {"project_id": study_id, "owner": user_id}


@router.patch("/studies/{study_id}")
async def update_study(
    study_id: str, user_id: int = Security(get_active_user_id, scopes=["write"]),
):
    # TODO: Replace code by calls to web-server api
    return {"project_id": study_id, "owner": user_id}


@router.delete("/studies/{study_id}")
async def delete_study(
    study_id: str, user_id: int = Security(get_active_user_id, scopes=["write"]),
):
    # TODO: Replace code by calls to web-server api
    _data = {"project_id": study_id, "owner": user_id}
    return None

from fastapi import APIRouter
from pydantic import BaseModel

# MODELS -----------------------------------------------------------------------------------------


class Profile(BaseModel):
    ...


class ProfileUpdate(BaseModel):
    ...


# ROUTES -----------------------------------------------------------------------------------------

router = APIRouter()


@router.get("", response_model=Profile)
async def get_my_profile():
    ...


@router.put("", response_model=Profile)
async def update_my_profile(profile_update: ProfileUpdate):
    ...

# FIXME: Until tests
# pylint: skip-file
#

from fastapi import APIRouter, Depends, Security

from ...models.schemas.profiles import Profile, ProfileUpdate
from ..dependencies.authentication import get_active_user_id

router = APIRouter()


@router.get("", response_model=Profile)
async def get_my_profile(user_id: int = Depends(get_active_user_id)):
    # TODO: Replace code by calls to web-server api
    return  # Profile.fake()


@router.patch("", response_model=Profile)
async def update_my_profile(
    profile_update: ProfileUpdate,
    user_id: int = Security(get_active_user_id, scopes=["write"]),
):
    # TODO: Replace code by calls to web-server api
    return  # Profile.fake()

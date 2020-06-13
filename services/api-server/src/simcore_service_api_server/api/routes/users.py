# FIXME: Until tests
# pylint: skip-file
#

from fastapi import APIRouter, Depends, Security

from ...models.schemas.profiles import Profile, ProfileUpdate
from ..dependencies.authentication import get_active_user_id

router = APIRouter()


FAKE_PROFILE = Profile.parse_obj(
    {
        "first_name": "James",
        "last_name": "Maxwell",
        "login": "user@example.com",
        "role": "ANONYMOUS",
        "groups": {
            "me": {"gid": "string", "label": "string", "description": "string"},
            "organizations": [
                {"gid": "string", "label": "string", "description": "string"}
            ],
            "all": {"gid": "string", "label": "string", "description": "string"},
        },
        "gravatar_id": "string",
    }
)



@router.get("", response_model=Profile)
async def get_my_profile(user_id: int = Depends(get_active_user_id)):
    # TODO: Replace code by calls to web-server api
    return FAKE_PROFILE


@router.patch("", response_model=Profile)
async def update_my_profile(
    profile_update: ProfileUpdate,
    user_id: int = Security(get_active_user_id, scopes=["write"]),
):
    global FAKE_PROFILE
    FAKE_PROFILE = FAKE_PROFILE.copy(update=profile_update.dict())
    # TODO: Replace code by calls to web-server api
    return FAKE_PROFILE

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Security

from ...models.schemas.profiles import Profile, ProfileUpdate
from ...services.webserver import AuthSession
from ..dependencies.webserver import get_webserver_session

_logger = logging.getLogger(__name__)


router = APIRouter()


@router.get("", response_model=Profile)
async def get_my_profile(
    webserver_session: Annotated[AuthSession, Depends(get_webserver_session)],
) -> Profile:
    data = await webserver_session.get("/me")
    return Profile.parse_obj(data)


@router.put("", response_model=Profile)
async def update_my_profile(
    profile_update: ProfileUpdate,
    webserver_session: Annotated[
        AuthSession, Security(get_webserver_session, scopes=["write"])
    ],
) -> Profile:
    await webserver_session.put("/me", body=profile_update.dict(exclude_none=True))
    profile: Profile = await get_my_profile(webserver_session)
    return profile

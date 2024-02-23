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
    profile: Profile = await webserver_session.get_me()
    return profile


@router.put("", response_model=Profile)
async def update_my_profile(
    profile_update: ProfileUpdate,
    webserver_session: Annotated[
        AuthSession, Security(get_webserver_session, scopes=["write"])
    ],
) -> Profile:
    profile: Profile = await webserver_session.update_me(profile_update)
    return profile

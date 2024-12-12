import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Security, status

from ...exceptions.service_errors_utils import DEFAULT_BACKEND_SERVICE_STATUS_CODES
from ...models.schemas.errors import ErrorGet
from ...models.schemas.profiles import Profile, ProfileUpdate
from ...services_http.webserver import AuthSession
from ..dependencies.webserver import get_webserver_session

_logger = logging.getLogger(__name__)


router = APIRouter()

_USER_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "User not found",
        "model": ErrorGet,
    },
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}


@router.get("", response_model=Profile, responses=_USER_STATUS_CODES)
async def get_my_profile(
    webserver_session: Annotated[AuthSession, Depends(get_webserver_session)],
) -> Profile:
    profile: Profile = await webserver_session.get_me()
    return profile


@router.put("", response_model=Profile, responses=_USER_STATUS_CODES)
async def update_my_profile(
    profile_update: ProfileUpdate,
    webserver_session: Annotated[
        AuthSession, Security(get_webserver_session, scopes=["write"])
    ],
) -> Profile:
    profile: Profile = await webserver_session.update_me(profile_update=profile_update)
    return profile

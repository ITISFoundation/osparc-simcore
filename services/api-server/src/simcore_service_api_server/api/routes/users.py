from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Security
from httpx import AsyncClient, Response, StatusCode
from loguru import logger
from starlette import status

from ...models.schemas.profiles import Profile, ProfileUpdate
from ..dependencies.webserver import get_session_cookie, get_webserver_client

# from ...db.repositories.users import UsersRepository
# from ..dependencies.authentication import get_active_user_id
# from ..dependencies.database import get_repository

router = APIRouter()

# SEE: https://www.python-httpx.org/async/
# TODO: path mapping and operation
# TODO: if fails, raise for status and translates to service unavailable if fails
#


@router.get("", response_model=Profile)
async def get_my_profile(
    client: AsyncClient = Depends(get_webserver_client),
    session_cookies: Dict = Depends(get_session_cookie),
) -> Profile:
    response = await client.get("/me/", cookies=session_cookies)
    profile = Profile.parse_obj(response.json())
    return profile


@router.patch("", response_model=Profile)
async def update_my_profile(
    profile_update: ProfileUpdate,
    client: AsyncClient = Depends(get_webserver_client),
    session_cookies: Dict = Security(get_session_cookie, scopes=["write"]),
) -> Profile:
    resp: Response = await client.patch(
        "/me/", data=profile_update.dict(), cookies=session_cookies
    )

    if StatusCode.is_server_error(resp.status_code):
        logger.error(resp.reason_phrase)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

    profile = await get_my_profile(client, session_cookies)
    return profile


####### BACKUP ####

# FAKE_PROFILE = Profile.parse_obj(
#     {
#         "first_name": "James",
#         "last_name": "Maxwell",
#         "login": "user@example.com",
#         "role": "ANONYMOUS",
#         "groups": {
#             "me": {"gid": "string", "label": "string", "description": "string"},
#             "organizations": [
#                 {"gid": "string", "label": "string", "description": "string"}
#             ],
#             "all": {"gid": "string", "label": "string", "description": "string"},
#         },
#         "gravatar_id": "string",
#     }
# )
# @router.get("", response_model=Profile)
# async def get_my_profile(
#     user_id: int = Depends(get_active_user_id),
#     users_repo: UsersRepository = Depends(get_repository(UsersRepository)),
# ):
#     profile = await users_repo.get_my_profile(user_id)
#     if not profile:
#         # FIXME: headers!
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid profile"
#         )
#     return profile


# @router.patch("", response_model=Profile)
# async def update_my_profile(
#     profile_update: ProfileUpdate,
#     user_id: int = Security(get_active_user_id, scopes=["write"]),
# ):
#     global FAKE_PROFILE
#     FAKE_PROFILE = FAKE_PROFILE.copy(update=profile_update.dict())
#     return FAKE_PROFILE

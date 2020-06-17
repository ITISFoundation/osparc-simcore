from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Security
from httpx import AsyncClient, Response, StatusCode
from loguru import logger

# SEE: https://www.python-httpx.org/async/
# TODO: path mapping and operation
# TODO: if fails, raise for status and translates to service unavailable if fails
#
from pydantic import ValidationError
from starlette import status

from ...models.schemas.profiles import Profile, ProfileUpdate
from ..dependencies.webserver import get_session_cookie, get_webserver_client

router = APIRouter()


@router.get("", response_model=Profile)
async def get_my_profile(
    client: AsyncClient = Depends(get_webserver_client),
    session_cookies: Dict = Depends(get_session_cookie),
) -> Profile:
    resp = await client.get("/v0/me", cookies=session_cookies)

    if resp.status_code == status.HTTP_200_OK:
        data = resp.json()["data"]
        try:
            # FIXME: temporary patch until web-API is reviewed
            data["role"] = data["role"].upper()
            profile = Profile.parse_obj(data)
            return profile
        except ValidationError:
            logger.exception("webserver response invalid")
            raise

    elif StatusCode.is_server_error(resp.status_code):
        logger.error("webserver failed :{}", resp.reason_phrase)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

    raise HTTPException(resp.status_code, resp.reason_phrase)


@router.put("", response_model=Profile)
async def update_my_profile(
    profile_update: ProfileUpdate,
    client: AsyncClient = Depends(get_webserver_client),
    session_cookies: Dict = Security(get_session_cookie, scopes=["write"]),
) -> Profile:
    # FIXME: replace by patch
    # TODO: improve. from patch -> put, we need to ensure it has a default in place
    profile_update.first_name = profile_update.first_name or ""
    profile_update.last_name = profile_update.last_name or ""
    resp: Response = await client.put(
        "/v0/me", json=profile_update.dict(), cookies=session_cookies
    )

    if StatusCode.is_error(resp.status_code):
        logger.error("webserver failed: {}", resp.reason_phrase)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

    profile = await get_my_profile(client, session_cookies)
    return profile

import functools
import time
from typing import Optional, TypedDict

from aiohttp import web
from pydantic import PositiveInt, validate_arguments
from servicelib.aiohttp.typing_extension import Handler

from .session import get_session
from .session_settings import SessionSettings, get_plugin_settings

SESSION_GRANTED_ACCESS_TOKENS_KEY = f"{__name__}.SESSION_GRANTED_ACCESS_TOKENS_KEY"


class AccessToken(TypedDict, total=True):
    count: int
    expires: int  # time in seconds since the epoch as a floating point number.


def consume_access(token: AccessToken) -> None:
    token["count"] = -1


_MINUTES = 60
EXPIRATION_INTERVAL_SECS = 30 * _MINUTES


def is_expired(token: AccessToken) -> bool:
    return token["expires"] <= time.time()


@validate_arguments
def on_success_grant_session_access_to(
    name: str,
    *,
    max_access_count: PositiveInt = 1,
):
    """Creates access token if handle suceeds with 2XX"""

    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request):
            session = await get_session(request)

            response = await handler(request)

            if response.status < 400:  # success
                settings: SessionSettings = get_plugin_settings(request.app)

                granted_access_tokens = session.setdefault(
                    SESSION_GRANTED_ACCESS_TOKENS_KEY, {}
                )
                # NOTE: does NOT add up access counts but re-assigns to max_access_count
                granted_access_tokens[name] = AccessToken(
                    count=max_access_count,
                    expires=time.time()
                    + settings.SESSION_ACCESS_TOKENS_EXPIRATION_INTERVAL_SECS,
                )

            return response

        return _wrapper

    return _decorator


def session_access_required(
    name: str,
    *,
    unauthorized_reason: Optional[str] = None,
    one_time_access: bool = True,
    remove_all_on_success: bool = False,
):
    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request):
            session = await get_session(request)
            granted_access_tokens = session.get(SESSION_GRANTED_ACCESS_TOKENS_KEY, {})

            try:
                access_token: Optional[AccessToken] = granted_access_tokens.get(
                    name, None
                )
                if not access_token:
                    raise web.HTTPUnauthorized(reason=unauthorized_reason)

                access_token["count"] -= 1  # consume access count
                if access_token["count"] < 0 or is_expired(access_token):
                    raise web.HTTPUnauthorized(reason=unauthorized_reason)

                # update and keep for future accesses (e.g. retry this route)
                granted_access_tokens[name] = access_token

                # Access granted to this handler
                response = await handler(request)

                if response.status < 400:  # success
                    if one_time_access:
                        # avoids future accesses by clearing all tokens
                        granted_access_tokens.pop(name, None)

                    if remove_all_on_success:
                        # all access tokens removed
                        granted_access_tokens = {}

                return response

            finally:
                # prunes
                session[SESSION_GRANTED_ACCESS_TOKENS_KEY] = {
                    name: access_token
                    for name, access_token in granted_access_tokens.items()
                    if access_token["count"] > 0 and not is_expired(access_token)
                }

        return _wrapper

    return _decorator

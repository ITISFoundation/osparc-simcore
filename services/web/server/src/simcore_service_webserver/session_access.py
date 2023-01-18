import functools
from typing import Optional

from aiohttp import web
from pydantic import PositiveInt, validate_arguments
from servicelib.aiohttp.typing_extension import Handler

from .session import get_session

SESSION_GRANTED_ACCESS_TOKENS_KEY = f"{__name__}.SESSION_GRANTED_ACCESS_TOKENS_KEY"


@validate_arguments
def on_success_grant_session_access_to(
    name: str,
    max_access_count: PositiveInt = 1,
):
    """Creates access token if handle suceeds with 2XX"""

    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request):
            session = await get_session(request)

            response = await handler(request)

            if response.status < 400:  # success
                granted_access_tokens = session.setdefault(
                    SESSION_GRANTED_ACCESS_TOKENS_KEY, {}
                )
                # NOTE: does NOT add up access counts but re-assigns to max_access_count
                granted_access_tokens[name] = max_access_count

            return response

        return _wrapper

    return _decorator


def session_access_required(
    name: str,
    unauthorized_reason: Optional[str] = None,
    one_time_access: bool = True,
):
    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request):
            session = await get_session(request)
            granted_access_tokens = session.get(SESSION_GRANTED_ACCESS_TOKENS_KEY, {})

            try:
                access_count: int = granted_access_tokens.get(name, 0)
                access_count -= 1  # consume access count
                if access_count < 0:
                    raise web.HTTPUnauthorized(reason=unauthorized_reason)

                # update and keep for future accesses (e.g. retry this route)
                granted_access_tokens[name] = access_count

                # Access granted to this handler
                response = await handler(request)

                if response.status < 400:  # success
                    if one_time_access:
                        # avoids future accesses by clearing all tokens
                        granted_access_tokens.pop(name, None)

                return response

            finally:
                # prunes
                session[SESSION_GRANTED_ACCESS_TOKENS_KEY] = {
                    name: access_count
                    for name, access_count in granted_access_tokens.items()
                    if access_count > 0
                }

        return _wrapper

    return _decorator

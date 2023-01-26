import functools
import logging
import time
from contextlib import contextmanager
from typing import Iterator, Optional, TypedDict

from aiohttp import web
from aiohttp_session import Session
from pydantic import PositiveInt, validate_arguments
from servicelib.aiohttp.typing_extension import Handler

from .session import get_session
from .session_settings import SessionSettings, get_plugin_settings

SESSION_GRANTED_ACCESS_TOKENS_KEY = f"{__name__}.SESSION_GRANTED_ACCESS_TOKENS_KEY"

logger = logging.getLogger(__name__)


class AccessToken(TypedDict, total=True):
    count: int
    expires: int  # time in seconds since the epoch as a floating point number.


def is_expired(token: AccessToken) -> bool:
    expired = token["expires"] <= time.time()
    logger.debug("%s -> %s", f"{token=}", f"{expired=}")
    return expired


@contextmanager
def access_tokens_cleanup_ctx(session: Session) -> Iterator[dict[str, AccessToken]]:
    # WARNING: make sure this does not wrapp any ``await handler(request)``
    # Note that these access_tokens correspond to the values BEFORE that call
    # and all the tokens added/removed in the decorators nested on the handler
    # are not updated on ``access_tokens`` returned.
    access_tokens = {}
    try:
        access_tokens = session.setdefault(SESSION_GRANTED_ACCESS_TOKENS_KEY, {})

        yield access_tokens

    finally:

        def _is_valid(token) -> bool:
            # NOTE: We have experience (old) tokens that
            # were not deserialized as AccessToken dicts
            try:
                return token["count"] > 0 and not is_expired(token)
            except (KeyError, TypeError):
                return False

        # prunes
        pruned_access_tokens = {
            name: token for name, token in access_tokens.items() if _is_valid(token)
        }
        session[SESSION_GRANTED_ACCESS_TOKENS_KEY] = pruned_access_tokens


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
                with access_tokens_cleanup_ctx(session) as access_tokens:
                    # NOTE: does NOT add up access counts but re-assigns to max_access_count
                    access_tokens[name] = AccessToken(
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

            with access_tokens_cleanup_ctx(session) as access_tokens:
                access: Optional[AccessToken] = access_tokens.get(name, None)
                if not access:
                    raise web.HTTPUnauthorized(reason=unauthorized_reason)

                access["count"] -= 1  # consume access count
                if access["count"] < 0 or is_expired(access):
                    raise web.HTTPUnauthorized(reason=unauthorized_reason)

                # update and keep for future accesses (e.g. retry this route)
                access_tokens[name] = access

            # Access granted to this handler
            response = await handler(request)

            if response.status < 400:  # success
                with access_tokens_cleanup_ctx(session) as access_tokens:
                    if one_time_access:
                        # avoids future accesses by clearing all tokens
                        access_tokens.pop(name, None)

                    if remove_all_on_success:
                        # all access tokens removed
                        access_tokens = {}

            return response

        return _wrapper

    return _decorator

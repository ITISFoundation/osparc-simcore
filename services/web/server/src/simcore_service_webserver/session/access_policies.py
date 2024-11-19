import functools
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

from aiohttp import web
from aiohttp_session import Session
from pydantic import PositiveInt, validate_call
from servicelib.aiohttp import status
from servicelib.aiohttp.typing_extension import Handler
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

from .api import get_session
from .settings import SessionSettings, get_plugin_settings

_SESSION_GRANTED_ACCESS_TOKENS_KEY: Final = (
    f"{__name__}._SESSION_GRANTED_ACCESS_TOKENS_KEY"
)

# Errors start in this code https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/400
_HTTP_400_BAD_REQUEST: Final = status.HTTP_400_BAD_REQUEST

_logger = logging.getLogger(__name__)


class _AccessToken(TypedDict, total=True):
    count: int
    expires: int  # time in seconds since the epoch as a floating point number.


def _is_expired(token: _AccessToken) -> bool:
    expired = token["expires"] <= time.time()
    _logger.debug("%s -> %s", f"{token=}", f"{expired=}")
    return expired


def _is_valid(token) -> bool:
    # NOTE: We have experience (old) tokens that
    # were not deserialized as AccessToken dicts
    try:
        return token["count"] > 0 and not _is_expired(token)
    except (KeyError, TypeError):
        return False


@contextmanager
def _access_tokens_cleanup_ctx(session: Session) -> Iterator[dict[str, _AccessToken]]:
    # WARNING: make sure this does not wrapp any ``await handler(request)``
    # Note that these access_tokens correspond to the values BEFORE that call
    # and all the tokens added/removed in the decorators nested on the handler
    # are not updated on ``access_tokens`` returned.
    access_tokens = {}
    try:
        access_tokens = session.setdefault(_SESSION_GRANTED_ACCESS_TOKENS_KEY, {})

        yield access_tokens

    finally:
        # prunes
        pruned_access_tokens = {
            name: token for name, token in access_tokens.items() if _is_valid(token)
        }
        session[_SESSION_GRANTED_ACCESS_TOKENS_KEY] = pruned_access_tokens


@validate_call
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

            if response.status < _HTTP_400_BAD_REQUEST:
                settings: SessionSettings = get_plugin_settings(request.app)
                with _access_tokens_cleanup_ctx(session) as access_tokens:
                    # NOTE: does NOT add up access counts but re-assigns to max_access_count
                    access_tokens[name] = _AccessToken(
                        count=max_access_count,
                        expires=int(
                            time.time()
                            + settings.SESSION_ACCESS_TOKENS_EXPIRATION_INTERVAL_SECS
                        ),
                    )

            return response

        return _wrapper

    return _decorator


def session_access_required(
    name: str,
    *,
    unauthorized_reason: str | None = None,
    one_time_access: bool = True,
    remove_all_on_success: bool = False,
):
    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request):
            session = await get_session(request)

            with _access_tokens_cleanup_ctx(session) as access_tokens:
                access: _AccessToken | None = access_tokens.get(name, None)
                if not access:
                    raise web.HTTPUnauthorized(reason=unauthorized_reason)

                access["count"] -= 1  # consume access count
                if access["count"] < 0 or _is_expired(access):
                    raise web.HTTPUnauthorized(reason=unauthorized_reason)

                # update and keep for future accesses (e.g. retry this route)
                access_tokens[name] = access

            # Access granted to this handler
            response = await handler(request)

            if response.status < _HTTP_400_BAD_REQUEST:  # success
                with _access_tokens_cleanup_ctx(session) as access_tokens:
                    if one_time_access:
                        # avoids future accesses by clearing all tokens
                        access_tokens.pop(name, None)

                    if remove_all_on_success:
                        # all access tokens removed
                        access_tokens.clear()

            return response

        return _wrapper

    return _decorator

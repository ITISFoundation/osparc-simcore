import functools
import time
from typing import Optional, TypedDict

from aiohttp import web
from pydantic import PositiveInt, validate_arguments
from servicelib.aiohttp.typing_extension import Handler

from .session import get_session


# NOTE: dataclass cannot be serialized in the cookie
class RouteTrace(TypedDict):
    route_name: str
    timestamp: float


# session keys
SESSION_CONTRAINT_TRACE_KEY = "SESSION_ACCESS_TRACE.LAST_VISIT"
SESSION_CONTRAINT_COUNT_KEY = "SESSION_ACCESS_CONSTRAINT.COUNT.{name}"


def session_access_trace(route_name: str):
    def _decorator(handler: Handler):
        @functools.wraps(handler)
        async def _wrapper(request: web.Request):
            session = await get_session(request)

            response = await handler(request)

            # produce trace
            session[SESSION_CONTRAINT_TRACE_KEY] = RouteTrace(
                route_name=route_name, timestamp=time.time()
            )
            return response

        return _wrapper

    return _decorator


def session_access_constraint(
    allow_access_after: list[str],
    max_number_of_access: int = 1,
    unauthorized_reason: Optional[str] = None,
):
    """
    allow_access_after: grants access if any of the listed names was accessed before
    max_count: maximum number of requests after satifying the 'fronm_routes' condition
    """
    if not allow_access_after:
        raise ValueError("Expected at least 'from_routes' one constraint")
    if max_number_of_access is not None and max_number_of_access < 1:
        raise ValueError("max_count >=1")

    def _decorator(handler: Handler):
        # NOTE: session[SESSION_CALLS_COUNTS_KEY] counts the number of calls
        # on THIS handler on a GIVEN session
        SESSION_CALLS_COUNTS_KEY = SESSION_CONTRAINT_COUNT_KEY.format(
            name=handler.__name__
        )

        @functools.wraps(handler)
        async def _wrapper(request: web.Request):
            session = await get_session(request)

            # get & check trace
            previous_route_info: Optional[RouteTrace] = session.get(
                SESSION_CONTRAINT_TRACE_KEY
            )
            if (
                not previous_route_info
                or previous_route_info["route_name"] not in allow_access_after
            ):
                raise web.HTTPUnauthorized(reason=unauthorized_reason)

            # check call counts
            session.setdefault(SESSION_CALLS_COUNTS_KEY, max_number_of_access)

            # account for access
            session[SESSION_CALLS_COUNTS_KEY] -= 1
            if session[SESSION_CALLS_COUNTS_KEY] == 0:
                # consumes  trace to avoid subsequent accesses
                del session[SESSION_CONTRAINT_TRACE_KEY]
                del session[SESSION_CALLS_COUNTS_KEY]

            response = await handler(request)
            return response

        return _wrapper

    return _decorator


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

            response = await handler(request)

            # success 2XX ---
            session = await get_session(request)
            # TODO: what if raises non-error?
            routes_granted_acess = session.setdefault(
                SESSION_GRANTED_ACCESS_TOKENS_KEY, {}
            )
            # NOTE: does NOT add up access counts but resets to max_access_count
            routes_granted_acess[name] = max_access_count
            # ----

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

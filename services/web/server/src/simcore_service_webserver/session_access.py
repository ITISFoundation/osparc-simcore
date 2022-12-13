import functools
import time
from typing import Optional, TypedDict

from aiohttp import web
from servicelib.aiohttp.typing_extension import Handler

from .session import get_session


# NOTE: dataclass cannot be serialized in the cookie
class RouteTrace(TypedDict):
    route_name: str
    timestamp: int


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
    unauthorized_reason: str = None,
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

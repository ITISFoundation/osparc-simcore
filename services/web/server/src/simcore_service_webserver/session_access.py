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


SESSION_CONTRAINT_TRACE_KEY = "session_access_trace.last_visit"
SESSION_CONTRAINT_COUNT_KEY = "session_access_constraint.count"


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
        @functools.wraps(handler)
        async def _wrapper(request: web.Request):
            session = await get_session(request)

            # get & check trace
            trace: Optional[RouteTrace] = session.get(SESSION_CONTRAINT_TRACE_KEY)
            if not trace or trace["route_name"] not in allow_access_after:
                raise web.HTTPUnauthorized(reason=unauthorized_reason)

            # check hit counts
            session.setdefault(SESSION_CONTRAINT_COUNT_KEY, max_number_of_access)
            if session[SESSION_CONTRAINT_COUNT_KEY] <= 0:
                del session[SESSION_CONTRAINT_TRACE_KEY]
                del session[SESSION_CONTRAINT_COUNT_KEY]
                raise web.HTTPUnauthorized(reason=unauthorized_reason)

            session[SESSION_CONTRAINT_COUNT_KEY] -= 1

            response = await handler(request)
            return response

        return _wrapper

    return _decorator

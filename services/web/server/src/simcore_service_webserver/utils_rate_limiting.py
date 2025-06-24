from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from math import ceil
from typing import Final, NamedTuple

from aiohttp.web_exceptions import HTTPTooManyRequests
from common_library.user_messages import user_message
from models_library.rest_error import EnvelopedError, ErrorGet
from servicelib.aiohttp import status


class RateLimitSetup(NamedTuple):
    number_of_requests: int
    interval_seconds: float


MSG_TOO_MANY_REQUESTS: Final[str] = user_message(
    "Requests are being made too frequently. Please wait a moment before trying again."
)


def global_rate_limit_route(
    number_of_requests: int,
    interval_seconds: float,
    error_msg: str = MSG_TOO_MANY_REQUESTS,
):
    """
    Limits the requests per given interval to this endpoint
    from all incoming sources.
    Used to prevent abuse of unauthenticated endpoints.

    The limit rate is set as number_of_requests / interval_seconds

    number_of_requests: number of max requests per total interval
    interval_seconds: interval expressed in seconds
    """

    # compute the amount of requests per
    def _decorator(decorated_function: Callable):
        @dataclass
        class _Context:
            max_allowed: int  # maximum allowed requests per interval
            remaining: int  # remaining requests
            rate_limit_reset: float  # utc timestamp

        context = _Context(
            max_allowed=number_of_requests,
            remaining=number_of_requests,
            rate_limit_reset=0,
        )

        @wraps(decorated_function)
        async def _wrapper(*args, **kwargs):
            utc_now = datetime.now(UTC)
            utc_now_timestamp = datetime.timestamp(utc_now)

            # reset counter & first time initialization
            if utc_now_timestamp >= context.rate_limit_reset:
                context.rate_limit_reset = datetime.timestamp(
                    utc_now + timedelta(seconds=interval_seconds)
                )
                context.remaining = context.max_allowed

            if utc_now_timestamp <= context.rate_limit_reset and context.remaining <= 0:
                # SEE https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429
                retry_after_sec = int(
                    ceil(context.rate_limit_reset - utc_now_timestamp)
                )
                raise HTTPTooManyRequests(
                    headers={
                        "Content-Type": "application/json",
                        "Retry-After": f"{retry_after_sec}",
                    },
                    text=EnvelopedError(
                        error=ErrorGet(
                            message=error_msg,
                            status=status.HTTP_429_TOO_MANY_REQUESTS,
                        )
                    ).model_dump_json(),
                )

            assert (  # nosec
                HTTPTooManyRequests.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            )

            # increase counter and return original function call
            context.remaining -= 1
            return await decorated_function(*args, **kwargs)

        _wrapper.rate_limit_setup = RateLimitSetup(number_of_requests, interval_seconds)  # type: ignore
        return _wrapper

    return _decorator

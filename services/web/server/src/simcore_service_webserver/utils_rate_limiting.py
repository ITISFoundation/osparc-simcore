import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from math import ceil
from typing import NamedTuple

from aiohttp.web_exceptions import HTTPTooManyRequests


class RateLimitSetup(NamedTuple):
    number_of_requests: int
    interval_seconds: float


def global_rate_limit_route(number_of_requests: int, interval_seconds: float):
    """
    Limits the requests per given interval to this endpoint
    from all incoming sources.
    Used to prevent abuse of unauthenticated endpoints.

    The limit rate is set as number_of_requests / interval_seconds

    number_of_requests: number of max requests per total interval
    interval_seconds: interval expressed in seconds
    """

    # compute the amount of requests per
    def decorator(decorated_function):
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
        async def wrapper(*args, **kwargs):
            utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
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
                    text=json.dumps(
                        {
                            "error": {
                                "logs": [{"message": "API rate limit exceeded."}],
                                "status": HTTPTooManyRequests.status_code,
                            }
                        }
                    ),
                )

            # increase counter and return original function call
            context.remaining -= 1
            return await decorated_function(*args, **kwargs)

        wrapper.rate_limit_setup = RateLimitSetup(number_of_requests, interval_seconds)
        return wrapper

    return decorator

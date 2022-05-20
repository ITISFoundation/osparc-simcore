import json
from datetime import datetime, timedelta
from functools import wraps

import attr
from aiohttp.web_exceptions import HTTPTooManyRequests


def global_rate_limit_route(number_of_requests: int, interval_seconds: int):
    """
    Limits the requests per given interval to this endpoint
    from all incoming sources.
    Used to prevent abuse of unauthenticated endpoints.

    The limit rate is set as number_of_requests / interval_seconds

    number_of_requests: number of max requests per total interval
    interval_seconds: interval expressed in seconds
    """

    # compute the amount of requests per
    def decorating_function(decorated_function):
        @attr.s(auto_attribs=True)
        class Context:
            max_allowed: int  # maximum allowed requests per interval
            remaining: int  # remaining requests
            rate_limit_reset: int  # utc timestamp

        context = Context(
            max_allowed=number_of_requests,
            remaining=number_of_requests,
            rate_limit_reset=0,
        )

        @wraps(decorated_function)
        async def wrapper(*args, **kwargs):
            utc_now = datetime.utcnow()
            current_utc_timestamp = datetime.timestamp(utc_now)

            # reset counter & first time initialization
            if current_utc_timestamp >= context.rate_limit_reset:
                context.rate_limit_reset = datetime.timestamp(
                    utc_now + timedelta(seconds=interval_seconds)
                )
                context.remaining = context.max_allowed

            if (
                current_utc_timestamp <= context.rate_limit_reset
                and context.remaining <= 0
            ):
                # show error and return from here
                raise HTTPTooManyRequests(
                    headers={
                        "Content-Type": "application/json",
                        "Retry-After": str(int(context.rate_limit_reset)),
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

        wrapper.rate_limit_setup = (number_of_requests, interval_seconds)
        return wrapper

    return decorating_function

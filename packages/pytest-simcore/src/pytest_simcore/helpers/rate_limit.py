import asyncio
import logging
import math
import time
from collections.abc import Awaitable
from functools import wraps

from aiohttp import ClientResponse, ClientSession, ClientTimeout

log = logging.getLogger()


def function_duration(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        end = time.time()
        elapsed = end - start
        log.info("Function '%s' execution took '%0.2f' seconds", func.__name__, elapsed)
        return result

    return wrapper


def is_rate_limit_reached(result: ClientResponse) -> bool:
    return "Retry-After" in result.headers


async def get_request_result(
    client: ClientSession, endpoint_to_check: str
) -> ClientResponse:
    result = await client.get(endpoint_to_check)
    log.debug("%s\n%s\n%s", result, await result.text(), dict(result.headers))
    return result


async def assert_burst_request(
    client: ClientSession,
    endpoint_to_check: str,
    burst: int,
):
    functions = [get_request_result(client, endpoint_to_check) for x in range(burst)]
    results = await asyncio.gather(*functions)
    for result in results:
        assert is_rate_limit_reached(result) is False


@function_duration
async def assert_burst_rate_limit(
    endpoint_to_check: str, average: int, period_sec: int, burst: int
) -> float:
    """
    Runs 2 burst sequences with a pause in between and expects for the
    next result to fail.
    """

    max_rate = period_sec / average
    # sleeping 2 times the burst window
    burst_window = period_sec / burst
    sleep_internval = 2 * burst_window

    log.info(
        "Sleeping params: burst_window=%s, sleep_interval=%s, max_rate=%s",
        burst_window,
        sleep_internval,
        max_rate,
    )

    timeout = ClientTimeout(total=10, connect=1, sock_connect=1)
    async with ClientSession(timeout=timeout) as client:

        # check can burst in timeframe
        await assert_burst_request(
            client=client, endpoint_to_check=endpoint_to_check, burst=burst
        )

        log.info("First burst finished")

        await asyncio.sleep(sleep_internval)

        # check that burst in timeframe is ok
        await assert_burst_request(
            client=client, endpoint_to_check=endpoint_to_check, burst=burst
        )

        log.info("Second burst finished")

        # check that another request after the burst fails
        result = await get_request_result(client, endpoint_to_check)
        assert is_rate_limit_reached(result) is True

    return sleep_internval


@function_duration
async def assert_steady_rate_in_5_seconds(
    endpoint_to_check: str, average: int, period_sec: int, **_
) -> float:
    """Creates a requests at a continuous rate without considering burst limits"""
    # run tests for at least 5 seconds
    max_rate = period_sec / average  # reqs/ sec
    requests_to_make = int(math.ceil(max_rate * 5))

    sleep_interval = max_rate

    log.info(
        "Steady rate params: sleep_interval=%s, max_rate=%s, requests_to_make=%s",
        sleep_interval,
        max_rate,
        requests_to_make,
    )

    timeout = ClientTimeout(total=10, connect=1, sock_connect=1)
    async with ClientSession(timeout=timeout) as client:

        for i in range(requests_to_make):
            log.info("Request %s", i)
            result = await get_request_result(client, endpoint_to_check)
            assert is_rate_limit_reached(result) is False
            log.info("Sleeping for %s s", sleep_interval)
            await asyncio.sleep(sleep_interval)

    return sleep_interval


CHECKS_TO_RUN: list[Awaitable] = [
    assert_steady_rate_in_5_seconds,
    assert_burst_rate_limit,
]


@function_duration
async def run_rate_limit_configuration_checks(
    endpoint_to_check: str, average: int = 0, period_sec: int = 1, burst: int = 1
):
    """
    Runner to start all the checks for the firewall configuration

    All tests mut return the period to sleep before the next test can start.

    All defaults are taken from Traefik's docs
    SEE https://doc.traefik.io/traefik/middlewares/ratelimit/
    """

    log.warning(
        "Runtime will vary based on the rate limit configuration of the service\n"
    )

    for awaitable in CHECKS_TO_RUN:
        log.info("<<<< Starting test '%s'...", awaitable.__name__)
        sleep_before_next_test = await awaitable(
            endpoint_to_check=endpoint_to_check,
            average=average,
            period_sec=period_sec,
            burst=burst,
        )
        log.info(">>>> Finished testing '%s'\n", awaitable.__name__)

        log.info(">>>> Sleeping '%s' seconds before next test", sleep_before_next_test)
        await asyncio.sleep(sleep_before_next_test)

    log.info("All tests completed")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(threadName)s [%(name)s] %(message)s",
    )

    # How to use, the below parameters are derived from the following labels:
    # - traefik.http.middlewares.ratelimit-${SWARM_STACK_NAME}_api-server.ratelimit.average=1
    # - traefik.http.middlewares.ratelimit-${SWARM_STACK_NAME}_api-server.ratelimit.period=1m
    # - traefik.http.middlewares.ratelimit-${SWARM_STACK_NAME}_api-server.ratelimit.burst=10
    # Will result in: average=1, period_sec=60, burst=10
    # WARNING: in the above example the test will run for 5 hours :\

    asyncio.get_event_loop().run_until_complete(
        run_rate_limit_configuration_checks(
            endpoint_to_check="http://localhost:10081/",
            average=1,
            period_sec=60,
            burst=10,
        )
    )

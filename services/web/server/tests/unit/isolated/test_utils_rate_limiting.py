# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import time

import pytest
from aiohttp import web
from aiohttp.web_exceptions import HTTPTooManyRequests
from simcore_service_webserver.utils_rate_limiting import global_rate_limit_route

MAX_NUM_REQUESTS = 3
MEASURE_INTERVAL = 0.5
MAX_REQUEST_RATE = MAX_NUM_REQUESTS / MEASURE_INTERVAL


@global_rate_limit_route(
    number_of_requests=MAX_NUM_REQUESTS, interval_seconds=MEASURE_INTERVAL
)
async def get_ok_handler(_request: web.Request):
    return web.json_response({"value": 1})


@pytest.mark.parametrize(
    "requests_per_second",
    [0.5 * MAX_REQUEST_RATE, MAX_REQUEST_RATE, 2 * MAX_REQUEST_RATE],
)
async def test_global_rate_limit_route(requests_per_second, aiohttp_client):
    #
    app = web.Application()
    app.router.add_get("/", get_ok_handler)

    client = await aiohttp_client(app)
    # ---

    # decorated function keeps setup
    assert get_ok_handler.rate_limit_setup == (MAX_NUM_REQUESTS, MEASURE_INTERVAL)

    # Creates desired stream of requests for 1 second
    TOTAL_TEST_TIME = 1  # secs
    num_requests = int(requests_per_second * TOTAL_TEST_TIME)
    time_between_requests = 1.0 / requests_per_second

    futures = []
    t0 = time.time()
    while len(futures) < num_requests:
        t1 = time.time()
        futures.append(asyncio.ensure_future(client.get("/")))
        time.sleep(time_between_requests - (time.time() - t1))

    elapsed = time.time() - t0
    count = len(futures)
    print(
        count,
        "requests in",
        f"{elapsed:3.2f} seconds =>",
        f"{count / elapsed:3.2f}",
        "reqs/sec",
    )

    # checks if cadence was right
    assert count == num_requests
    assert elapsed == pytest.approx(TOTAL_TEST_TIME, abs=0.1)

    for i, fut in enumerate(futures):
        while not fut.done():
            await asyncio.sleep(0.1)
        assert not fut.cancelled()
        assert not fut.exception()
        print("%2d" % i, fut.result().status)

    expected_status = 200

    # first requests are OK
    assert all(f.result().status == expected_status for f in futures[:MAX_NUM_REQUESTS])

    if requests_per_second >= MAX_REQUEST_RATE:
        expected_status = HTTPTooManyRequests.status_code

    # after ...
    assert all(f.result().status == expected_status for f in futures[MAX_NUM_REQUESTS:])

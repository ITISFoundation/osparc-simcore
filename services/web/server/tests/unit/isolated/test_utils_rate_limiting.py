# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import time
from typing import Callable

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp.web_exceptions import HTTPOk, HTTPTooManyRequests
from pydantic import Field, TypeAdapter, ValidationError
from simcore_service_webserver.utils_rate_limiting import global_rate_limit_route
from typing_extensions import Annotated

TOTAL_TEST_TIME = 1  # secs
MAX_NUM_REQUESTS = 3
MEASURE_INTERVAL = 0.5
MAX_REQUEST_RATE = MAX_NUM_REQUESTS / MEASURE_INTERVAL


@global_rate_limit_route(
    number_of_requests=MAX_NUM_REQUESTS, interval_seconds=MEASURE_INTERVAL
)
async def get_ok_handler(_request: web.Request):
    return web.json_response({"value": 1})


@pytest.fixture
def client(event_loop, aiohttp_client: Callable) -> TestClient:
    app = web.Application()
    app.router.add_get("/", get_ok_handler)

    return event_loop.run_until_complete(aiohttp_client(app))


def test_rate_limit_route_decorator():
    # decorated function keeps setup
    assert get_ok_handler.rate_limit_setup == (MAX_NUM_REQUESTS, MEASURE_INTERVAL)


@pytest.mark.parametrize(
    "requests_per_second",
    [0.5 * MAX_REQUEST_RATE, MAX_REQUEST_RATE, 2 * MAX_REQUEST_RATE],
)
async def test_global_rate_limit_route(requests_per_second: float, client: TestClient):
    # WARNING: this test has some timings and might fail when using breakpoints

    # Creates desired stream of requests for 1 second
    num_requests = int(requests_per_second * TOTAL_TEST_TIME)
    time_between_requests = 1.0 / requests_per_second

    tasks = []
    t0 = time.time()
    while len(tasks) < num_requests:
        t1 = time.time()
        tasks.append(asyncio.create_task(client.get("/")))
        elapsed_on_creation = time.time() - t1  # ANE is really precise here ;-)

        # NOTE: I am not sure why using asyncio.sleep here would make some tests fail the check "after"
        # await asyncio.sleep(time_between_requests - create_gap)
        time.sleep(time_between_requests - elapsed_on_creation)

    elapsed = time.time() - t0
    count = len(tasks)
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

    msg = []
    for i, task in enumerate(tasks):
        while not task.done():
            await asyncio.sleep(0.01)
        assert not task.cancelled()
        assert not task.exception()
        msg.append(
            (
                "request # %2d" % i,
                f"status={task.result().status}",
                f"retry-after={task.result().headers.get('Retry-After')}",
            )
        )
        print(*msg[-1])

    expected_status = HTTPOk.status_code

    # first requests are OK
    assert all(
        t.result().status == expected_status for t in tasks[:MAX_NUM_REQUESTS]
    ), f" Failed with { msg[:MAX_NUM_REQUESTS]}"

    if requests_per_second >= MAX_REQUEST_RATE:
        expected_status = HTTPTooManyRequests.status_code

    # after ...
    assert all(
        t.result().status == expected_status for t in tasks[MAX_NUM_REQUESTS:]
    ), f" Failed with { msg[MAX_NUM_REQUESTS:]}"

    # checks Retry-After header
    failed = []
    for t in tasks:
        if retry_after := t.result().headers.get("Retry-After"):
            try:
                TypeAdapter(Annotated[int, Field(ge=1)]).validate_python(retry_after)
            except ValidationError as err:
                failed.append((retry_after, f"{err}"))
    assert not failed

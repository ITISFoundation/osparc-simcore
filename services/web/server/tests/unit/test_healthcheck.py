# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import asyncio
import logging
import time
from typing import Coroutine

import pytest
from aiohttp import web
from tenacity import Retrying, before_log, stop_after_attempt, wait_fixed

from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.application import setup_app_monitoring
from simcore_service_webserver.diagnostics_plugin import (
    K_MAX_AVG_RESP_DELAY,
    K_MAX_CANCEL_RATE,
    UnhealthyAppError,
    assert_health_app,
    setup_diagnostics,
)
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security

logger = logging.getLogger(__name__)


async def health_checker(
    client,
    api_version_prefix,
    *,
    start_period: int = 0,
    timeout: int = 30,
    interval: int = 30,
    retries: int = 3,
):
    # Emulates https://docs.docker.com/engine/reference/builder/#healthcheck
    checkpoint: Coroutine = client.get(f"/{api_version_prefix}/")

    time.sleep(start_period)

    while True:
        for attempt in Retrying(
            wait=wait_fixed(interval),
            stop=stop_after_attempt(retries),
            before=before_log(logger, logging.WARNING),
        ):
            with attempt:
                resp = await asyncio.wait_for(checkpoint, timeout=timeout)
                assert resp.status == web.HTTPOk.status_code

        time.sleep(interval)


@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, api_version_prefix):
    SLOW_HANDLER_DELAY_SECS = 1.0  # secs

    # pylint:disable=unused-variable
    routes = web.RouteTableDef()

    @routes.get("/error")
    async def unexpected_error(request: web.Request):
        raise Exception("boom shall produce 500")

    @routes.get("/fail")
    async def expected_failure(request: web.Request):
        raise web.HTTPServiceUnavailable()

    @routes.get("/slow")
    async def blocking_slow(request: web.Request):
        time.sleep(SLOW_HANDLER_DELAY_SECS * 1.1)
        return web.json_response({"data": True, "error": None})

    @routes.get("/cancelled")
    async def cancelled_task(request: web.Request):
        task: asyncio.Task = request.app.loop.create_task(
            asyncio.sleep(SLOW_HANDLER_DELAY_SECS * 3)
        )
        task.cancel()  # raise CancelledError

    @routes.get(r"/delay/{secs:\d+}")
    async def delay_response(request: web.Request):
        secs = int(request.match_info.get("secs", 0))
        await asyncio.sleep(secs)  # non-blocking slow
        return web.json_response({"data": True, "error": None})

    # -----

    app = create_safe_application()

    main = {
        "port": aiohttp_unused_port(),
        "host": "localhost",
        "monitoring_enabled": True,
    }
    app[APP_CONFIG_KEY] = {
        "main": main,
        "rest": {"enabled": True, "version": api_version_prefix},
    }

    # activates some sub-modules
    setup_security(app)
    setup_rest(app)
    setup_app_monitoring(app)
    setup_diagnostics(
        app,
        slow_duration_secs=SLOW_HANDLER_DELAY_SECS / 10,
        max_delay_allowed=SLOW_HANDLER_DELAY_SECS,
        max_cancelations_rate=3,  # cancelations/s during N repetitions
        max_avg_response_delay_secs=1,
    )

    app.router.add_routes(routes)

    cli = loop.run_until_complete(
        aiohttp_client(app, server_kwargs={key: main[key] for key in ("host", "port")})
    )
    return cli


async def test_healthy_app(client, api_version_prefix):
    resp = await client.get(f"/{api_version_prefix}/")

    data, error = await assert_status(resp, web.HTTPOk)

    assert data
    assert not error

    assert data["name"] == "simcore_service_webserver"
    assert data["status"] == "SERVICE_RUNNING"


async def test_unhealthy_app_with_slow_callbacks(client, api_version_prefix):
    resp = await client.get(f"/{api_version_prefix}/")
    await assert_status(resp, web.HTTPOk)

    resp = await client.get("/slow")  # emulates a very slow handle!
    await assert_status(resp, web.HTTPOk)

    resp = await client.get(f"/{api_version_prefix}/")
    await assert_status(resp, web.HTTPServiceUnavailable)


async def test_diagnose_on_unexpected_error(client):
    resp = await client.get("/error")
    assert resp.status == web.HTTPInternalServerError.status_code

    assert_health_app(client.app)


async def test_diagnose_on_failure(client):
    resp = await client.get("/fail")
    assert resp.status == web.HTTPServiceUnavailable.status_code

    assert_health_app(client.app)


async def test_diagnose_on_cancellations(client):
    count = client.app[K_MAX_CANCEL_RATE]  # cancelations per second

    for _ in range(count):
        resp = await client.get("/cancelled")
        assert resp.status == web.HTTPInternalServerError.status_code

    with pytest.raises(UnhealthyAppError):
        assert_health_app(client.app)


async def test_diagnose_on_response_delays(client):
    secs = 1.2 * client.app[K_MAX_AVG_RESP_DELAY]

    resp = await client.get(f"/delay/{secs}")
    assert_status(resp, web.HTTPOk)

    with pytest.raises(UnhealthyAppError):
        assert_health_app(client.app)


def test_read_prometheus_counter():
    # TODO move to test_prometheus_utils.py in servicelib
    from prometheus_client import Counter

    counter = Counter(
        "my_fullname_counter", "description", labelnames=("name", "surname")
    )

    def get_total():
        total_count = 0
        for metric in counter.collect():
            import pdb

            pdb.set_trace()
            for sample in metric.samples:
                if sample.name.endswith("_total"):
                    total_count += sample.value
        return total_count

    counter.labels("pedro", "crespo").inc()
    counter.labels("juan", "crespo").inc()
    counter.labels("pedro", "valero").inc()

    assert get_total() == 3

    counter.labels("pedro", "crespo").inc()
    counter.labels("pedro", "crespo").inc()

    assert get_total() == 5

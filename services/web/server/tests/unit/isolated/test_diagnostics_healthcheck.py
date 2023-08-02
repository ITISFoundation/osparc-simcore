# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=unused-variable

import asyncio
import logging
import time
from typing import Coroutine

import pytest
import simcore_service_webserver
from aiohttp import web
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver._constants import APP_SETTINGS_KEY
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.diagnostics._healthcheck import (
    HEALTH_LATENCY_PROBE,
    HealthCheckFailed,
    assert_healthy_app,
)
from simcore_service_webserver.diagnostics.plugin import setup_diagnostics
from simcore_service_webserver.diagnostics.settings import DiagnosticsSettings
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from tenacity import before_log, retry, stop_after_attempt, wait_fixed
from yarl import URL

logger = logging.getLogger(__name__)


def health_check_path(api_version_prefix) -> URL:
    return URL(f"/{api_version_prefix}/health")


async def health_check_emulator(
    client,
    health_check_path,
    *,
    min_num_checks=2,
    start_period: int = 0,
    timeout: int = 30,
    interval: int = 30,
    retries: int = 3,
):
    # Follows docker's health check protocol
    # SEE https://docs.docker.com/engine/reference/builder/#healthcheck
    checkpoint: Coroutine = client.get(health_check_path)

    check_count = 0

    @retry(
        wait=wait_fixed(interval),
        stop=stop_after_attempt(retries),
        before=before_log(logger, logging.WARNING),
    )
    async def _check_entrypoint():
        nonlocal check_count
        check_count += 1
        resp = await asyncio.wait_for(checkpoint, timeout=timeout)
        assert resp.status == web.HTTPOk.status_code

    await asyncio.sleep(start_period)

    while check_count < min_num_checks:
        await _check_entrypoint()
        await asyncio.sleep(interval)


SLOW_HANDLER_DELAY_SECS = 2.0  # secs


@pytest.fixture
def mock_environment(mock_env_devel_environment: dict[str, str], monkeypatch):
    monkeypatch.setenv("AIODEBUG_SLOW_DURATION_SECS", f"{SLOW_HANDLER_DELAY_SECS / 10}")
    monkeypatch.setenv("DIAGNOSTICS_MAX_TASK_DELAY", f"{SLOW_HANDLER_DELAY_SECS}")
    monkeypatch.setenv("DIAGNOSTICS_MAX_AVG_LATENCY", f"{2.0}")
    monkeypatch.setenv("DIAGNOSTICS_START_SENSING_DELAY", f"{0}")
    monkeypatch.setenv("SC_HEALTHCHECK_TIMEOUT", "2m")


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    unused_tcp_port_factory,
    aiohttp_client,
    api_version_prefix,
    mock_environment: None,
):
    routes = web.RouteTableDef()

    @routes.get("/error")
    async def unexpected_error(request: web.Request):
        raise Exception(  # pylint: disable=broad-exception-raised
            "boom shall produce 500"
        )

    @routes.get(r"/fail")
    async def expected_failure(request: web.Request):
        raise web.HTTPServiceUnavailable()

    @routes.get(r"/slow")
    async def blocking_slow(request: web.Request):
        time.sleep(SLOW_HANDLER_DELAY_SECS * 1.1)
        return web.json_response({"data": True, "error": None})

    @routes.get(r"/cancel")
    async def cancelled_task(request: web.Request):
        task: asyncio.Task = request.app.loop.create_task(asyncio.sleep(10))
        task.cancel()  # raise CancelledError

    @routes.get(r"/timeout/{secs}")
    async def time_out(request: web.Request):
        secs = float(request.match_info.get("secs", 0))
        await asyncio.wait_for(
            asyncio.sleep(10 * secs), timeout=secs
        )  # raises TimeOutError

    @routes.get(r"/delay/{secs}")
    async def delay_response(request: web.Request):
        secs = float(request.match_info.get("secs", 0))
        await asyncio.sleep(secs)  # non-blocking slow
        return web.json_response({"data": True, "error": None})

    # -----
    main = {"port": unused_tcp_port_factory(), "host": "localhost"}
    cfg = {
        "main": main,
        "rest": {"enabled": True, "version": api_version_prefix},
        "diagnostics": {"enabled": True},
    }

    app = create_safe_application(cfg)

    # activates some sub-modules
    assert setup_settings(app)
    setup_security(app)
    setup_rest(app)

    setup_diagnostics(app)

    settings: DiagnosticsSettings = app[APP_SETTINGS_KEY].WEBSERVER_DIAGNOSTICS
    assert settings.DIAGNOSTICS_MAX_AVG_LATENCY == 2.0

    app.router.add_routes(routes)

    cli = event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs={key: main[key] for key in ("host", "port")})
    )
    return cli


def test_diagnostics_setup(client):
    app = client.app

    assert len(app.middlewares) == 3
    assert "monitor" in app.middlewares[0].__middleware_name__
    assert "error" in app.middlewares[1].__middleware_name__
    assert "envelope" in app.middlewares[2].__middleware_name__


async def test_healthy_app(client, api_version_prefix):
    resp = await client.get(f"/{api_version_prefix}/health")

    data, error = await assert_status(resp, web.HTTPOk)

    assert data
    assert not error

    assert data["name"] == "simcore_service_webserver"
    assert data["version"] == simcore_service_webserver._meta.__version__


async def test_unhealthy_app_with_slow_callbacks(client, api_version_prefix):
    resp = await client.get(f"/{api_version_prefix}/health")
    await assert_status(resp, web.HTTPOk)

    resp = await client.get("/slow")  # emulates a very slow handle!
    await assert_status(resp, web.HTTPOk)

    resp = await client.get(f"/{api_version_prefix}/health")
    await assert_status(resp, web.HTTPServiceUnavailable)


async def test_diagnose_on_unexpected_error(client):
    resp = await client.get("/error")
    assert resp.status == web.HTTPInternalServerError.status_code

    assert_healthy_app(client.app)


async def test_diagnose_on_failure(client):
    resp = await client.get("/fail")
    assert resp.status == web.HTTPServiceUnavailable.status_code

    assert_healthy_app(client.app)


async def test_diagnose_on_response_delays(client):
    settings: DiagnosticsSettings = client.app[APP_SETTINGS_KEY].WEBSERVER_DIAGNOSTICS

    tmax = settings.DIAGNOSTICS_MAX_AVG_LATENCY
    coros = [client.get(f"/delay/{1.1*tmax}") for _ in range(10)]
    resps = await asyncio.gather(*coros)

    for resp in resps:
        await assert_status(resp, web.HTTPOk)

    # monitoring
    latency_observed = client.app[HEALTH_LATENCY_PROBE].value()
    assert latency_observed > tmax

    # diagnostics
    with pytest.raises(HealthCheckFailed):
        assert_healthy_app(client.app)


def test_read_prometheus_counter():
    # TODO move to test_prometheus_utils.py in servicelib
    from prometheus_client import Counter

    counter = Counter(
        "my_fullname_counter", "description", labelnames=("name", "surname")
    )

    def get_total():
        total_count = 0
        for metric in counter.collect():
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

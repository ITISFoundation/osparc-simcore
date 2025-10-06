# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=unused-variable

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Coroutine

import pytest
import simcore_service_webserver
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_mock import MockType
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.application_keys import APP_SETTINGS_APPKEY
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.diagnostics._healthcheck import (
    HEALTH_LATENCY_PROBE_APPKEY,
    HealthCheckError,
    assert_healthy_app,
)
from simcore_service_webserver.diagnostics.plugin import setup_diagnostics
from simcore_service_webserver.diagnostics.settings import DiagnosticsSettings
from simcore_service_webserver.rest.plugin import setup_rest
from tenacity import retry
from tenacity.before import before_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from yarl import URL

logger = logging.getLogger(__name__)


def _health_check_path(api_version_prefix: str) -> URL:
    return URL(f"/{api_version_prefix}/health")


async def _health_check_emulator(
    client: TestClient,
    health_check_path: URL,
    *,
    min_num_checks: int = 2,
    start_period: int = 0,
    timeout: int = 30,
    interval: int = 30,
    retries: int = 3,
):
    # Follows docker's health check protocol
    # SEE https://docs.docker.com/engine/reference/builder/#healthcheck
    checkpoint: Coroutine = client.get(health_check_path.path)

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
        assert resp.status == status.HTTP_200_OK

    await asyncio.sleep(start_period)

    while check_count < min_num_checks:
        await _check_entrypoint()
        await asyncio.sleep(interval)


SLOW_HANDLER_DELAY_SECS = 2.0  # secs


@pytest.fixture
def mock_environment(
    mock_env_devel_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **mock_env_devel_environment,
            "AIODEBUG_SLOW_DURATION_SECS": f"{SLOW_HANDLER_DELAY_SECS / 10}",
            "WEBSERVER_DIAGNOSTICS": json.dumps(
                {
                    "DIAGNOSTICS_MAX_AVG_LATENCY": "2.0",
                    "DIAGNOSTICS_MAX_TASK_DELAY": f"{SLOW_HANDLER_DELAY_SECS}",
                    "DIAGNOSTICS_START_SENSING_DELAY": f"{0}",
                    "DIAGNOSTICS_HEALTHCHECK_ENABLED": "1",
                }
            ),
            "SC_HEALTHCHECK_TIMEOUT": "2m",
            "WEBSERVER_RPC_NAMESPACE": "null",
        },
    )


@pytest.fixture
async def client(
    mocked_db_setup_in_setup_security: MockType,
    unused_tcp_port_factory: Callable,
    aiohttp_client: Callable[..., Awaitable[TestClient]],
    api_version_prefix: str,
    mock_environment: EnvVarsDict,
) -> TestClient:
    routes = web.RouteTableDef()

    @routes.get("/error")
    async def unexpected_error(request: web.Request):
        msg = "boom shall produce 500"
        raise Exception(msg)  # pylint: disable=broad-exception-raised

    @routes.get(r"/fail")
    async def expected_failure(request: web.Request):
        raise web.HTTPServiceUnavailable

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
    setup_rest(app)

    setup_diagnostics(app)

    settings: DiagnosticsSettings = app[APP_SETTINGS_APPKEY].WEBSERVER_DIAGNOSTICS
    assert settings.DIAGNOSTICS_MAX_AVG_LATENCY == 2.0

    app.router.add_routes(routes)

    return await aiohttp_client(
        app, server_kwargs={key: main[key] for key in ("host", "port")}
    )


def test_diagnostics_setup(client: TestClient):
    assert client.app
    assert {m.__middleware_name__ for m in client.app.middlewares} == {
        "servicelib.aiohttp.monitoring.monitor_simcore_service_webserver",
        "servicelib.aiohttp.rest_middlewares.envelope_v0",
        "servicelib.aiohttp.rest_middlewares.error_v0",
        "simcore_service_webserver.session.plugin.session",
    }


async def test_healthy_app(client: TestClient, api_version_prefix: str):
    resp = await client.get(f"/{api_version_prefix}/health")

    data, error = await assert_status(resp, status.HTTP_200_OK)

    assert data
    assert not error

    assert data["name"] == simcore_service_webserver._meta.APP_NAME
    assert data["version"] == simcore_service_webserver._meta.__version__


async def test_unhealthy_app_with_slow_callbacks(
    client: TestClient, api_version_prefix: str
):
    resp = await client.get(f"/{api_version_prefix}/health")
    await assert_status(resp, status.HTTP_200_OK)

    resp = await client.get("/slow")  # emulates a very slow handle!
    await assert_status(resp, status.HTTP_200_OK)

    resp = await client.get(f"/{api_version_prefix}/health")
    await assert_status(resp, status.HTTP_503_SERVICE_UNAVAILABLE)


async def test_diagnose_on_unexpected_error(client: TestClient):
    assert client.app
    resp = await client.get("/error")
    assert resp.status == status.HTTP_500_INTERNAL_SERVER_ERROR

    assert_healthy_app(client.app)


async def test_diagnose_on_failure(client: TestClient):
    assert client.app
    resp = await client.get("/fail")
    assert resp.status == status.HTTP_503_SERVICE_UNAVAILABLE

    assert_healthy_app(client.app)


async def test_diagnose_on_response_delays(client: TestClient):
    assert client.app
    settings: DiagnosticsSettings = client.app[
        APP_SETTINGS_APPKEY
    ].WEBSERVER_DIAGNOSTICS

    tmax = settings.DIAGNOSTICS_MAX_AVG_LATENCY
    coros = [client.get(f"/delay/{1.1 * tmax}") for _ in range(10)]
    resps = await asyncio.gather(*coros)

    for resp in resps:
        await assert_status(resp, status.HTTP_200_OK)

    # monitoring
    latency_observed = client.app[HEALTH_LATENCY_PROBE_APPKEY].value()
    assert latency_observed > tmax

    # diagnostics
    with pytest.raises(HealthCheckError):
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

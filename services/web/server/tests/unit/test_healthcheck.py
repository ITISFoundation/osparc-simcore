# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-name-in-module

import pytest
from aiohttp import web
import time

from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.application import create_safe_application
from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.diagnostics import setup_diagnostics


from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security


@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, api_version_prefix):
    SLOW_HANDLER_DELAY_SECS = 1.0  # secs

    async def slow_handler(request: web.Request):
        time.sleep(SLOW_HANDLER_DELAY_SECS * 1.1)
        return web.json_response({"data": 1, "error": None})

    app = create_safe_application()

    server_kwargs = {"port": aiohttp_unused_port(), "host": "localhost"}
    # fake config
    app[APP_CONFIG_KEY] = {
        "main": server_kwargs,
        "rest": {"enabled": True, "version": api_version_prefix},
    }
    # activates only security+restAPI sub-modules
    setup_security(app)
    setup_rest(app)
    setup_diagnostics(app, max_delay_allowed=SLOW_HANDLER_DELAY_SECS)

    app.router.add_get("/slow", slow_handler)

    cli = loop.run_until_complete(aiohttp_client(app, server_kwargs=server_kwargs))
    return cli


async def test_check_health_entrypoint(client, api_version_prefix):
    resp = await client.get(f"/{api_version_prefix}/")
    payload = await resp.json()

    assert resp.status == 200, str(payload)
    data, error = tuple(payload.get(k) for k in ("data", "error"))

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

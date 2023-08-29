# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionError
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.activity.plugin import setup_activity
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session


@pytest.fixture
def mocked_login_required(mocker: MockerFixture):
    return mocker.patch(
        "aiohttp_security.api.authorized_userid",
        autospec=True,
        return_value=1,  # user_id
    )


@pytest.fixture
def mocked_monitoring(mocker: MockerFixture, activity_data: dict[str, Any]) -> None:
    prometheus_data: dict[str, Any] = activity_data["prometheus"]

    cpu_ret = prometheus_data.get("cpu_return")
    mocker.patch(
        "simcore_service_webserver.activity._handlers.get_cpu_usage",
        return_value=cpu_ret,
    )

    mem_ret = prometheus_data.get("memory_return")
    mocker.patch(
        "simcore_service_webserver.activity._handlers.get_memory_usage",
        return_value=mem_ret,
    )

    labels_ret = prometheus_data.get("labels_return")
    mocker.patch(
        "simcore_service_webserver.activity._handlers.get_container_metric_for_labels",
        return_value=labels_ret,
    )


@pytest.fixture
def mocked_monitoring_down(mocker):
    mocker.patch(
        "simcore_service_webserver.activity._api.query_prometheus",
        side_effect=ClientConnectionError,
    )
    return mocker


@pytest.fixture
def app_config(fake_data_dir: Path, osparc_simcore_root_dir: Path) -> dict[str, Any]:
    with Path.open(fake_data_dir / "test_activity_config.yml") as fh:
        content = fh.read()
        config = content.replace(
            "${OSPARC_SIMCORE_REPO_ROOTDIR}", str(osparc_simcore_root_dir)
        )

    return yaml.safe_load(config)


@pytest.fixture
def client(
    event_loop,
    aiohttp_client: Callable,
    app_config: dict[str, Any],
    mock_orphaned_services,
    monkeypatch_setenv_from_app_config: Callable,
):
    monkeypatch_setenv_from_app_config(app_config)

    app = create_safe_application(app_config)

    assert setup_settings(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    assert setup_activity(app)

    return event_loop.run_until_complete(aiohttp_client(app))


async def test_has_login_required(client: TestClient):
    resp = await client.get("/v0/activity/status")
    await assert_status(resp, web.HTTPUnauthorized)


async def test_monitoring_up(mocked_login_required, mocked_monitoring, client):
    RUNNING_NODE_ID = "894dd8d5-de3b-4767-950c-7c3ed8f51d8c"

    resp = await client.get("/v0/activity/status")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert RUNNING_NODE_ID in data, "Running node not present"

    prometheus = data.get(RUNNING_NODE_ID, {})

    assert "limits" in prometheus, "There is no limits key for executing node"
    assert "stats" in prometheus, "There is no stats key for executed node"

    limits = prometheus.get("limits", {})
    assert limits.get("cpus") == 4.0, "Incorrect value: Cpu limit"
    assert limits.get("mem") == 2048.0, "Incorrect value: Memory limit"

    stats = prometheus.get("stats", {})
    assert stats.get("cpuUsage") == 3.9952102200000006, "Incorrect value: Cpu usage"
    assert stats.get("memUsage") == 177.664, "Incorrect value: Memory usage"


async def test_monitoring_down(mocked_login_required, mocked_monitoring_down, client):
    resp = await client.get("/v0/activity/status")
    await assert_status(resp, web.HTTPNoContent)

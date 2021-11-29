# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import importlib
from pathlib import Path

import pytest
import yaml
from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionError
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.activity import handlers
from simcore_service_webserver.activity.module_setup import setup_activity
from simcore_service_webserver.computation_config import ComputationSettings
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.session import setup_session


@pytest.fixture
def mocked_celery_client(mocker):
    mocker.patch(
        "simcore_service_webserver.activity.celery_client._get_computation_settings",
        return_value=ComputationSettings.create_from_env(),
    )


@pytest.fixture
def mocked_login_required(mocker):
    mock = mocker.patch(
        "simcore_service_webserver.login.decorators.login_required", lambda h: h
    )
    importlib.reload(handlers)
    return mock


@pytest.fixture
def mocked_monitoring(loop, mocker, activity_data):
    prometheus_data = activity_data.get("prometheus")
    cpu_ret = prometheus_data.get("cpu_return")
    mocker.patch(
        "simcore_service_webserver.activity.handlers.get_cpu_usage",
        return_value=cpu_ret,
    )

    mem_ret = prometheus_data.get("memory_return")
    mocker.patch(
        "simcore_service_webserver.activity.handlers.get_memory_usage",
        return_value=mem_ret,
    )

    labels_ret = prometheus_data.get("labels_return")
    mocker.patch(
        "simcore_service_webserver.activity.handlers.get_container_metric_for_labels",
        return_value=labels_ret,
    )

    celery_data = activity_data.get("celery")
    celery_ret = celery_data.get("celery_return")
    mocker.patch(
        "simcore_service_webserver.activity.handlers.get_celery_reserved",
        return_value=celery_ret,
    )


@pytest.fixture
def mocked_monitoring_down(mocker):
    mocker.patch(
        "simcore_service_webserver.activity.handlers.query_prometheus",
        side_effect=ClientConnectionError,
    )
    mocker.patch(
        "simcore_service_webserver.activity.handlers.celery_reserved",
        side_effect=ClientConnectionError,
    )
    return mocker


@pytest.fixture
def app_config(fake_data_dir: Path, osparc_simcore_root_dir: Path):
    with open(fake_data_dir / "test_activity_config.yml") as fh:
        content = fh.read()
        config = content.replace(
            "${OSPARC_SIMCORE_REPO_ROOTDIR}", str(osparc_simcore_root_dir)
        )

    return yaml.safe_load(config)


@pytest.fixture
def client(
    mocked_celery_client, loop, aiohttp_client, app_config, mock_orphaned_services
):
    app = create_safe_application(app_config)

    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_activity(app)

    cli = loop.run_until_complete(aiohttp_client(app))
    return cli


async def test_has_login_required(loop, client):
    resp = await client.get("/v0/activity/status")
    await assert_status(resp, web.HTTPUnauthorized)


async def test_monitoring_up(loop, mocked_login_required, mocked_monitoring, client):
    QUEUED_NODE_ID = "35f95ad4-67b8-4ed8-bd55-84a5d600e687"
    RUNNING_NODE_ID = "894dd8d5-de3b-4767-950c-7c3ed8f51d8c"

    resp = await client.get("/v0/activity/status")
    data, _ = await assert_status(resp, web.HTTPOk)
    assert QUEUED_NODE_ID in data, "Queued node not present"
    assert RUNNING_NODE_ID in data, "Running node not present"

    celery = data.get(QUEUED_NODE_ID, {})
    prometheus = data.get(RUNNING_NODE_ID, {})

    assert "queued" in celery, "There is no queued key for queued node"
    assert bool(celery.get("queued")), "Queued should be True for queued node"

    assert "limits" in prometheus, "There is no limits key for executing node"
    assert "stats" in prometheus, "There is no stats key for executed node"

    limits = prometheus.get("limits", {})
    assert limits.get("cpus") == 4.0, "Incorrect value: Cpu limit"
    assert limits.get("mem") == 2048.0, "Incorrect value: Memory limit"

    stats = prometheus.get("stats", {})
    assert stats.get("cpuUsage") == 3.9952102200000006, "Incorrect value: Cpu usage"
    assert stats.get("memUsage") == 177.664, "Incorrect value: Memory usage"


async def test_monitoring_down(
    loop, mocked_login_required, mocked_monitoring_down, client
):
    resp = await client.get("/v0/activity/status")
    await assert_status(resp, web.HTTPNoContent)

# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import urllib.parse
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, HTTPException, status
from models_library.services_metadata_published import ServiceMetaDataPublished
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_catalog.api._dependencies.director import get_director_client
from simcore_service_catalog.clients.director import DirectorClient


@pytest.fixture
def app_environment(monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "SC_BOOT_MODE": "local-development",
            # keep the director requests fast and verify it is effectively used
            "HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT": "3",
        },
    )


@pytest.fixture
def service_key_and_version(
    expected_director_rest_api_list_services: list[dict[str, Any]],
) -> tuple[str, str]:
    expected_service = expected_director_rest_api_list_services[0]
    return expected_service["key"], expected_service["version"]


async def test_director_client_high_level_api(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    expected_director_rest_api_list_services: list[dict[str, Any]],
    mocked_director_rest_api: MockRouter,
    app: FastAPI,
):
    # gets director client as used in handlers
    director_api = get_director_client(app)

    assert app.state.director_api == director_api
    assert isinstance(director_api, DirectorClient)

    # PING
    assert await director_api.is_responsive()

    # GET
    expected_service = ServiceMetaDataPublished(**expected_director_rest_api_list_services[0])
    assert await director_api.get_service(expected_service.key, expected_service.version) == expected_service


async def test_director_client_low_level_api(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    service_key_and_version: tuple[str, str],
    app: FastAPI,
):
    director_api = get_director_client(app)

    key, version = service_key_and_version

    service_labels = await director_api.get(f"/services/{urllib.parse.quote_plus(key)}/{version}/labels")

    assert service_labels

    service = await director_api.get(f"/services/{urllib.parse.quote_plus(key)}/{version}")
    assert service


async def test_director_client_get_service_extras_with_org_labels(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    service_key_and_version: tuple[str, str],
    app: FastAPI,
):
    director_api = get_director_client(app)

    key, version = service_key_and_version

    service_extras = await director_api.get_service_extras(key, version)

    # Check node requirements are present
    assert service_extras.node_requirements is not None
    assert service_extras.node_requirements.cpu > 0
    assert service_extras.node_requirements.ram > 0

    # Check service build details are present (since we have org.label-schema labels)
    assert service_extras.service_build_details is not None
    assert service_extras.service_build_details.build_date == "2023-04-17T08:04:15Z"
    assert service_extras.service_build_details.vcs_ref == "4d79449a2e79f8a3b3b2e1dd0290af9f3d1a8792"
    assert service_extras.service_build_details.vcs_url == "https://github.com/ITISFoundation/jupyter-math.git"


async def test_director_client_get_service_extras_without_org_labels(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api_base: MockRouter,
    service_key_and_version: tuple[str, str],
    get_mocked_service_labels: Callable[..., dict],
    app: FastAPI,
):
    # Setup mock without org.label-schema labels
    service_key, service_version = service_key_and_version

    # Mock the labels endpoint without org labels
    @mocked_director_rest_api_base.get(
        path__regex=r"^/services/(?P<service_key>[/\w-]+)/(?P<service_version>[0-9\.]+)/labels$",
        name="get_service_labels_no_org",
    )
    def _get_service_labels_no_org(request, service_key, service_version):
        return httpx.Response(
            status_code=status.HTTP_200_OK,
            json={"data": get_mocked_service_labels(service_key, service_version, include_org_labels=False)},
        )

    director_api = get_director_client(app)
    service_extras = await director_api.get_service_extras(service_key, service_version)

    # Check node requirements are present
    assert service_extras.node_requirements is not None
    assert service_extras.node_requirements.cpu > 0
    assert service_extras.node_requirements.ram > 0

    # Check service build details are NOT present (since we don't have org.label-schema labels)
    assert service_extras.service_build_details is None


async def test_requests_honor_configured_timeout(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    service_key_and_version: tuple[str, str],
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
):
    """A hardcoded per-request timeout would silently shadow HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT"""
    settings = app.state.settings.CATALOG_CLIENT_REQUEST
    assert settings is not None
    assert settings.HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT == 3

    director_api = get_director_client(app)
    assert director_api.client.timeout == httpx.Timeout(3.0)

    requested_timeouts: list[Any] = []
    original_request = httpx.AsyncClient.request

    async def _capture_request(self: httpx.AsyncClient, method: str, url, **kwargs):
        requested_timeouts.append(kwargs.get("timeout"))
        return await original_request(self, method, url, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "request", _capture_request)

    key, version = service_key_and_version
    await director_api.get_service_labels(key, version)

    # no per-request override: the client's configured timeout applies
    assert requested_timeouts == [httpx.USE_CLIENT_DEFAULT]


_LABELS_PATH_REGEX = r"^/services/(?P<service_key>[/\w-]+)/(?P<service_version>[0-9\.]+)/labels$"


@pytest.mark.parametrize(
    "dropped_connection_error",
    [
        httpx.RemoteProtocolError("Server disconnected without sending a response."),
        httpx.ReadError("Connection reset by peer"),
    ],
    ids=lambda e: type(e).__name__,
)
async def test_director_client_retries_once_when_connection_is_dropped(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api_base: MockRouter,
    service_key_and_version: tuple[str, str],
    app: FastAPI,
    dropped_connection_error: Exception,
):
    labels = {"io.simcore.name": "some-service"}
    labels_route = mocked_director_rest_api_base.get(path__regex=_LABELS_PATH_REGEX, name="labels_flaky").mock(
        side_effect=[dropped_connection_error, httpx.Response(status.HTTP_200_OK, json={"data": labels})]
    )

    key, version = service_key_and_version
    assert await get_director_client(app).get_service_labels(key, version) == labels
    assert labels_route.call_count == 2


@pytest.mark.parametrize(
    "error, expected_calls",
    [
        (httpx.RemoteProtocolError("Server disconnected without sending a response."), 2),
        (httpx.ReadTimeout("timed out"), 1),
    ],
    ids=["dropped-connection-retried-once", "timeout-not-retried"],
)
async def test_director_client_gives_up_after_failed_attempts(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api_base: MockRouter,
    service_key_and_version: tuple[str, str],
    app: FastAPI,
    error: Exception,
    expected_calls: int,
):
    labels_route = mocked_director_rest_api_base.get(path__regex=_LABELS_PATH_REGEX, name="labels_down").mock(
        side_effect=error
    )

    key, version = service_key_and_version
    with pytest.raises(HTTPException) as exc_info:
        await get_director_client(app).get_service_labels(key, version)

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert labels_route.call_count == expected_calls

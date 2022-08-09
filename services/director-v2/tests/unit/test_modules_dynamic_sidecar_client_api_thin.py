# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from typing import Any, Callable, Optional

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI, status
from httpx import Response
from pydantic import AnyHttpUrl, parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx import MockRouter, Route
from respx.types import SideEffectTypes
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._thin import (
    ThinDynamicSidecarClient,
)

# NOTE: typing and callables cannot
MockRequestType = Callable[
    [str, str, Optional[Response], Optional[SideEffectTypes]], Route
]


# UTILS


def assert_responses(mocked: Response, result: Optional[Response]) -> None:
    assert result is not None
    assert mocked.status_code == result.status_code
    assert mocked.headers == result.headers
    assert mocked.text == result.text


# FIXTURES


@pytest.fixture
def mocked_app(monkeypatch: MonkeyPatch, mock_env: EnvVarsDict) -> FastAPI:
    monkeypatch.setenv("S3_ENDPOINT", "")
    monkeypatch.setenv("S3_ACCESS_KEY", "")
    monkeypatch.setenv("S3_SECRET_KEY", "")
    monkeypatch.setenv("S3_BUCKET_NAME", "")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")

    monkeypatch.setenv("POSTGRES_HOST", "")
    monkeypatch.setenv("POSTGRES_USER", "")
    monkeypatch.setenv("POSTGRES_PASSWORD", "")
    monkeypatch.setenv("POSTGRES_DB", "")

    # reduce number of retries to make more reliable
    monkeypatch.setenv("DYNAMIC_SIDECAR_API_CLIENT_REQUEST_MAX_RETRIES", "1")

    app = FastAPI()
    app.state.settings = AppSettings.create_from_envs()
    return app


@pytest.fixture
def thin_client(mocked_app: FastAPI) -> ThinDynamicSidecarClient:
    return ThinDynamicSidecarClient(mocked_app)


@pytest.fixture
def dynamic_sidecar_endpoint() -> AnyHttpUrl:
    return parse_obj_as(AnyHttpUrl, "http://missing-host:1111")


@pytest.fixture
def mock_request(
    dynamic_sidecar_endpoint: AnyHttpUrl, respx_mock: MockRouter
) -> MockRequestType:
    def request_mock(
        method: str,
        path: str,
        return_value: Optional[Response] = None,
        side_effect: Optional[SideEffectTypes] = None,
    ) -> Route:
        print(f"Mocking {path=}")
        return respx_mock.request(
            method=method, url=f"{dynamic_sidecar_endpoint}{path}"
        ).mock(return_value=return_value, side_effect=side_effect)

    return request_mock


# TESTS


async def test_get_health(
    thin_client: ThinDynamicSidecarClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
) -> None:
    mock_response = Response(status.HTTP_200_OK)
    mock_request("GET", "/health", mock_response, None)

    response = await thin_client.get_health(dynamic_sidecar_endpoint)
    assert_responses(mock_response, response)


@pytest.mark.parametrize("only_status", [False, True])
async def test_get_containers(
    thin_client: ThinDynamicSidecarClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    only_status: bool,
) -> None:
    mock_response = Response(status.HTTP_200_OK)
    mock_request(
        "GET",
        f"{dynamic_sidecar_endpoint}/{thin_client.API_VERSION}/containers?only_status={str(only_status).lower()}",
        mock_response,
        None,
    )

    response = await thin_client.get_containers(
        dynamic_sidecar_endpoint, only_status=only_status
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize("is_enabled", [False, True])
async def test_post_patch_containers_directory_watcher(
    thin_client: ThinDynamicSidecarClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    is_enabled: bool,
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    mock_request(
        "PATCH",
        f"{dynamic_sidecar_endpoint}/{thin_client.API_VERSION}/containers/directory-watcher",
        mock_response,
        None,
    )

    response = await thin_client.patch_containers_directory_watcher(
        dynamic_sidecar_endpoint, is_enabled=is_enabled
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize("outputs_labels", [{}, {"some": "data"}])
async def test_post_containers_ports_outputs_dirs(
    thin_client: ThinDynamicSidecarClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    outputs_labels: dict[str, Any],
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}/{thin_client.API_VERSION}/containers/ports/outputs/dirs",
        mock_response,
        None,
    )

    response = await thin_client.post_containers_ports_outputs_dirs(
        dynamic_sidecar_endpoint, outputs_labels=outputs_labels
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize("dynamic_sidecar_network_name", ["test_nw_name"])
async def test_get_containers_name(
    thin_client: ThinDynamicSidecarClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    dynamic_sidecar_network_name: str,
) -> None:
    mock_response = Response(status.HTTP_200_OK)
    encoded_filters = json.dumps(dict(network=dynamic_sidecar_network_name))
    mock_request(
        "GET",
        (
            f"{dynamic_sidecar_endpoint}/{thin_client.API_VERSION}"
            f"/containers/name?filters={encoded_filters}"
        ),
        mock_response,
        None,
    )

    response = await thin_client.get_containers_name(
        dynamic_sidecar_endpoint,
        dynamic_sidecar_network_name=dynamic_sidecar_network_name,
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize("network_aliases", [[], ["an_alias"], ["multuple_aliases"]])
async def test_post_containers_networks_attach(
    thin_client: ThinDynamicSidecarClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    network_aliases: list[str],
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    container_id = "a_container_id"
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}/{thin_client.API_VERSION}/containers/{container_id}/networks:attach",
        mock_response,
        None,
    )

    response = await thin_client.post_containers_networks_attach(
        dynamic_sidecar_endpoint,
        container_id=container_id,
        network_id="network_id",
        network_aliases=network_aliases,
    )
    assert_responses(mock_response, response)


async def test_post_containers_networks_detach(
    thin_client: ThinDynamicSidecarClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    container_id = "a_container_id"
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}/{thin_client.API_VERSION}/containers/{container_id}/networks:detach",
        mock_response,
        None,
    )

    response = await thin_client.post_containers_networks_detach(
        dynamic_sidecar_endpoint, container_id=container_id, network_id="network_id"
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize(
    "handler_name, mock_endpoint, extra_kwargs",
    [
        pytest.param(
            "post_containers_tasks",
            "/containers",
            dict(compose_spec="some_fake_compose_as_str"),
            id="post_containers_tasks",
        ),
        pytest.param(
            "post_containers_tasks_down",
            "/containers:down",
            {},
            id="down",
        ),
        pytest.param(
            "post_containers_tasks_state_restore",
            "/containers/state:restore",
            {},
            id="state_restore",
        ),
        pytest.param(
            "post_containers_tasks_state_save",
            "/containers/state:save",
            {},
            id="state_save",
        ),
        pytest.param(
            "post_containers_tasks_ports_inputs_pull",
            "/containers/ports/inputs:pull",
            {},
            id="ports_inputs_pull",
        ),
        pytest.param(
            "post_containers_tasks_ports_outputs_pull",
            "/containers/ports/outputs:pull",
            {},
            id="ports_outputs_pull",
        ),
        pytest.param(
            "post_containers_tasks_ports_outputs_push",
            "/containers/ports/outputs:push",
            {},
            id="ports_outputs_push",
        ),
        pytest.param(
            "post_containers_tasks_restart",
            "/containers:restart",
            {},
            id="restart",
        ),
    ],
)
async def test_post_containers_tasks(
    thin_client: ThinDynamicSidecarClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    handler_name: str,
    mock_endpoint: str,
    extra_kwargs: dict[str, Any],
) -> None:
    mock_response = Response(status.HTTP_202_ACCEPTED, json="mocked_task_id")
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}/{thin_client.API_VERSION}{mock_endpoint}",
        mock_response,
        None,
    )

    thin_client_handler = getattr(thin_client, handler_name)
    response = await thin_client_handler(dynamic_sidecar_endpoint, **extra_kwargs)
    assert_responses(mock_response, response)

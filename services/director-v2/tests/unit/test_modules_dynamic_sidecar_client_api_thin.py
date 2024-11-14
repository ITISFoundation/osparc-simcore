# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from collections.abc import AsyncIterable, Callable
from typing import Any

import pytest
from faker import Faker
from fastapi import FastAPI, status
from httpx import Response
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from models_library.sidecar_volumes import VolumeCategory, VolumeStatus
from pydantic import AnyHttpUrl, TypeAdapter
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx import MockRouter, Route
from respx.types import SideEffectTypes
from servicelib.docker_constants import SUFFIX_EGRESS_PROXY_NAME
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._thin import (
    ThinSidecarsClient,
)

MockRequestType = Callable[[str, str, Response | None, SideEffectTypes | None], Route]


# UTILS


def assert_responses(mocked: Response, result: Response | None) -> None:
    assert result is not None
    assert mocked.status_code == result.status_code
    assert mocked.headers == result.headers
    assert mocked.text == result.text


@pytest.fixture
def mocked_app(
    monkeypatch: pytest.MonkeyPatch, mock_env: EnvVarsDict, faker: Faker
) -> FastAPI:
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")

    monkeypatch.setenv("POSTGRES_HOST", "")
    monkeypatch.setenv("POSTGRES_USER", "")
    monkeypatch.setenv("POSTGRES_PASSWORD", "")
    monkeypatch.setenv("POSTGRES_DB", "")

    app = FastAPI()
    app.state.settings = AppSettings.create_from_envs()
    return app


@pytest.fixture
async def thin_client(mocked_app: FastAPI) -> AsyncIterable[ThinSidecarsClient]:
    async with ThinSidecarsClient(mocked_app) as client:
        yield client


@pytest.fixture
def dynamic_sidecar_endpoint() -> AnyHttpUrl:
    return TypeAdapter(AnyHttpUrl).validate_python("http://missing-host:1111")


@pytest.fixture
def mock_request(respx_mock: MockRouter) -> MockRequestType:
    def request_mock(
        method: str,
        path: str,
        return_value: Response | None = None,
        side_effect: SideEffectTypes | None = None,
    ) -> Route:
        print(f"Mocking {path=}")
        return respx_mock.request(method=method, url=f"{path}").mock(
            return_value=return_value, side_effect=side_effect
        )

    return request_mock


async def test_get_health(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
) -> None:
    mock_response = Response(status.HTTP_200_OK)
    mock_request("GET", "/health", mock_response, None)

    response = await thin_client.get_health(dynamic_sidecar_endpoint)
    assert_responses(mock_response, response)


async def test_get_health_no_retry(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
):
    mock_response = Response(status.HTTP_200_OK)
    mock_request("GET", "/health", mock_response, None)

    response = await thin_client.get_health_no_retry(dynamic_sidecar_endpoint)
    assert_responses(mock_response, response)


@pytest.mark.parametrize("only_status", [False, True])
async def test_get_containers(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    only_status: bool,
) -> None:
    mock_response = Response(status.HTTP_200_OK)
    mock_request(
        "GET",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}/containers?only_status={str(only_status).lower()}",
        mock_response,
        None,
    )

    response = await thin_client.get_containers(
        dynamic_sidecar_endpoint, only_status=only_status
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize("enable_outputs", [False, True])
@pytest.mark.parametrize("enable_inputs", [False, True])
async def test_post_patch_containers_ports_io(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    enable_outputs: bool,
    enable_inputs: bool,
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    mock_request(
        "PATCH",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}/containers/ports/io",
        mock_response,
        None,
    )

    response = await thin_client.patch_containers_ports_io(
        dynamic_sidecar_endpoint,
        enable_outputs=enable_outputs,
        enable_inputs=enable_inputs,
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize("outputs_labels", [{}, {"some": "data"}])
async def test_post_containers_ports_outputs_dirs(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    outputs_labels: dict[str, Any],
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}/containers/ports/outputs/dirs",
        mock_response,
        None,
    )

    response = await thin_client.post_containers_ports_outputs_dirs(
        dynamic_sidecar_endpoint, outputs_labels=outputs_labels
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize("dynamic_sidecar_network_name", ["test_nw_name"])
async def test_get_containers_name(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    dynamic_sidecar_network_name: str,
) -> None:
    mock_response = Response(status.HTTP_200_OK)

    encoded_filters = json.dumps(
        {
            "network": dynamic_sidecar_network_name,
            "exclude": SUFFIX_EGRESS_PROXY_NAME,
        }
    )
    mock_request(
        "GET",
        (
            f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}"
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
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    network_aliases: list[str],
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    container_id = "a_container_id"
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}/containers/{container_id}/networks:attach",
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
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    container_id = "a_container_id"
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}/containers/{container_id}/networks:detach",
        mock_response,
        None,
    )

    response = await thin_client.post_containers_networks_detach(
        dynamic_sidecar_endpoint, container_id=container_id, network_id="network_id"
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize("volume_category", VolumeCategory)
@pytest.mark.parametrize("volume_status", VolumeStatus)
async def test_put_volumes(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    volume_category: str,
    volume_status: VolumeStatus,
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    mock_request(
        "PUT",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}/volumes/{volume_category}",
        mock_response,
        None,
    )

    response = await thin_client.put_volumes(
        dynamic_sidecar_endpoint,
        volume_category=volume_category,
        volume_status=volume_status,
    )
    assert_responses(mock_response, response)


@pytest.mark.parametrize(
    "handler_name, mock_endpoint, extra_kwargs",
    [
        pytest.param(
            "post_containers_tasks",
            "/containers",
            {
                "metrics_params": TypeAdapter(
                    CreateServiceMetricsAdditionalParams
                ).validate_python(
                    CreateServiceMetricsAdditionalParams.model_config[
                        "json_schema_extra"
                    ]["example"],
                )
            },
            id="post_containers_tasks",
        ),
        pytest.param(
            "post_containers_tasks_down",
            "/containers:down",
            {},
            id="down",
        ),
        pytest.param(
            "post_containers_images_pull",
            "/containers/images:pull",
            {},
            id="user_servces_images_pull",
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
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
    handler_name: str,
    mock_endpoint: str,
    extra_kwargs: dict[str, Any],
) -> None:
    mock_response = Response(status.HTTP_202_ACCEPTED, json="mocked_task_id")
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}{mock_endpoint}",
        mock_response,
        None,
    )

    thin_client_handler = getattr(thin_client, handler_name)
    response = await thin_client_handler(dynamic_sidecar_endpoint, **extra_kwargs)
    assert_responses(mock_response, response)


async def test_get_containers_inactivity(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
) -> None:
    mock_response = Response(status.HTTP_200_OK, json={})
    mock_request(
        "GET",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}/containers/activity",
        mock_response,
        None,
    )

    response = await thin_client.get_containers_activity(dynamic_sidecar_endpoint)
    assert_responses(mock_response, response)


async def test_post_disk_reserved_free(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
) -> None:
    mock_response = Response(status.HTTP_204_NO_CONTENT)
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}/disk/reserved:free",
        mock_response,
        None,
    )

    response = await thin_client.post_disk_reserved_free(dynamic_sidecar_endpoint)
    assert_responses(mock_response, response)


async def test_post_containers_compose_spec(
    thin_client: ThinSidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_request: MockRequestType,
):
    mock_response = Response(status.HTTP_202_ACCEPTED)
    mock_request(
        "POST",
        f"{dynamic_sidecar_endpoint}{thin_client.API_VERSION}/containers/compose-spec",
        mock_response,
        None,
    )

    response = await thin_client.post_containers_compose_spec(
        dynamic_sidecar_endpoint, compose_spec="some_fake_compose_as_str"
    )
    assert_responses(mock_response, response)

# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from contextlib import contextmanager
from typing import Any, AsyncIterable, Callable, Iterator, Optional
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from httpx import HTTPError, Response
from pydantic import AnyHttpUrl, parse_obj_as
from pytest import LogCaptureFixture, MonkeyPatch
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._errors import (
    ClientHttpError,
    UnexpectedStatusError,
)
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._public import (
    DynamicSidecarClient,
    get_dynamic_sidecar_client,
)
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._public import (
    setup as api_client_setup,
)
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._public import (
    shutdown,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    EntrypointContainerNotFoundError,
)


@pytest.fixture
def dynamic_sidecar_endpoint() -> AnyHttpUrl:
    return parse_obj_as(AnyHttpUrl, "http://missing-host:1111")


@pytest.fixture
def mock_env(monkeypatch: MonkeyPatch, mock_env: EnvVarsDict) -> None:
    monkeypatch.setenv("S3_ACCESS_KEY", "")
    monkeypatch.setenv("S3_SECRET_KEY", "")
    monkeypatch.setenv("S3_BUCKET_NAME", "")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")

    monkeypatch.setenv("POSTGRES_HOST", "")
    monkeypatch.setenv("POSTGRES_USER", "")
    monkeypatch.setenv("POSTGRES_PASSWORD", "")
    monkeypatch.setenv("POSTGRES_DB", "")

    # reduce number of retries to make more reliable
    monkeypatch.setenv("DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S", "3")
    monkeypatch.setenv("S3_ENDPOINT", "")


@pytest.fixture
async def dynamic_sidecar_client(
    mock_env: EnvVarsDict,
) -> AsyncIterable[DynamicSidecarClient]:
    app = FastAPI()
    app.state.settings = AppSettings.create_from_envs()

    # WARNING: pytest gets confused with 'setup', use instead alias 'api_client_setup'
    await api_client_setup(app)
    yield get_dynamic_sidecar_client(app)
    await shutdown(app)


@pytest.fixture
def request_timeout() -> int:
    # below refer to exponential wait step duration
    return 1 + 2


@pytest.fixture
def raise_request_timeout(
    monkeypatch: MonkeyPatch, request_timeout: int, mock_env: EnvVarsDict
) -> None:
    monkeypatch.setenv("DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S", f"{request_timeout}")


@pytest.fixture
def get_patched_client(
    dynamic_sidecar_client: DynamicSidecarClient, mocker: MockerFixture
) -> Callable:
    @contextmanager
    def wrapper(
        method: str,
        return_value: Optional[Any] = None,
        side_effect: Optional[Callable] = None,
    ) -> Iterator[DynamicSidecarClient]:
        mocker.patch(
            f"simcore_service_director_v2.modules.dynamic_sidecar.api_client._thin.ThinDynamicSidecarClient.{method}",
            return_value=return_value,
            side_effect=side_effect,
        )
        yield dynamic_sidecar_client

    return wrapper


@pytest.mark.parametrize("is_healthy", [True, False])
async def test_is_healthy_api_ok(
    get_patched_client: Callable, dynamic_sidecar_endpoint: AnyHttpUrl, is_healthy: bool
) -> None:
    mock_json = {"is_healthy": is_healthy}
    with get_patched_client(
        "get_health",
        return_value=Response(status_code=status.HTTP_200_OK, json=mock_json),
    ) as client:
        assert await client.is_healthy(dynamic_sidecar_endpoint) == is_healthy


async def test_is_healthy_times_out(
    raise_request_timeout: None,
    dynamic_sidecar_client: DynamicSidecarClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    caplog_info_level: LogCaptureFixture,
) -> None:
    assert await dynamic_sidecar_client.is_healthy(dynamic_sidecar_endpoint) is False
    # check if the right amount of messages was captured by the logs
    unexpected_counter = 1
    for log_message in caplog_info_level.messages:
        if log_message.startswith("Retrying"):
            assert "as it raised" in log_message
            continue
        assert log_message.startswith(f"Request timed-out after {unexpected_counter}")
        unexpected_counter += 1


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(
            UnexpectedStatusError(
                Response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content="some mocked error",
                    request=AsyncMock(),
                ),
                status.HTTP_200_OK,
            ),
            id="UnexpectedStatusError",
        ),
        pytest.param(
            ClientHttpError(HTTPError("another mocked error")), id="HTTPError"
        ),
    ],
)
async def test_is_healthy_api_error(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    side_effect: Exception,
) -> None:
    with get_patched_client(
        "get_health",
        side_effect=side_effect,
    ) as client:
        assert await client.is_healthy(dynamic_sidecar_endpoint) == False


async def test_containers_inspect(
    get_patched_client: Callable, dynamic_sidecar_endpoint: AnyHttpUrl
) -> None:
    mock_json = {"ok": "data"}
    with get_patched_client(
        "get_containers",
        return_value=Response(status_code=status.HTTP_200_OK, json=mock_json),
    ) as client:
        assert await client.containers_inspect(dynamic_sidecar_endpoint) == mock_json


async def test_containers_docker_status_api_ok(
    get_patched_client: Callable, dynamic_sidecar_endpoint: AnyHttpUrl
) -> None:
    mock_json = {"container_id": {"ok": "data"}}
    with get_patched_client(
        "get_containers",
        return_value=Response(status_code=status.HTTP_200_OK, json=mock_json),
    ) as client:
        assert (
            await client.containers_docker_status(dynamic_sidecar_endpoint) == mock_json
        )


async def test_containers_docker_status_api_error(
    get_patched_client: Callable, dynamic_sidecar_endpoint: AnyHttpUrl
) -> None:
    with get_patched_client(
        "get_containers",
        side_effect=UnexpectedStatusError(
            Response(
                status_code=status.HTTP_400_BAD_REQUEST,
                content="some mocked error",
                request=AsyncMock(),
            ),
            status.HTTP_200_OK,
        ),
    ) as client:
        assert await client.containers_docker_status(dynamic_sidecar_endpoint) == {}


async def test_service_disable_dir_watcher(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
) -> None:
    with get_patched_client(
        "patch_containers_directory_watcher",
        return_value=Response(status_code=status.HTTP_204_NO_CONTENT),
    ) as client:
        assert (
            await client.service_disable_dir_watcher(dynamic_sidecar_endpoint) == None
        )


async def test_service_enable_dir_watcher(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
) -> None:
    with get_patched_client(
        "patch_containers_directory_watcher",
        return_value=Response(status_code=status.HTTP_204_NO_CONTENT),
    ) as client:
        assert await client.service_enable_dir_watcher(dynamic_sidecar_endpoint) == None


@pytest.mark.parametrize("outputs_labels", [{}, {"ok": "data"}])
async def test_service_outputs_create_dirs(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    outputs_labels: dict[str, Any],
) -> None:
    with get_patched_client(
        "post_containers_ports_outputs_dirs",
        return_value=Response(status_code=status.HTTP_204_NO_CONTENT),
    ) as client:
        assert (
            await client.service_outputs_create_dirs(
                dynamic_sidecar_endpoint, outputs_labels
            )
            == None
        )


@pytest.mark.parametrize("dynamic_sidecar_network_name", ["a_test_network"])
async def test_get_entrypoint_container_name_ok(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    dynamic_sidecar_network_name: str,
) -> None:
    with get_patched_client(
        "get_containers_name",
        return_value=Response(status_code=status.HTTP_200_OK, json="a_test_container"),
    ) as client:
        assert (
            await client.get_entrypoint_container_name(
                dynamic_sidecar_endpoint, dynamic_sidecar_network_name
            )
            == "a_test_container"
        )


@pytest.mark.parametrize("dynamic_sidecar_network_name", ["a_test_network"])
async def test_get_entrypoint_container_name_api_not_found(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    dynamic_sidecar_network_name: str,
) -> None:
    with get_patched_client(
        "get_containers_name",
        side_effect=UnexpectedStatusError(
            Response(status_code=status.HTTP_404_NOT_FOUND, request=AsyncMock()),
            status.HTTP_204_NO_CONTENT,
        ),
    ) as client:
        with pytest.raises(EntrypointContainerNotFoundError):
            await client.get_entrypoint_container_name(
                dynamic_sidecar_endpoint, dynamic_sidecar_network_name
            )


@pytest.mark.parametrize("network_aliases", [[], ["an-alias"], ["alias-1", "alias-2"]])
async def test_attach_container_to_network(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    network_aliases: list[str],
) -> None:
    with get_patched_client(
        "post_containers_networks_attach",
        return_value=Response(status_code=status.HTTP_204_NO_CONTENT),
    ) as client:
        assert (
            # pylint:disable=protected-access
            await client._attach_container_to_network(
                dynamic_sidecar_endpoint,
                container_id="container_id",
                network_id="network_id",
                network_aliases=network_aliases,
            )
            == None
        )


async def test_detach_container_from_network(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
) -> None:
    with get_patched_client(
        "post_containers_networks_detach",
        return_value=Response(status_code=status.HTTP_204_NO_CONTENT),
    ) as client:
        assert (
            # pylint:disable=protected-access
            await client._detach_container_from_network(
                dynamic_sidecar_endpoint,
                container_id="container_id",
                network_id="network_id",
            )
            == None
        )

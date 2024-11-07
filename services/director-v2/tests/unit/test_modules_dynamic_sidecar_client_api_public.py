# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from contextlib import contextmanager
from typing import Any, AsyncIterable, Callable, Iterator
from unittest.mock import AsyncMock
from models_library.api_schemas_dynamic_sidecar.containers import (
    ActivityInfoOrNone
)

import pytest
from common_library.json_serialization import json_dumps
from faker import Faker
from fastapi import FastAPI, status
from httpx import HTTPError, Response
from models_library.sidecar_volumes import VolumeCategory, VolumeStatus
from pydantic import AnyHttpUrl, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.http_client_thin import ClientHttpError, UnexpectedStatusError
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._public import (
    SidecarsClient,
    get_sidecars_client,
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
    return TypeAdapter(AnyHttpUrl).validate_python("http://missing-host:1111")


@pytest.fixture
def mock_env(
    monkeypatch: pytest.MonkeyPatch, mock_env: EnvVarsDict, faker: Faker
) -> None:
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")

    monkeypatch.setenv("POSTGRES_HOST", "")
    monkeypatch.setenv("POSTGRES_USER", "")
    monkeypatch.setenv("POSTGRES_PASSWORD", "")
    monkeypatch.setenv("POSTGRES_DB", "")

    # reduce number of retries to make more reliable
    monkeypatch.setenv("DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S", "3")
    monkeypatch.setenv("S3_ENDPOINT", faker.url())


@pytest.fixture
async def sidecars_client(
    mock_env: EnvVarsDict, faker: Faker
) -> AsyncIterable[SidecarsClient]:
    app = FastAPI()
    app.state.settings = AppSettings.create_from_envs()

    # WARNING: pytest gets confused with 'setup', use instead alias 'api_client_setup'
    await api_client_setup(app)
    yield await get_sidecars_client(app, faker.uuid4())
    await shutdown(app)


@pytest.fixture
def request_timeout() -> int:
    # below refer to exponential wait step duration
    return 1 + 2


@pytest.fixture
def raise_request_timeout(
    monkeypatch: pytest.MonkeyPatch, request_timeout: int, mock_env: EnvVarsDict
) -> None:
    monkeypatch.setenv("DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S", f"{request_timeout}")


@pytest.fixture
def get_patched_client(
    sidecars_client: SidecarsClient, mocker: MockerFixture
) -> Callable:
    @contextmanager
    def wrapper(
        method: str,
        return_value: Any | None = None,
        side_effect: Callable | None = None,
    ) -> Iterator[SidecarsClient]:
        mocker.patch(
            f"simcore_service_director_v2.modules.dynamic_sidecar.api_client._thin.ThinSidecarsClient.{method}",
            return_value=return_value,
            side_effect=side_effect,
        )
        yield sidecars_client

    return wrapper


@pytest.mark.parametrize("is_healthy", [True, False])
@pytest.mark.parametrize("with_retry", [True, False])
async def test_is_healthy(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    is_healthy: bool,
    with_retry: bool,
) -> None:
    mock_json = {"is_healthy": is_healthy}
    with get_patched_client(
        "get_health" if with_retry else "get_health_no_retry",
        return_value=Response(status_code=status.HTTP_200_OK, json=mock_json),
    ) as client:
        assert (
            await client.is_healthy(dynamic_sidecar_endpoint, with_retry=with_retry)
            == is_healthy
        )


async def test_is_healthy_times_out(
    raise_request_timeout: None,
    sidecars_client: SidecarsClient,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    caplog_info_level: pytest.LogCaptureFixture,
) -> None:
    assert await sidecars_client.is_healthy(dynamic_sidecar_endpoint) is False
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
                response=Response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content="some mocked error",
                    request=AsyncMock(),
                ),
                expecting=status.HTTP_200_OK,
            ),
            id="UnexpectedStatusError",
        ),
        pytest.param(
            ClientHttpError(error=HTTPError("another mocked error")), id="HTTPError"
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
        assert await client.is_healthy(dynamic_sidecar_endpoint) is False


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
            response=Response(
                status_code=status.HTTP_400_BAD_REQUEST,
                content="some mocked error",
                request=AsyncMock(),
            ),
            expecting=status.HTTP_200_OK,
        ),
    ) as client:
        assert await client.containers_docker_status(dynamic_sidecar_endpoint) == {}


@pytest.mark.parametrize("enable_outputs", [True, False])
@pytest.mark.parametrize("enable_inputs", [True, False])
async def test_toggle_service_ports_io(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    enable_outputs: bool,
    enable_inputs: bool,
) -> None:
    with get_patched_client(
        "patch_containers_ports_io",
        return_value=Response(status_code=status.HTTP_204_NO_CONTENT),
    ) as client:
        assert (
            await client.toggle_service_ports_io(
                dynamic_sidecar_endpoint,
                enable_outputs=enable_outputs,
                enable_inputs=enable_inputs,
            )
            is None
        )


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
            is None
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
            response=Response(
                status_code=status.HTTP_404_NOT_FOUND, request=AsyncMock()
            ),
            expecting=status.HTTP_204_NO_CONTENT,
        ),
    ) as client, pytest.raises(EntrypointContainerNotFoundError):
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
            await client._attach_container_to_network(  # noqa: SLF001
                dynamic_sidecar_endpoint,
                container_id="container_id",
                network_id="network_id",
                network_aliases=network_aliases,
            )
            is None
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
            await client._detach_container_from_network(  # noqa: SLF001
                dynamic_sidecar_endpoint,
                container_id="container_id",
                network_id="network_id",
            )
            is None
        )


@pytest.mark.parametrize("volume_category", VolumeCategory)
@pytest.mark.parametrize("volume_status", VolumeStatus)
async def test_update_volume_state(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    volume_category: VolumeCategory,
    volume_status: VolumeStatus,
) -> None:
    with get_patched_client(
        "put_volumes",
        return_value=Response(status_code=status.HTTP_204_NO_CONTENT),
    ) as client:
        assert (
            await client.update_volume_state(
                dynamic_sidecar_endpoint,
                volume_category=volume_category,
                volume_status=volume_status,
            )
            is None
        )


@pytest.mark.parametrize(
    "mock_dict",
    [{"seconds_inactive": 1}, {"seconds_inactive": 0}, None],
)
async def test_get_service_activity(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
    mock_dict: dict[str, Any],
) -> None:
    with get_patched_client(
        "get_containers_activity",
        return_value=Response(
            status_code=status.HTTP_200_OK, text=json_dumps(mock_dict)
        ),
    ) as client:
        assert await client.get_service_activity(dynamic_sidecar_endpoint) == TypeAdapter(ActivityInfoOrNone).validate_python(mock_dict)


async def test_free_reserved_disk_space(
    get_patched_client: Callable,
    dynamic_sidecar_endpoint: AnyHttpUrl,
) -> None:
    with get_patched_client(
        "post_disk_reserved_free",
        return_value=Response(status_code=status.HTTP_204_NO_CONTENT),
    ) as client:
        assert (
            await client.free_reserved_disk_space(
                dynamic_sidecar_endpoint,
            )
            is None
        )

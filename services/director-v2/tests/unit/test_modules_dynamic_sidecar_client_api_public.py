from contextlib import contextmanager
import json
from typing import Awaitable, Callable, Coroutine, Any, Iterable, Iterator, Optional
from unittest.mock import AsyncMock
import pytest
from pydantic import AnyHttpUrl, parse_obj_as
from fastapi import FastAPI, status
from pytest_mock import MockerFixture
from _pytest.monkeypatch import MonkeyPatch
from httpx import Response, HTTPError
from simcore_service_director_v2.core.settings import AppSettings


from simcore_service_director_v2.modules.dynamic_sidecar.api_client._public import (
    DynamicSidecarClient,
)
from simcore_service_director_v2.modules.dynamic_sidecar.api_client._errors import (
    UnexpectedStatusError,
)


from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarUnexpectedResponseStatus,
)

pytestmark = pytest.mark.asyncio

# FIXTURES


@pytest.fixture
def dynamic_sidecar_endpoint() -> AnyHttpUrl:
    return parse_obj_as(AnyHttpUrl, "http://test-client:8282")


@pytest.fixture
def mocked_app(monkeypatch: MonkeyPatch, mock_env: None) -> FastAPI:
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
def dynamic_sidecar_client(mocked_app: FastAPI) -> DynamicSidecarClient:
    return DynamicSidecarClient(mocked_app)


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
            f"simcore_service_director_v2.modules.dynamic_sidecar.api_client._public.DynamicSidecarClient.{method}",
            return_value=return_value,
            side_effect=side_effect,
        )
        yield dynamic_sidecar_client

    return wrapper


# TESTS


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


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(
            DynamicSidecarUnexpectedResponseStatus(
                Response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content="some mocked error",
                    request=AsyncMock(),
                )
            ),
            id="DynamicSidecarUnexpectedResponseStatus",
        ),
        pytest.param(HTTPError("another mocked error"), id="HTTPError"),
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


async def test_start_service_creation(
    get_patched_client: Callable, dynamic_sidecar_endpoint: AnyHttpUrl
) -> None:
    docker_compose_reply = "a mocked docker compose plain string reply"
    with get_patched_client(
        "post_containers",
        return_value=Response(
            status_code=status.HTTP_200_OK, content=docker_compose_reply
        ),
    ) as client:
        assert (
            await client.start_service_creation(
                dynamic_sidecar_endpoint, compose_spec="mock compose spec"
            )
            == None
        )

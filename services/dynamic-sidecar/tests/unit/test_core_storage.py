# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import multiprocessing
from collections.abc import AsyncIterable
from typing import Annotated, Final
from unittest.mock import Mock

import pytest
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from httpx import AsyncClient
from pydantic import TypeAdapter
from settings_library.node_ports import StorageAuthSettings
from simcore_service_dynamic_sidecar.core.storage import (
    _get_url,
    wait_for_storage_liveness,
)
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

_SERVER_STARTUP_TIMEOUT_S: Final[float] = 30


def _create_storage_app(username: str | None, password: str | None) -> FastAPI:
    app = FastAPI()
    security = HTTPBasic()

    @app.get("/")
    def health():
        return "ok"

    def _authenticate_user(
        credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    ):
        if credentials.username != username or credentials.password != password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Basic"},
            )
        return {"username": username}

    if username and password:

        @app.get("/v0/")
        async def protected_route(user: Annotated[dict, Depends(_authenticate_user)]):
            return {"message": f"Welcome, {user['username']}!"}

    else:

        @app.get("/v0/")
        async def unprotected_route():
            return {"message": "Welcome, no auth!"}

    return app


def _run_server(host: str, port: int, username: str | None, password: str | None) -> None:
    uvicorn.run(_create_storage_app(username, password), host=host, port=port)


@pytest.fixture
def storage_auth_settings(username: str | None, password: str | None) -> StorageAuthSettings:
    return TypeAdapter(StorageAuthSettings).validate_python(
        {
            "STORAGE_HOST": "localhost",
            "STORAGE_PORT": 44332,
            "STORAGE_USERNAME": username,
            "STORAGE_PASSWORD": password,
        }
    )


@pytest.fixture
async def mock_storage_server(
    username: str | None,
    password: str | None,
    storage_auth_settings: StorageAuthSettings,
) -> AsyncIterable[None]:
    process = multiprocessing.Process(
        target=_run_server,
        args=(
            storage_auth_settings.STORAGE_HOST,
            storage_auth_settings.STORAGE_PORT,
            username,
            password,
        ),
    )
    process.start()

    base_url = f"http://{storage_auth_settings.STORAGE_HOST}:{storage_auth_settings.STORAGE_PORT}"

    async with AsyncClient(timeout=1) as client:
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1),
            stop=stop_after_delay(_SERVER_STARTUP_TIMEOUT_S),
            reraise=True,
        ):
            with attempt:
                response = await client.get(f"{base_url}/")
                assert response.status_code == status.HTTP_200_OK

    yield None

    process.kill()
    process.join()


@pytest.fixture
def mock_dynamic_sidecar_app(
    storage_auth_settings: StorageAuthSettings,
) -> Mock:
    mock = Mock()
    mock.state.settings.NODE_PORTS_STORAGE_AUTH = storage_auth_settings
    return mock


_USERNAME_PASSWORD_TEST_CASES: Final[list] = [
    pytest.param("user", "password", id="authenticated"),
    pytest.param(None, None, id="no-auth"),
]


@pytest.mark.parametrize("username, password", _USERNAME_PASSWORD_TEST_CASES)
async def test_wait_for_storage_liveness(mock_storage_server: None, mock_dynamic_sidecar_app: Mock):
    await wait_for_storage_liveness(mock_dynamic_sidecar_app)


@pytest.mark.parametrize("username, password", _USERNAME_PASSWORD_TEST_CASES)
def test__get_url(storage_auth_settings: StorageAuthSettings):
    assert _get_url(storage_auth_settings) == "http://localhost:44332/v0/"

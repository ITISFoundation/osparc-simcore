# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import multiprocessing
from collections.abc import AsyncIterable
from datetime import timedelta
from typing import Annotated, Final
from unittest.mock import Mock

import pytest
import requests
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from settings_library.node_ports import StorageAuthSettings
from simcore_service_dynamic_sidecar.core.storage import (
    _get_url,
    wait_for_storage_liveness,
)
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed


@pytest.fixture
def mock_storage_app(username: str | None, password: str | None) -> FastAPI:
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


@pytest.fixture
def storage_auth_settings(
    username: str | None, password: str | None
) -> StorageAuthSettings:
    return TypeAdapter(StorageAuthSettings).validate_python(
        {
            "STORAGE_HOST": "localhost",
            "STORAGE_PORT": 44332,
            "STORAGE_USERNAME": username,
            "STORAGE_PASSWORD": password,
        }
    )


def _get_base_url(storage_auth_settings: StorageAuthSettings) -> str:
    return f"http://{storage_auth_settings.STORAGE_HOST}:{storage_auth_settings.STORAGE_PORT}"


@pytest.fixture
async def mock_storage_server(
    mock_storage_app: None, storage_auth_settings: StorageAuthSettings
) -> AsyncIterable[None]:
    def _run_server(app):
        uvicorn.run(
            app,
            host=storage_auth_settings.STORAGE_HOST,
            port=storage_auth_settings.STORAGE_PORT,
        )

    process = multiprocessing.Process(target=_run_server, args=(mock_storage_app,))
    process.start()

    base_url = _get_base_url(storage_auth_settings)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(1),
        reraise=True,
    ):
        with attempt:
            response = requests.get(f"{base_url}/", timeout=1)
            assert response.status_code == status.HTTP_200_OK

    yield None

    process.kill()


@pytest.fixture
def mock_liveness_timeout(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.service_liveness._DEFAULT_TIMEOUT_INTERVAL",
        new=timedelta(seconds=2),
    )


@pytest.fixture
def mock_dynamic_sidecar_app(
    mock_liveness_timeout: None, storage_auth_settings: StorageAuthSettings
) -> Mock:
    mock = Mock()
    mock.state.settings.NODE_PORTS_STORAGE_AUTH = storage_auth_settings
    return mock


_USERNAME_PASSWORD_TEST_CASES: Final[list] = [
    pytest.param("user", "password", id="authenticated"),
    pytest.param(None, None, id="no-auth"),
]


@pytest.mark.parametrize("username, password", _USERNAME_PASSWORD_TEST_CASES)
async def test_wait_for_storage_liveness(
    mock_storage_server: None, mock_dynamic_sidecar_app: Mock
):
    await wait_for_storage_liveness(mock_dynamic_sidecar_app)


@pytest.mark.parametrize("username, password", _USERNAME_PASSWORD_TEST_CASES)
def test__get_url(storage_auth_settings: StorageAuthSettings):
    assert _get_url(storage_auth_settings) == "http://localhost:44332/v0/"

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator, Callable

import httpx
import pytest
from fastapi import FastAPI, status
from httpx._transports.asgi import ASGITransport
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.schemas.auth import Token


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    disable_rabbitmq_and_rpc_setup: Callable,
    disable_db_setup: Callable,
) -> EnvVarsDict:
    # disables rabbit before creating app
    disable_rabbitmq_and_rpc_setup()
    disable_db_setup()

    #
    return app_environment


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # - Needed for app to trigger start/stop event handlers
    # -Prefer this client instead of fastapi.testclient.TestClient
    async with httpx.AsyncClient(
        app=app,
        base_url="http://payments.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        assert isinstance(client._transport, ASGITransport)
        yield client


@pytest.fixture
async def auth_headers(client: httpx.AsyncClient, app: FastAPI) -> dict[str, str]:
    # get access token
    settings: ApplicationSettings = app.state.settings
    assert settings

    form_data = {
        "username": settings.PAYMENTS_USERNAME,
        "password": settings.PAYMENTS_PASSWORD.get_secret_value(),
    }

    response = await client.post(
        "/v1/token",
        data=form_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = Token(**response.json())
    assert response.status_code == status.HTTP_200_OK
    assert token.token_type == "bearer"

    return {"Authorization": f"Bearer {token.access_token}"}

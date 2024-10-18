# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI, status
from pydantic import HttpUrl
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.schemas.auth import Token


async def test_bearer_token(httpbin_base_url: HttpUrl, faker: Faker):
    bearer_token = faker.word()
    headers = {"Authorization": f"Bearer {bearer_token}"}

    async with httpx.AsyncClient(
        base_url=f"{httpbin_base_url}", headers=headers
    ) as client:
        response = await client.get("/bearer")
        assert response.json() == {"authenticated": True, "token": bearer_token}


@pytest.mark.parametrize("valid_credentials", [True, False])
async def test_login_to_create_access_token(
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    client: httpx.AsyncClient,
    app: FastAPI,
    faker: Faker,
    valid_credentials: bool,
):
    # SEE fixture in conftest.py:auth_headers
    #
    # At some point might want to use httpx plugins as:
    # - https://docs.authlib.org/en/latest/client/httpx.html
    # OR implement an auth_flow interface
    # - https://www.python-httpx.org/advanced/#customizing-authentication
    #
    #
    settings: ApplicationSettings = app.state.settings
    assert settings

    form_data = {
        "username": settings.PAYMENTS_USERNAME,
        "password": settings.PAYMENTS_PASSWORD.get_secret_value(),
    }

    if not valid_credentials:
        form_data["username"] = faker.user_name()
        form_data["password"] = faker.password()

    response = await client.post(
        "/v1/token",
        data=form_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if valid_credentials:
        token = Token(**response.json())
        assert response.status_code == status.HTTP_200_OK
        assert token.token_type == "bearer"
    else:
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        error = response.json()
        assert "password" in error["detail"]

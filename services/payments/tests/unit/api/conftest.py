# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import httpx
import pytest
from fastapi import FastAPI, status
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.schemas.auth import Token


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

    headers = {"Authorization": f"Bearer {token.access_token}"}
    return headers

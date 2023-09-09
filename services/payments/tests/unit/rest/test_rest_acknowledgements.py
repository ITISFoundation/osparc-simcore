import httpx
from faker import Faker
from fastapi import FastAPI, status
from pydantic import HttpUrl
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.schemas.acknowledgements import AckPayment
from simcore_service_payments.models.schemas.auth import Token


async def test_bearer_token(httpbin_base_url: HttpUrl, faker: Faker):
    bearer_token = faker.word()
    headers = {"Authorization": f"Bearer {bearer_token}"}

    async with httpx.AsyncClient(base_url=httpbin_base_url, headers=headers) as client:
        response = await client.get("/bearer")
        assert response.json() == {"authenticated": True, "token": bearer_token}


async def test_login_complete_payment(
    client: httpx.AsyncClient, app: FastAPI, faker: Faker
):
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
        headers={"Content-Type": "applicaiton/x-www-form-urlencoded"},
    )
    token = Token(**response.json())
    assert response.status_code == status.HTTP_200_OK
    assert token.token_type == "bearer"

    # w/o header
    payments_id = faker.uuid4()
    payment_ack = AckPayment(success=True).dict()
    response = await client.post(
        f"/v1/payments/{payments_id}:ack",
        json=payment_ack,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text

    # w/ header
    headers = {"Authorization": f"Bearer {token.access_token}"}
    response = await client.post(
        f"/v1/payments/{payments_id}:ack", json=payment_ack, headers=headers
    )
    assert response.status_code != status.HTTP_401_UNAUTHORIZED, response.text

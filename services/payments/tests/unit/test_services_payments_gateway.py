# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Iterator

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from respx import MockRouter
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import (
    InitPayment,
    PaymentInitiated,
)
from simcore_service_payments.services.payments_gateway import PaymentGatewayApi


async def test_setup_payment_gateway_api(app_environment: EnvVarsDict):
    new_app = FastAPI()
    new_app.state.settings = ApplicationSettings.create_from_envs()
    with pytest.raises(AttributeError):
        PaymentGatewayApi.get_from_state(new_app)

    PaymentGatewayApi.setup(new_app)
    payment_gateway_api = PaymentGatewayApi.get_from_state(new_app)

    assert payment_gateway_api is not None


@pytest.fixture
def mock_payments_gateway_service_api(
    app: FastAPI,
    faker: Faker,
) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    with respx.mock(
        base_url=settings.PAYMENTS_GATEWAY_URL,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as respx_mock:
        # /  ---------------
        respx_mock.get(
            path="/",
            name="healthcheck",
        ).respond(status.HTTP_200_OK, text="ok")

        # /init ---------------
        def init_payment(request: httpx.Request):
            init = InitPayment.parse_raw(request.content)
            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(PaymentInitiated(payment_id=faker.uuid4())),
            )

        respx_mock.post(
            path="/init",
            name="init_payment",
        ).mock(side_effect=init_payment)

        yield respx_mock


@pytest.mark.testit
async def test_one_time_init_payment(
    app: FastAPI,
    faker: Faker,
    mock_payments_gateway_service_api: MockRouter,
):
    PaymentGatewayApi.setup(app)
    payment_gateway_api = PaymentGatewayApi.get_from_state(app)
    assert payment_gateway_api

    payment = InitPayment(
        amount_dollars=100,
        credits=100,
        user_name=faker.user_name(),
        user_email=faker.email(),
        wallet_name=faker.word(),
    )

    payment_initiated = await payment_gateway_api.init_payment(payment)

    submission_link = payment_gateway_api.get_form_payment_url(
        payment_initiated.payment_id
    )

    app_settings: ApplicationSettings = app.state.settings
    assert submission_link.host == app_settings.PAYMENTS_GATEWAY_URL.host

    #
    assert mock_payments_gateway_service_api.routes["init_payment"].called

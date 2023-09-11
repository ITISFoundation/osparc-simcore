# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from faker import Faker
from fastapi import FastAPI
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import InitPayment
from simcore_service_payments.services.payments_gateway import PaymentGatewayApi


def mock_payments_gateway_service_api():
    # respx fake interface
    ...


async def test_setup_payment_gateway_api(app_environment: EnvVarsDict):
    new_app = FastAPI()
    new_app.state.settings = ApplicationSettings.create_from_envs()
    with pytest.raises(AttributeError):
        PaymentGatewayApi.get_from_state(new_app)

    PaymentGatewayApi.setup(new_app)
    payment_gateway_api = PaymentGatewayApi.get_from_state(new_app)

    assert payment_gateway_api is not None


async def test_one_time_init_payment(app: FastAPI, faker: Faker):
    PaymentGatewayApi.setup(app)
    payment_gateway_api = PaymentGatewayApi.get_from_state(app)

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

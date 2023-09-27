# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable

import pytest
from faker import Faker
from fastapi import FastAPI, status
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from respx import MockRouter
from simcore_service_payments.core.application import create_app
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import InitPayment
from simcore_service_payments.services.payments_gateway import PaymentsGatewayApi


async def test_setup_payment_gateway_api(app_environment: EnvVarsDict):
    new_app = FastAPI()
    new_app.state.settings = ApplicationSettings.create_from_envs()
    with pytest.raises(AttributeError):
        PaymentsGatewayApi.get_from_state(new_app)

    PaymentsGatewayApi.setup(new_app)
    payment_gateway_api = PaymentsGatewayApi.get_from_state(new_app)

    assert payment_gateway_api is not None


@pytest.fixture
def app(
    disable_rabbitmq_service: Callable,
    disable_db: Callable,
    app_environment: EnvVarsDict,
):
    disable_rabbitmq_service()
    disable_db()
    return create_app()


async def test_payment_gateway_responsiveness(
    app: FastAPI,
    mock_payments_gateway_service_api_base: MockRouter,
):
    # NOTE: should be standard practice
    payment_gateway_api = PaymentsGatewayApi.get_from_state(app)
    assert payment_gateway_api

    mock_payments_gateway_service_api_base.get(
        path="/",
        name="healthcheck",
    ).respond(status.HTTP_503_SERVICE_UNAVAILABLE)

    assert await payment_gateway_api.ping()
    assert not await payment_gateway_api.is_healhy()

    mock_payments_gateway_service_api_base.get(
        path="/",
        name="healthcheck",
    ).respond(status.HTTP_200_OK)

    assert await payment_gateway_api.ping()
    assert await payment_gateway_api.is_healhy()


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/4715"
)
async def test_one_time_payment_workflow(
    app: FastAPI,
    faker: Faker,
    mock_payments_gateway_service_api_base: MockRouter,
    mock_init_payment_route: Callable,
):
    mock_init_payment_route(mock_payments_gateway_service_api_base)

    payment_gateway_api = PaymentsGatewayApi.get_from_state(app)
    assert payment_gateway_api

    # init
    payment_initiated = await payment_gateway_api.init_payment(
        payment=InitPayment(
            amount_dollars=100,
            credits=100,
            user_name=faker.user_name(),
            user_email=faker.email(),
            wallet_name=faker.word(),
        )
    )

    # form url
    submission_link = payment_gateway_api.get_form_payment_url(
        payment_initiated.payment_id
    )

    app_settings: ApplicationSettings = app.state.settings
    assert submission_link.host == app_settings.PAYMENTS_GATEWAY_URL.host

    # check mock
    assert mock_payments_gateway_service_api_base.routes["init_payment"].called

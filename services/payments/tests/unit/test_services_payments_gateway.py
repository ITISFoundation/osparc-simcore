# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable

import pytest
from faker import Faker
from fastapi import FastAPI, status
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from respx import MockRouter
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import InitPayment
from simcore_service_payments.services.payments_gateway import (
    PaymentsGatewayApi,
    setup_payments_gateway,
)


async def test_setup_payment_gateway_api(app_environment: EnvVarsDict):
    new_app = FastAPI()
    new_app.state.settings = ApplicationSettings.create_from_envs()
    with pytest.raises(AttributeError):
        PaymentsGatewayApi.get_from_app_state(new_app)

    setup_payments_gateway(new_app)
    payment_gateway_api = PaymentsGatewayApi.get_from_app_state(new_app)

    assert payment_gateway_api is not None


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    with_disabled_rabbitmq_and_rpc: None,
    with_disabled_postgres: None,
    external_secret_envs: EnvVarsDict,
):
    # set environs
    return setenvs_from_dict(
        monkeypatch,
        {**app_environment, **external_secret_envs},
    )


async def test_payment_gateway_responsiveness(
    app: FastAPI,
    mock_payments_gateway_service_api_base: MockRouter,
):
    # NOTE: should be standard practice
    payment_gateway_api = PaymentsGatewayApi.get_from_app_state(app)
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


@pytest.fixture
def mock_payments_gateway_service_or_none(
    mock_payments_gateway_service_api_base: MockRouter,
    mock_payments_routes: Callable,
    external_secret_envs: EnvVarsDict,
) -> MockRouter | None:

    # EITHER tests against external payments-gateway
    if payments_gateway_url := external_secret_envs.get("PAYMENTS_GATEWAY_URL"):
        print("🚨 EXTERNAL: these tests are running against", f"{payments_gateway_url=}")
        mock_payments_gateway_service_api_base.stop()
        return None

    # OR tests against mock payments-gateway
    mock_payments_routes(mock_payments_gateway_service_api_base)
    return mock_payments_gateway_service_api_base


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/4715"
)
async def test_one_time_payment_workflow(
    app: FastAPI,
    faker: Faker,
    mock_payments_gateway_service_or_none: MockRouter | None,
):

    payment_gateway_api = PaymentsGatewayApi.get_from_app_state(app)
    assert payment_gateway_api

    # init
    payment_initiated = await payment_gateway_api.init_payment(
        payment=InitPayment(
            amount_dollars=faker.pydecimal(
                positive=True, right_digits=2, left_digits=4
            ),
            credits_=faker.pydecimal(positive=True, right_digits=2, left_digits=4),
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

    # cancel
    await payment_gateway_api.cancel_payment(payment_initiated)

    # check mock
    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes["init_payment"].called
        assert mock_payments_gateway_service_or_none.routes["cancel_payment"].called

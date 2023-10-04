# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Callable
from pathlib import Path

import pytest
from faker import Faker
from fastapi import FastAPI, status
from pytest_simcore.helpers.utils_envs import (
    EnvVarsDict,
    load_dotenv,
    setenvs_from_dict,
)
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
        PaymentsGatewayApi.load_from_state(new_app)

    setup_payments_gateway(new_app)
    payment_gateway_api = PaymentsGatewayApi.load_from_state(new_app)

    assert payment_gateway_api is not None


@pytest.fixture
def external_secret_envs(project_tests_dir: Path) -> EnvVarsDict:
    """
    If a file under test prefixed `.env-secret` is present,
    then some mocks are disabled and real external services are used.

    This technique allows reusing the same tests to check against
    external development/production servers
    """
    envs = {}
    env_files = list(project_tests_dir.glob(".env-secret*"))
    if env_files:
        assert len(env_files) == 1
        envs = load_dotenv(env_files[0])
        assert "PAYMENTS_GATEWAY_API_SECRET" in envs
        assert "PAYMENTS_GATEWAY_URL" in envs
    return envs


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    disable_rabbitmq_and_rpc_setup: Callable,
    disable_db_setup: Callable,
    external_secret_envs: EnvVarsDict,
):
    # mocks setup
    disable_rabbitmq_and_rpc_setup()
    disable_db_setup()

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
    payment_gateway_api = PaymentsGatewayApi.load_from_state(app)
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


@pytest.mark.testit
@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/4715"
)
async def test_one_time_payment_workflow(
    app: FastAPI,
    faker: Faker,
    mock_payments_gateway_service_api_base: MockRouter,
    mock_payments_routes: Callable,
):
    mock_payments_routes(mock_payments_gateway_service_api_base)

    payment_gateway_api = PaymentsGatewayApi.load_from_state(app)
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

    # cancel
    await payment_gateway_api.cancel_payment(payment_initiated)

    # check mock
    assert mock_payments_gateway_service_api_base.routes["init_payment"].called
    assert mock_payments_gateway_service_api_base.routes["cancel_payment"].called

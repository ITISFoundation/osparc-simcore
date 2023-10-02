# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import EnvVarsDict, load_dotenv
from respx import MockRouter
from simcore_service_payments.core.application import create_app
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import (
    InitPayment,
    PaymentInitiated,
)


@pytest.fixture
def disable_rabbitmq_and_rpc_setup(mocker: MockerFixture) -> Callable:
    def _doit():
        # The following moduls are affected if rabbitmq is not in place
        mocker.patch("simcore_service_payments.core.application.setup_rabbitmq")
        mocker.patch("simcore_service_payments.core.application.setup_rpc_api_routes")

    return _doit


@pytest.fixture
def disable_db_setup(mocker: MockerFixture) -> Callable:
    def _doit():
        # The following moduls are affected if rabbitmq is not in place
        mocker.patch("simcore_service_payments.core.application.setup_db")

    return _doit


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
async def app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    test_app = create_app()
    async with LifespanManager(
        test_app,
        startup_timeout=None,  # for debugging
        shutdown_timeout=10,
    ):
        yield test_app


@pytest.fixture
def mock_payments_gateway_service_api_base(
    app: FastAPI, external_secret_envs: EnvVarsDict
) -> Iterator[MockRouter]:
    """
    If external_secret_envs is present, then this mock is not really used
    and instead the test runs against some real services
    """
    settings: ApplicationSettings = app.state.settings
    mock_base_url = settings.PAYMENTS_GATEWAY_URL

    if external_secret_envs.get("PAYMENTS_GATEWAY_URL") == mock_base_url:
        print("WARNING: Bypassing mock, and using external service at", mock_base_url)
        mock_base_url = "https://httpbin.org/"

    with respx.mock(
        base_url=mock_base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as respx_mock:
        yield respx_mock


@pytest.fixture
def mock_init_payment_route(faker: Faker) -> Callable:
    def _mock(mock_router: MockRouter):
        def _init_payment_successfully(request: httpx.Request):
            assert InitPayment.parse_raw(request.content) is not None
            assert "*" not in request.headers["X-Init-Api-Secret"]

            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(PaymentInitiated(payment_id=faker.uuid4())),
            )

        mock_router.post(
            path="/init",
            name="init_payment",
        ).mock(side_effect=_init_payment_successfully)

    return _mock

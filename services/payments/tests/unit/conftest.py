# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
import respx
import sqlalchemy as sa
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

#
# rabbit-MQ
#


@pytest.fixture
def disable_rabbitmq_and_rpc_setup(mocker: MockerFixture) -> Callable:
    def _do():
        # The following services are affected if rabbitmq is not in place
        mocker.patch("simcore_service_payments.core.application.setup_rabbitmq")
        mocker.patch("simcore_service_payments.core.application.setup_rpc_api_routes")

    return _do


@pytest.fixture
def with_disabled_rabbitmq_and_rpc(disable_rabbitmq_and_rpc_setup: Callable):
    disable_rabbitmq_and_rpc_setup()


#
# postgres
#


@pytest.fixture
def disable_postgres_setup(mocker: MockerFixture) -> Callable:
    def _setup(app: FastAPI):
        app.state.engine = (
            Mock()
        )  # NOTE: avoids error in api._dependencies::get_db_engine

    def _do():
        # The following services are affected if postgres is not in place
        mocker.patch(
            "simcore_service_payments.core.application.setup_postgres",
            spec=True,
            side_effect=_setup,
        )

    return _do


@pytest.fixture
def with_disabled_postgres(disable_postgres_setup: Callable):
    disable_postgres_setup()


@pytest.fixture
def wait_for_postgres_ready_and_db_migrated(postgres_db: sa.engine.Engine) -> None:
    """
    Typical use-case is to include it in

    @pytest.fixture
    def app_environment(
        ...
        postgres_env_vars_dict: EnvVarsDict,
        wait_for_postgres_ready_and_db_migrated: None,
    )
    """
    assert postgres_db


@pytest.fixture
async def app(app_environment: EnvVarsDict) -> AsyncIterator[FastAPI]:
    test_app = create_app()
    async with LifespanManager(
        test_app,
        startup_timeout=None,  # for debugging
        shutdown_timeout=10,
    ):
        yield test_app


#
# mock payments-gateway-service API
#


@pytest.fixture
def mock_payments_gateway_service_api_base(app: FastAPI) -> Iterator[MockRouter]:
    """
    If external_secret_envs is present, then this mock is not really used
    and instead the test runs against some real services
    """
    settings: ApplicationSettings = app.state.settings

    with respx.mock(
        base_url=settings.PAYMENTS_GATEWAY_URL,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as respx_mock:
        yield respx_mock


@pytest.fixture
def mock_payments_routes(faker: Faker) -> Callable:
    def _mock(mock_router: MockRouter):
        def _init_200(request: httpx.Request):
            assert InitPayment.parse_raw(request.content) is not None
            assert "*" not in request.headers["X-Init-Api-Secret"]

            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(PaymentInitiated(payment_id=faker.uuid4())),
            )

        def _cancel_200(request: httpx.Request):
            assert PaymentInitiated.parse_raw(request.content) is not None
            assert "*" not in request.headers["X-Init-Api-Secret"]

            return httpx.Response(status.HTTP_200_OK, json={})

        mock_router.post(
            path="/init",
            name="init_payment",
        ).mock(side_effect=_init_200)

        mock_router.post(
            path="/cancel",
            name="cancel_payment",
        ).mock(side_effect=_cancel_200)

    return _mock


@pytest.fixture
def external_secret_envs(project_tests_dir: Path) -> EnvVarsDict:
    """
    If a file under test folder prefixed with `.env-secret` is present,
    then this fixture captures it.

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

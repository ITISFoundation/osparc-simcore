# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator, Callable, Iterator

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx import MockRouter
from simcore_service_payments.core.application import create_app
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import (
    InitPayment,
    PaymentInitiated,
)


@pytest.fixture
def disable_rabbitmq_and_rpc_setup(mocker: MockerFixture) -> Callable:
    def _do():
        # The following services are affected if rabbitmq is not in place
        mocker.patch("simcore_service_payments.core.application.setup_rabbitmq")
        mocker.patch("simcore_service_payments.core.application.setup_rpc_api_routes")

    return _do


@pytest.fixture
def disable_postgres_setup(mocker: MockerFixture) -> Callable:
    def _do():
        # The following services are affected if postgres is not in place
        mocker.patch("simcore_service_payments.core.application.setup_postgres")

    return _do


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

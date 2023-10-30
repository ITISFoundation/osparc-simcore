# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import NamedTuple
from unittest.mock import Mock

import httpx
import pytest
import respx
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_webserver.wallets import PaymentMethodID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.rawdata_fakers import random_payment_method_data
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import load_dotenv
from respx import MockRouter
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_service_payments.core.application import create_app
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.models.payments_gateway import (
    BatchGetPaymentMethods,
    GetPaymentMethod,
    InitPayment,
    InitPaymentMethod,
    PaymentInitiated,
    PaymentMethodInitiated,
    PaymentMethodsBatch,
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
def payments_clean_db(postgres_db: sa.engine.Engine) -> Iterator[None]:
    with postgres_db.connect() as con:
        yield
        con.execute(payments_transactions.delete())


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
    If external_environment is present, then this mock is not really used
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

            # responds with an empty authough it can also contain a message
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
def mock_payments_methods_routes(faker: Faker) -> Iterator[Callable]:
    class PaymentMethodInfoTuple(NamedTuple):
        init: InitPaymentMethod
        get: GetPaymentMethod

    _payment_methods: dict[str, PaymentMethodInfoTuple] = {}

    def _mock(mock_router: MockRouter):
        def _init(request: httpx.Request):
            assert "*" not in request.headers["X-Init-Api-Secret"]

            pm_id = faker.uuid4()
            _payment_methods[pm_id] = PaymentMethodInfoTuple(
                init=InitPaymentMethod.parse_raw(request.content),
                get=GetPaymentMethod(**random_payment_method_data(idr=pm_id)),
            )

            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(PaymentMethodInitiated(payment_method_id=pm_id)),
            )

        def _get(request: httpx.Request, pm_id: PaymentMethodID):
            assert "*" not in request.headers["X-Init-Api-Secret"]

            try:
                _, payment_method = _payment_methods[pm_id]
                return httpx.Response(
                    status.HTTP_200_OK, json=jsonable_encoder(payment_method)
                )
            except KeyError:
                return httpx.Response(status.HTTP_404_NOT_FOUND)

        def _del(request: httpx.Request, pm_id: PaymentMethodID):
            assert "*" not in request.headers["X-Init-Api-Secret"]

            try:
                _payment_methods.pop(pm_id)
                return httpx.Response(status.HTTP_204_NO_CONTENT)
            except KeyError:
                return httpx.Response(status.HTTP_404_NOT_FOUND)

        def _batch_get(request: httpx.Request):
            assert "*" not in request.headers["X-Init-Api-Secret"]
            batch = BatchGetPaymentMethods.parse_raw(request.content)

            try:
                items = [_payment_methods[pm].get for pm in batch.payment_methods_ids]
            except KeyError:
                return httpx.Response(status.HTTP_404_NOT_FOUND)

            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(PaymentMethodsBatch(items=items)),
            )

        def _init_payment(request: httpx.Request, pm_id: PaymentMethodID):
            assert "*" not in request.headers["X-Init-Api-Secret"]
            assert InitPayment.parse_raw(request.content) is not None

            # checks
            _get(request, pm_id)

            return httpx.Response(
                status.HTTP_200_OK,
                json=jsonable_encoder(PaymentInitiated(payment_id=faker.uuid4())),
            )

        # ------

        mock_router.post(
            path="/payment-methods:init",
            name="init_payment_method",
        ).mock(side_effect=_init)

        mock_router.post(
            path="/payment-methods:batchGet",
            name="batch_get_payment_methods",
        ).mock(side_effect=_batch_get)

        mock_router.get(
            path__regex=r"/payment-methods/(?P<pm_id>[\w-]+)$",
            name="get_payment_method",
        ).mock(side_effect=_get)

        mock_router.delete(
            path__regex=r"/payment-methods/(?P<pm_id>[\w-]+)$",
            name="delete_payment_method",
        ).mock(side_effect=_del)

        mock_router.post(
            path__regex=r"/payment-methods/(?P<pm_id>[\w-]+):pay$",
            name="init_payment_with_payment_method",
        ).mock(side_effect=_init_payment)

    yield _mock

    _payment_methods.clear()


def pytest_addoption(parser: pytest.Parser):
    group = parser.getgroup(
        "external_environment",
        description="Replaces mocked services with real ones by passing actual environs and connecting directly to external services",
    )
    group.addoption(
        "--external-envfile",
        action="store",
        type=Path,
        default=None,
        help="Path to an env file. Consider passing a link to repo configs, i.e. `ln -s /path/to/osparc-ops-config/repo.config`",
    )


@pytest.fixture
def external_environment(request: pytest.FixtureRequest) -> EnvVarsDict:
    """
    If a file under test folder prefixed with `.env-secret` is present,
    then this fixture captures it.

    This technique allows reusing the same tests to check against
    external development/production servers
    """
    envs = {}
    if envfile := request.config.getoption("--external-envfile"):
        assert isinstance(envfile, Path)
        print("🚨 EXTERNAL: external envs detected. Loading", envfile, "...")
        envs = load_dotenv(envfile)
        assert "PAYMENTS_GATEWAY_API_SECRET" in envs
        assert "PAYMENTS_GATEWAY_URL" in envs

    return envs


@pytest.fixture
def mock_payments_gateway_service_or_none(
    mock_payments_gateway_service_api_base: MockRouter,
    mock_payments_routes: Callable,
    mock_payments_methods_routes: Callable,
    external_environment: EnvVarsDict,
) -> MockRouter | None:

    # EITHER tests against external payments-gateway
    if payments_gateway_url := external_environment.get("PAYMENTS_GATEWAY_URL"):
        print("🚨 EXTERNAL: these tests are running against", f"{payments_gateway_url=}")
        mock_payments_gateway_service_api_base.stop()
        return None

    # OR tests against mock payments-gateway
    mock_payments_routes(mock_payments_gateway_service_api_base)
    mock_payments_methods_routes(mock_payments_gateway_service_api_base)
    return mock_payments_gateway_service_api_base

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator, Awaitable, Callable
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_service_notifier.core.application import create_app

#
# rabbit-MQ
#


@pytest.fixture
def disable_rabbitmq_and_rpc_setup(mocker: MockerFixture) -> Callable:
    def _():
        # The following services are affected if rabbitmq is not in place
        mocker.patch("simcore_service_notifier.core.application.setup_socketio")
        mocker.patch("simcore_service_notifier.core.application.setup_rabbitmq")
        mocker.patch("simcore_service_notifier.core.application.setup_rpc_api_routes")
        mocker.patch(
            "simcore_service_notifier.core.application.setup_auto_recharge_listener"
        )

    return _


@pytest.fixture
def with_disabled_rabbitmq_and_rpc(disable_rabbitmq_and_rpc_setup: Callable):
    disable_rabbitmq_and_rpc_setup()


@pytest.fixture
async def rpc_client(
    faker: Faker, rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]]
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client(f"web-server-client-{faker.word()}")


#
# postgres
#


@pytest.fixture
def disable_postgres_setup(mocker: MockerFixture) -> Callable:
    def _setup(app: FastAPI):
        app.state.engine = (
            Mock()
        )  # NOTE: avoids error in api._dependencies::get_db_engine

    def _():
        # The following services are affected if postgres is not in place
        mocker.patch(
            "simcore_service_notifier.core.application.setup_postgres",
            spec=True,
            side_effect=_setup,
        )

    return _


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


MAX_TIME_FOR_APP_TO_STARTUP = 10
MAX_TIME_FOR_APP_TO_SHUTDOWN = 10


@pytest.fixture
async def app(
    app_environment: EnvVarsDict, is_pdb_enabled: bool
) -> AsyncIterator[FastAPI]:
    the_test_app = create_app()
    async with LifespanManager(
        the_test_app,
        startup_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_STARTUP,
        shutdown_timeout=None if is_pdb_enabled else MAX_TIME_FOR_APP_TO_SHUTDOWN,
    ):
        yield the_test_app

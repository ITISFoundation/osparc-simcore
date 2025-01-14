# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
import shutil
import stat
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from httpx._transports.asgi import ASGITransport
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.efs import AwsEfsSettings
from simcore_service_efs_guardian.core.application import create_app

#
# rabbit-MQ
#


@pytest.fixture
def disable_rabbitmq_and_rpc_setup(mocker: MockerFixture) -> Callable:
    def _():
        # The following services are affected if rabbitmq is not in place
        mocker.patch("simcore_service_efs_guardian.core.application.setup_rabbitmq")
        mocker.patch("simcore_service_efs_guardian.core.application.setup_rpc_routes")
        mocker.patch(
            "simcore_service_efs_guardian.core.application.setup_process_messages"
        )

    return _


@pytest.fixture
def with_disabled_rabbitmq_and_rpc(disable_rabbitmq_and_rpc_setup: Callable):
    disable_rabbitmq_and_rpc_setup()


@pytest.fixture
async def rpc_client(
    faker: Faker, rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]]
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client(f"director-v2-client-{faker.word()}")


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
            "simcore_service_efs_guardian.core.application.setup_db",
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


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    # - Needed for app to trigger start/stop event handlers
    # - Prefer this client instead of fastapi.testclient.TestClient
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://efs-guardian.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        assert isinstance(
            client._transport, ASGITransport  # pylint: disable=protected-access
        )
        yield client


#
# Redis
#


@pytest.fixture
def disable_redis_and_background_tasks_setup(mocker: MockerFixture) -> Callable:
    def _():
        # The following services are affected if redis is not in place
        mocker.patch("simcore_service_efs_guardian.core.application.setup_redis")
        mocker.patch(
            "simcore_service_efs_guardian.core.application.setup_background_tasks"
        )

    return _


@pytest.fixture
def with_disabled_redis_and_background_tasks(
    disable_redis_and_background_tasks_setup: Callable,
):
    disable_redis_and_background_tasks_setup()


#
# Others
#


@pytest.fixture
async def efs_cleanup(app: FastAPI):

    yield

    aws_efs_settings: AwsEfsSettings = app.state.settings.EFS_GUARDIAN_AWS_EFS_SETTINGS
    _dir_path = Path(aws_efs_settings.EFS_MOUNTED_PATH)
    if _dir_path.exists():
        for root, dirs, files in os.walk(_dir_path):
            for name in dirs + files:
                file_path = Path(root, name)
                # Get the current permissions of the file or directory
                current_permissions = Path.stat(file_path).st_mode
                # Add write permission for the owner (user)
                Path.chmod(file_path, current_permissions | stat.S_IWUSR)

        shutil.rmtree(_dir_path)

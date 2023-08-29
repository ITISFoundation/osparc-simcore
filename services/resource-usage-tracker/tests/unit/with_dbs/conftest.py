# pylint: disable=not-context-manager
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime, timezone
from typing import Any, AsyncIterable, Callable

import faker
import httpx
import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingMessageType,
    RabbitResourceTrackingStartedMessage,
)
from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from simcore_service_resource_usage_tracker.core.application import create_app
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture(scope="function")
def mock_env(monkeypatch: MonkeyPatch) -> EnvVarsDict:
    """This is the base mock envs used to configure the app.

    Do override/extend this fixture to change configurations
    """
    env_vars: EnvVarsDict = {
        "SC_BOOT_MODE": "production",
        "POSTGRES_CLIENT_NAME": "postgres_test_client",
    }
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture(scope="function")
async def initialized_app(
    mock_env: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
) -> AsyncIterable[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture(scope="function")
async def async_client(initialized_app: FastAPI) -> AsyncIterable[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=initialized_app,
        base_url="http://resource-usage-tracker.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def random_resource_tracker_service_run(faker: Faker) -> Callable[..., dict[str, Any]]:
    def _creator(**overrides) -> dict[str, Any]:
        data = dict(
            product_name="osparc",
            service_run_id=faker.uuid4(),
            wallet_id=faker.pyint(),
            wallet_name=faker.word(),
            pricing_plan_id=faker.pyint(),
            pricing_detail_id=faker.pyint(),
            simcore_user_agent=faker.word(),
            user_id=faker.pyint(),
            user_email=faker.email(),
            project_id=faker.uuid4(),
            project_name=faker.word(),
            node_id=faker.uuid4(),
            node_name=faker.word(),
            service_key="simcore/services/dynamic/jupyter-smash",
            service_version="3.0.7",
            service_type="DYNAMIC_SERVICE",
            service_resources={},
            service_additional_metadata={},
            started_at=datetime.now(tz=timezone.utc),
            stopped_at=None,
            service_run_status="RUNNING",
            modified=datetime.now(tz=timezone.utc),
            last_heartbeat_at=datetime.now(tz=timezone.utc),
        )
        data.update(overrides)
        return data

    return _creator


@pytest.fixture()
def resource_tracker_service_run_db(postgres_db: sa.engine.Engine):
    with postgres_db.connect() as con:
        # removes all service runs before continuing
        con.execute(resource_tracker_service_runs.delete())
        yield
        con.execute(resource_tracker_service_runs.delete())


async def assert_service_runs_db_row(
    postgres_db, service_run_id: str, status: str | None = None
) -> dict | None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.2),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            with postgres_db.connect() as con:
                # removes all projects before continuing
                con.execute(resource_tracker_service_runs.select())
                result = con.execute(
                    sa.select(resource_tracker_service_runs).where(
                        resource_tracker_service_runs.c.service_run_id == service_run_id
                    )
                )
                row: dict | None = result.first()
                assert row
                if status:
                    assert row[21] == status
                return row


@pytest.fixture
def random_rabbit_message_heartbeat(
    faker: Faker,
) -> Callable[..., RabbitResourceTrackingHeartbeatMessage]:
    def _creator(**kwargs: dict[str, Any]) -> RabbitResourceTrackingHeartbeatMessage:
        msg_config = {"service_run_id": faker.uuid4(), **kwargs}

        return RabbitResourceTrackingHeartbeatMessage(**msg_config)

    return _creator


@pytest.fixture
def random_rabbit_message_start(
    faker: Faker,
) -> Callable[..., RabbitResourceTrackingStartedMessage]:
    def _creator(**kwargs: dict[str, Any]) -> RabbitResourceTrackingStartedMessage:
        msg_config = {
            "channel_name": "io.simcore.service.tracking",
            "service_run_id": faker.uuid4(),
            "created_at": datetime.now(timezone.utc),
            "message_type": RabbitResourceTrackingMessageType.TRACKING_STARTED,
            "wallet_id": faker.pyint(),
            "wallet_name": faker.pystr(),
            "pricing_plan_id": faker.pyint(),
            "pricing_detail_id": faker.pyint(),
            "product_name": "osparc",
            "simcore_user_agent": faker.pystr(),
            "user_id": faker.pyint(),
            "user_email": faker.email(),
            "project_id": faker.uuid4(),
            "project_name": faker.pystr(),
            "node_id": faker.uuid4(),
            "node_name": faker.pystr(),
            "service_key": "simcore/services/comp/itis/sleeper",
            "service_version": "2.1.6",
            "service_type": "computational",
            "service_resources": {
                "container": {
                    "image": "simcore/services/comp/itis/sleeper:2.1.6",
                    "resources": {
                        "CPU": {"limit": 0.1, "reservation": 0.1},
                        "RAM": {"limit": 134217728, "reservation": 134217728},
                    },
                    "boot_modes": ["CPU"],
                }
            },
            "service_additional_metadata": {},
            **kwargs,
        }

        return RabbitResourceTrackingStartedMessage(**msg_config)

    return _creator

# pylint: disable=not-context-manager
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterable, Callable
from datetime import datetime, timezone
from random import choice
from typing import Any, Awaitable

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
from pydantic import TypeAdapter
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.rabbitmq import RabbitMQRPCClient
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from simcore_service_resource_usage_tracker.core.application import create_app
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings
from simcore_service_resource_usage_tracker.models.credit_transactions import (
    CreditTransactionDB,
)
from simcore_service_resource_usage_tracker.models.service_runs import ServiceRunDB
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed


@pytest.fixture()
def mock_env(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    """This is the base mock envs used to configure the app.

    Do override/extend this fixture to change configurations
    """
    env_vars: EnvVarsDict = {
        "SC_BOOT_MODE": "production",
        "POSTGRES_CLIENT_NAME": "postgres_test_client",
        "RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_CHECK_ENABLED": "0",
        "RESOURCE_USAGE_TRACKER_TRACING": "null",
    }
    setenvs_from_dict(monkeypatch, env_vars)
    return env_vars


@pytest.fixture()
async def initialized_app(
    mock_env: EnvVarsDict,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
) -> AsyncIterable[FastAPI]:
    settings = ApplicationSettings.create_from_envs()
    app = create_app(settings)
    async with LifespanManager(app):
        yield app


@pytest.fixture()
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
        data = {
            "product_name": "osparc",
            "service_run_id": faker.uuid4(),
            "wallet_id": faker.pyint(),
            "wallet_name": faker.word(),
            "pricing_plan_id": faker.pyint(),
            "pricing_unit_id": faker.pyint(),
            "pricing_unit_cost_id": faker.pyint(),
            "simcore_user_agent": faker.word(),
            "user_id": faker.pyint(),
            "user_email": faker.email(),
            "project_id": faker.uuid4(),
            "project_name": faker.word(),
            "node_id": faker.uuid4(),
            "node_name": faker.word(),
            "parent_project_id": faker.uuid4(),
            "root_parent_project_id": faker.uuid4(),
            "root_parent_project_name": faker.pystr(),
            "parent_node_id": faker.uuid4(),
            "root_parent_node_id": faker.uuid4(),
            "service_key": "simcore/services/dynamic/jupyter-smash",
            "service_version": "3.0.7",
            "service_type": "DYNAMIC_SERVICE",
            "service_resources": {},
            "service_additional_metadata": {},
            "started_at": datetime.now(tz=timezone.utc),
            "stopped_at": None,
            "service_run_status": "RUNNING",
            "modified": datetime.now(tz=timezone.utc),
            "last_heartbeat_at": datetime.now(tz=timezone.utc),
            "pricing_unit_cost": abs(faker.pyfloat()),
        }
        data.update(overrides)
        return data

    return _creator


@pytest.fixture
def random_resource_tracker_credit_transactions(
    faker: Faker,
) -> Callable[..., dict[str, Any]]:
    def _creator(**overrides) -> dict[str, Any]:
        data = {
            "product_name": "osparc",
            "wallet_id": faker.pyint(),
            "wallet_name": faker.word(),
            "pricing_plan_id": faker.pyint(),
            "pricing_unit_id": faker.pyint(),
            "pricing_unit_cost_id": faker.pyint(),
            "user_id": faker.pyint(),
            "user_email": faker.email(),
            "osparc_credits": -abs(faker.pyfloat()),
            "transaction_status": choice(["BILLED", "PENDING", "NOT_BILLED"]),
            "transaction_classification": "DEDUCT_SERVICE_RUN",
            "service_run_id": faker.uuid4(),
            "payment_transaction_id": faker.uuid4(),
            "created": datetime.now(tz=timezone.utc),
            "last_heartbeat_at": datetime.now(tz=timezone.utc),
            "modified": datetime.now(tz=timezone.utc),
        }
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
) -> ServiceRunDB:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.2),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt, postgres_db.connect() as con:
            result = con.execute(
                sa.select(resource_tracker_service_runs).where(
                    resource_tracker_service_runs.c.service_run_id == service_run_id
                )
            )
            row = result.first()
            assert row
            service_run_db = ServiceRunDB.model_validate(row)
            if status:
                assert service_run_db.service_run_status == status
            return service_run_db
    raise ValueError


async def assert_credit_transactions_db_row(
    postgres_db, service_run_id: str, modified_at: datetime | None = None
) -> CreditTransactionDB:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.2),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt, postgres_db.connect() as con:
            result = con.execute(
                sa.select(resource_tracker_credit_transactions).where(
                    resource_tracker_credit_transactions.c.service_run_id
                    == service_run_id
                )
            )
            row = result.first()
            assert row
            credit_transaction_db = CreditTransactionDB.model_validate(row)
            if modified_at:
                assert credit_transaction_db.modified > modified_at
            return credit_transaction_db
    raise ValueError


@pytest.fixture
def random_rabbit_message_heartbeat(
    faker: Faker,
) -> Callable[..., RabbitResourceTrackingHeartbeatMessage]:
    def _creator(**kwargs: dict[str, Any]) -> RabbitResourceTrackingHeartbeatMessage:
        msg_config = {"service_run_id": faker.uuid4(), **kwargs}

        return TypeAdapter(RabbitResourceTrackingHeartbeatMessage).validate_python(
            msg_config
        )

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
            "pricing_unit_id": faker.pyint(),
            "pricing_unit_cost_id": faker.pyint(),
            "product_name": "osparc",
            "simcore_user_agent": faker.pystr(),
            "user_id": faker.pyint(),
            "user_email": faker.email(),
            "project_id": faker.uuid4(),
            "project_name": faker.pystr(),
            "node_id": faker.uuid4(),
            "node_name": faker.pystr(),
            "parent_project_id": faker.uuid4(),
            "root_parent_project_id": faker.uuid4(),
            "root_parent_project_name": faker.pystr(),
            "parent_node_id": faker.uuid4(),
            "root_parent_node_id": faker.uuid4(),
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

        return TypeAdapter(RabbitResourceTrackingStartedMessage).validate_python(
            msg_config
        )

    return _creator


@pytest.fixture
async def rpc_client(
    rabbit_service: RabbitSettings,
    initialized_app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")

# pylint:disable=contextmanager-generator-missing-cleanup
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import (
    PostgresTestConfig,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.services.base_repository import (
    get_repository,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._models import StepId, StepState
from simcore_service_dynamic_scheduler.services.p_scheduler._repositories import StepFailHistoryRepository
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    disable_generic_scheduler_lifespan: None,
    postgres_db: sa.engine.Engine,
    postgres_host_config: PostgresTestConfig,
    disable_rabbitmq_lifespan: None,
    disable_redis_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    disable_p_scheduler_lifespan: None,
    monkeypatch: pytest.MonkeyPatch,
) -> EnvVarsDict:
    setenvs_from_dict(
        monkeypatch,
        {
            "POSTGRES_CLIENT_NAME": "test_postgres_client",
        },
    )
    return app_environment


@pytest.fixture
def engine(app: FastAPI) -> AsyncEngine:
    assert isinstance(app.state.engine, AsyncEngine)
    return app.state.engine


@pytest.fixture()
def step_fail_history_repo(app: FastAPI) -> StepFailHistoryRepository:
    return get_repository(app, StepFailHistoryRepository)


async def test_insert_step_fail_history(
    engine: AsyncEngine, step_fail_history_repo: StepFailHistoryRepository, step_id: StepId
) -> None:
    await step_fail_history_repo.insert_step_fail_history(
        step_id=step_id,
        attempt=1,
        state=StepState.FAILED,
        finished_at=datetime.now(tz=UTC),
        message="test message",
    )
    step_fail_history = await step_fail_history_repo.get_step_fail_history(step_id)
    assert len(step_fail_history) == 1
    step_fail = step_fail_history[0]
    assert step_fail.step_id == step_id
    assert step_fail.attempt == 1
    assert step_fail.state == StepState.FAILED
    assert step_fail.message == "test message"

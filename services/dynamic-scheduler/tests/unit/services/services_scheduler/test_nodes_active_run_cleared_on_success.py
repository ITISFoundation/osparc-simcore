# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import PostgresTestConfig
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.base import metadata as pg_metadata
from simcore_postgres_database.models.dynamic_services_scheduler import (
    dynamic_services_scheduler_nodes,
    dynamic_services_scheduler_runs,
    dynamic_services_scheduler_step_deps,
    dynamic_services_scheduler_step_executions,
)
from simcore_service_dynamic_scheduler.services.services_scheduler.models import (
    DagTemplate,
    DbDesiredState,
    DbDirection,
    DbRunKind,
    DbRunState,
    DbStepState,
)
from simcore_service_dynamic_scheduler.services.services_scheduler.repository import (
    ServicesSchedulerRepository,
)
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


@pytest.fixture
def ensure_services_scheduler_tables(postgres_db: sa.engine.Engine) -> None:
    with postgres_db.begin() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS dynamic_services_scheduler_step_deps CASCADE"))
        conn.execute(sa.text("DROP TABLE IF EXISTS dynamic_services_scheduler_step_executions CASCADE"))
        conn.execute(sa.text("DROP TABLE IF EXISTS dynamic_services_scheduler_runs CASCADE"))
        conn.execute(sa.text("DROP TABLE IF EXISTS dynamic_services_scheduler_nodes CASCADE"))

    pg_metadata.create_all(
        postgres_db,
        tables=[
            dynamic_services_scheduler_nodes,
            dynamic_services_scheduler_runs,
            dynamic_services_scheduler_step_executions,
            dynamic_services_scheduler_step_deps,
        ],
        checkfirst=True,
    )


@pytest.fixture
def repo(engine: AsyncEngine) -> ServicesSchedulerRepository:
    return ServicesSchedulerRepository(engine)


@pytest.fixture
def node_id() -> NodeID:
    return uuid4()


async def test_active_run_cleared_when_run_finishes(
    repo: ServicesSchedulerRepository,
    node_id: NodeID,
    ensure_services_scheduler_tables: None,
    engine: AsyncEngine,
):
    async with engine.begin() as conn:
        await repo.lock_node(node_id, connection=conn)
        generation = await repo.set_node_desired(
            node_id=node_id,
            desired_state=DbDesiredState.PRESENT,
            desired_spec={},
            connection=conn,
        )
        run_id = await repo.create_run(
            node_id=node_id,
            generation=generation,
            kind=DbRunKind.APPLY,
            connection=conn,
        )
        await repo.set_active_run(node_id=node_id, run_id=run_id, connection=conn)

        template = DagTemplate(workflow_id="wf", nodes={"s1"}, edges=set())
        await repo.insert_steps(run_id=run_id, direction=DbDirection.DO, template=template, connection=conn)
        await repo.insert_deps(run_id=run_id, direction=DbDirection.DO, template=template, connection=conn)

    claim = await repo.claim_one_step(worker_id="w1")
    assert claim is not None

    await repo.mark_step_succeeded(claim=claim)
    finalized = await repo.try_finalize_run(run_id=run_id)
    assert finalized is True

    async with engine.connect() as conn:
        node_row = (
            await conn.execute(
                sa.select(dynamic_services_scheduler_nodes.c.active_run_id).where(
                    dynamic_services_scheduler_nodes.c.node_id == f"{node_id}"
                )
            )
        ).one()
        assert node_row.active_run_id is None

        run_row = (
            await conn.execute(
                sa.select(dynamic_services_scheduler_runs.c.state).where(
                    dynamic_services_scheduler_runs.c.run_id == run_id
                )
            )
        ).one()
        # SQLAlchemy returns the Python Enum associated with the DB column type.
        # Assert by Enum value to avoid Enum-class mismatches.
        state_value = getattr(run_row.state, "value", run_row.state)
        assert state_value == DbRunState.SUCCEEDED.value


@pytest.mark.parametrize(
    "final_step_state",
    [DbStepState.WAITING_MANUAL, DbStepState.ABANDONED],
)
async def test_run_has_problems_when_step_not_ok(
    repo: ServicesSchedulerRepository,
    node_id: NodeID,
    ensure_services_scheduler_tables: None,
    engine: AsyncEngine,
    final_step_state: DbStepState,
):
    async with engine.begin() as conn:
        await repo.lock_node(node_id, connection=conn)
        generation = await repo.set_node_desired(
            node_id=node_id,
            desired_state=DbDesiredState.PRESENT,
            desired_spec={},
            connection=conn,
        )
        run_id = await repo.create_run(
            node_id=node_id,
            generation=generation,
            kind=DbRunKind.APPLY,
            connection=conn,
        )

        template = DagTemplate(workflow_id="wf", nodes={"s1"}, edges=set())
        await repo.insert_steps(run_id=run_id, direction=DbDirection.DO, template=template, connection=conn)
        await repo.insert_deps(run_id=run_id, direction=DbDirection.DO, template=template, connection=conn)

    claim = await repo.claim_one_step(worker_id="w1")
    assert claim is not None

    if final_step_state is DbStepState.WAITING_MANUAL:
        await repo.mark_step_waiting_manual(claim=claim, error="boom")
    else:
        await repo.mark_step_abandoned(claim=claim, error="boom")

    assert await repo.run_has_problems(run_id=run_id) is True

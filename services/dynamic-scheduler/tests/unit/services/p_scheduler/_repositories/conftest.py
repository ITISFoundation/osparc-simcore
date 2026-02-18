# pylint:disable=contextmanager-generator-missing-cleanup
# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from faker import Faker
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.faker_factories import random_ps_run, random_ps_step
from pytest_simcore.helpers.postgres_tools import (
    insert_and_get_row_lifespan,
)
from simcore_postgres_database.models.p_scheduler import ps_runs, ps_steps
from simcore_service_dynamic_scheduler.services.p_scheduler._models import Run, RunId, Step, StepId
from sqlalchemy.ext.asyncio import AsyncEngine

### Run ###


@pytest.fixture
def random_ps_run_data(faker: Faker) -> dict[str, Any]:
    return random_ps_run(fake=faker)


@pytest.fixture
async def ps_run_in_db(engine: AsyncEngine, random_ps_run_data: dict[str, Any]) -> AsyncIterator[Run]:
    async with insert_and_get_row_lifespan(
        engine,
        table=ps_runs,
        values=random_ps_run_data,
        pk_col=ps_runs.c.run_id,
        pk_value=random_ps_run_data["run_id"],
    ) as row:
        yield Run(**row)


@pytest.fixture
async def auto_remove_ps_runs(engine: AsyncEngine) -> AsyncIterator[Callable[[Run | RunId], None]]:
    run_ids_to_remove: list[Run | RunId] = []

    def _(run_id: Run | RunId) -> None:
        if isinstance(run_id, Run):
            run_ids_to_remove.append(run_id.run_id)
        else:
            run_ids_to_remove.append(run_id)

    yield _

    async with engine.begin() as conn:
        await conn.execute(ps_runs.delete().where(ps_runs.c.run_id.in_(run_ids_to_remove)))


@pytest.fixture
def node_id(ps_run_in_db: Run) -> NodeID:
    return ps_run_in_db.node_id


@pytest.fixture
def run_id(ps_run_in_db: Run) -> RunId:
    return ps_run_in_db.run_id


@pytest.fixture
def missing_run_id() -> RunId:
    return -42


@pytest.fixture
def missing_node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


### Step ###


@pytest.fixture
async def random_ps_step_data(faker: Faker, ps_run_in_db: Run) -> dict[str, Any]:
    return random_ps_step(ps_run_in_db.run_id, fake=faker)


@pytest.fixture
async def ps_step_in_db(engine: AsyncEngine, random_ps_step_data: dict[str, Any]) -> AsyncIterator[Step]:
    async with insert_and_get_row_lifespan(
        engine,
        table=ps_steps,
        values=random_ps_step_data,
        pk_col=ps_steps.c.step_id,
        pk_value=random_ps_step_data["step_id"],
    ) as row:
        yield Step(**row)


@pytest.fixture
def step_id(ps_step_in_db: Step) -> StepId:
    return ps_step_in_db.step_id

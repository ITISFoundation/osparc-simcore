# pylint:disable=contextmanager-generator-missing-cleanup
# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
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
async def create_run_in_db(engine: AsyncEngine, faker: Faker) -> AsyncIterator[Callable[..., Awaitable[Run]]]:
    exit_stack = AsyncExitStack()

    async def _create(**overrides: Any) -> Run:
        data = random_ps_run(fake=faker) | overrides
        row = await exit_stack.enter_async_context(
            insert_and_get_row_lifespan(
                engine,
                table=ps_runs,
                values=data,
                pk_col=ps_runs.c.run_id,
                pk_value=data["run_id"],
            )
        )
        return Run(**row)

    yield _create

    await exit_stack.aclose()


@pytest.fixture
async def run_in_db(create_run_in_db: Callable[..., Awaitable[Run]]) -> Run:
    return await create_run_in_db()


@pytest.fixture
def node_id(run_in_db: Run) -> NodeID:
    return run_in_db.node_id


@pytest.fixture
def run_id(run_in_db: Run) -> RunId:
    return run_in_db.run_id


@pytest.fixture
def missing_run_id() -> RunId:
    return -42


@pytest.fixture
def missing_node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


### Step ###


@pytest.fixture
async def create_step_in_db(
    engine: AsyncEngine, faker: Faker, run_in_db: Run
) -> AsyncIterator[Callable[..., Awaitable[Step]]]:
    exit_stack = AsyncExitStack()

    async def _create(**overrides: Any) -> Step:
        data = random_ps_step(run_in_db.run_id, fake=faker) | overrides
        row = await exit_stack.enter_async_context(
            insert_and_get_row_lifespan(
                engine,
                table=ps_steps,
                values=data,
                pk_col=ps_steps.c.step_id,
                pk_value=data["step_id"],
            )
        )
        return Step(**row)

    yield _create

    await exit_stack.aclose()


@pytest.fixture
async def steo_in_db(create_step_in_db: Callable[..., Awaitable[Step]]) -> Step:
    return await create_step_in_db()


@pytest.fixture
async def step_id(steo_in_db: Step) -> StepId:
    return steo_in_db.step_id


@pytest.fixture
def missing_step_id() -> StepId:
    return -42

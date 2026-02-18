# pylint:disable=contextmanager-generator-missing-cleanup
# pylint: disable=redefined-outer-name

from collections.abc import AsyncIterator
from typing import Any

import pytest
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_ps_run
from pytest_simcore.helpers.postgres_tools import (
    insert_and_get_row_lifespan,
)
from simcore_postgres_database.models.p_scheduler import ps_runs
from simcore_service_dynamic_scheduler.services.p_scheduler._models import Run, RunId
from sqlalchemy.ext.asyncio import AsyncEngine


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
def run_id(ps_run_in_db: Run) -> RunId:
    return ps_run_in_db.run_id


@pytest.fixture
def missing_run_id() -> RunId:
    return -42

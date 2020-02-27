# pylint:disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=wildcard-import

import json
import random
from datetime import datetime
from typing import Dict
from uuid import uuid4

import faker
import pytest
import sqlalchemy as sa

# from aiopg.sa.result import ResultProxy, RowProxy
from psycopg2.errors import UniqueViolation  # pylint: disable=no-name-in-module

from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.models.comp_pipeline import (
    FAILED,
    PENDING,
    RUNNING,
    SUCCESS,
    UNKNOWN,
)
from simcore_postgres_database.webserver_models import comp_pipeline, comp_tasks

fake = faker.Faker()

STATES = [UNKNOWN, PENDING, RUNNING, SUCCESS, FAILED]


def fake_pipeline(**overrides) -> Dict:
    data = dict(dag_adjacency_list=json.dumps({}), state=random.choice(STATES),)
    data.update(overrides)
    return data


def fake_task(**overrides) -> Dict:
    data = dict(
        project_id=uuid4(),
        node_id=uuid4(),
        job_id=uuid4(),
        internal_id=1,  # TODO: incremental
        schema=json.dumps({}),
        inputs=json.dumps({}),
        outputs=json.dumps({}),
        image=json.dumps({}),
        state=random.choice(STATES),
        submit=datetime.utcnow(),
        start=datetime.utcnow(),
        end=datetime.utcnow(),
    )
    # TODO: state and times must be logic submit < start and end
    data.update(overrides)
    return data


@pytest.fixture
def engine(make_engine, loop):
    async def start():
        engine = await make_engine()
        sync_engine = make_engine(False)
        metadata.drop_all(sync_engine)
        metadata.create_all(sync_engine)

        async with engine.acquire() as conn:
            await conn.execute(
                comp_pipeline.insert().values(**fake_pipeline(project_id="PA"))
            )
            await conn.execute(
                comp_pipeline.insert().values(**fake_pipeline(project_id="PB"))
            )

        return engine

    return loop.run_until_complete(start())


async def test_unique_project_node_pairs(engine):

    async with engine.acquire() as conn:

        task_id = await conn.scalar(
            comp_tasks.insert().values(**fake_task(project_id="PA", node_id="N1"))
        )
        assert task_id == 1

        assert (
            await conn.scalar(
                comp_tasks.insert().values(**fake_task(project_id="PA", node_id="N2"))
            )
            == 2
        )

        assert (
            await conn.scalar(
                comp_tasks.insert().values(**fake_task(project_id="PB", node_id="N2"))
            )
            == 3
        )

        task_inputs = await conn.scalar(
            sa.select([comp_tasks.c.inputs]).where(
                sa.and_(comp_tasks.c.project_id == "PB", comp_tasks.c.node_id == "N2",)
            )
        )
        assert json.loads(task_inputs) == {}

        with pytest.raises(UniqueViolation, match="project_node_uniqueness"):
            #
            # psycopg2.errors.UniqueViolation:
            #   duplicate key value violates unique constraint "project_node_uniqueness" ...
            #
            await conn.execute(
                comp_tasks.insert().values(**fake_task(project_id="PA", node_id="N1"))
            )

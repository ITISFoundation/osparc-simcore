# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import AsyncIterator, Awaitable, Callable, Iterator, Optional, Union

import aiopg.sa
import aiopg.sa.exc
import pytest
import sqlalchemy as sa
import yaml
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from pytest_simcore.helpers.rawdata_fakers import random_group, random_user
from simcore_postgres_database.webserver_models import (
    GroupType,
    groups,
    user_to_groups,
    users,
)
from sqlalchemy import literal_column

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.pytest_global_environs",
]


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip, docker_compose_file) -> str:
    # container environment
    with open(docker_compose_file) as fh:
        config = yaml.safe_load(fh)
    environ = config["services"]["postgres"]["environment"]

    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        user=environ["POSTGRES_USER"],
        password=environ["POSTGRES_PASSWORD"],
        host=docker_ip,
        port=docker_services.port_for("postgres", 5432),
        database=environ["POSTGRES_DB"],
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_postgres_responsive(dsn),
        timeout=30.0,
        pause=0.1,
    )
    return dsn


@pytest.fixture
def make_engine(
    postgres_service: str,
) -> Callable[[bool], Union[Awaitable[Engine], sa.engine.base.Engine]]:
    dsn = postgres_service

    def maker(*, is_async=True) -> Union[Awaitable[Engine], sa.engine.base.Engine]:
        engine = aiopg.sa.create_engine(dsn) if is_async else sa.create_engine(dsn)
        return engine

    return maker


def is_postgres_responsive(dsn) -> bool:
    """Check if something responds to ``url``"""
    try:
        engine = sa.create_engine(dsn)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True


@pytest.fixture(scope="session")
def db_metadata():
    from simcore_postgres_database.models.base import metadata

    return metadata


@pytest.fixture
async def pg_engine(make_engine: Callable, db_metadata) -> AsyncIterator[Engine]:
    async_engine = await make_engine(is_async=True)

    # NOTE: Using migration to upgrade/downgrade is not
    # such a great idea since these tests are used while developing
    # the tables, i.e. when no migration mechanism are in place
    # Best is therefore to start from scratch and delete all at
    # the end
    sync_engine = make_engine(is_async=False)

    # NOTE: ALL is deleted before
    db_metadata.drop_all(sync_engine)
    db_metadata.create_all(sync_engine)

    yield async_engine

    # closes async-engine connections and terminates
    async_engine.close()
    await async_engine.wait_closed()
    async_engine.terminate()

    # NOTE: ALL is deleted after
    db_metadata.drop_all(sync_engine)
    sync_engine.dispose()


#
# FACTORY FIXTURES
#


@pytest.fixture
def create_fake_group(
    make_engine: Callable[[bool], Union[Awaitable[Engine], sa.engine.base.Engine]]
) -> Iterator[Callable]:
    """factory to create standard group"""
    created_ids = []

    async def _create_group(conn: SAConnection, **overrides) -> RowProxy:
        result: ResultProxy = await conn.execute(
            groups.insert()
            .values(**random_group(type=GroupType.STANDARD, **overrides))
            .returning(literal_column("*"))
        )
        group = await result.fetchone()
        assert group
        created_ids.append(group.gid)
        return group

    yield _create_group

    sync_engine = make_engine(is_async=False)
    sync_engine.execute(groups.delete().where(groups.c.gid.in_(created_ids)))


@pytest.fixture
def create_fake_user(
    make_engine: Callable[[bool], Union[Awaitable[Engine], sa.engine.base.Engine]]
) -> Iterator[Callable]:
    """factory to create a user w/ or w/o a standard group"""

    created_ids = []

    async def _create_user(
        conn, group: Optional[RowProxy] = None, **overrides
    ) -> RowProxy:
        user_id = await conn.scalar(
            users.insert().values(**random_user(**overrides)).returning(users.c.id)
        )
        assert user_id is not None

        # This is done in two executions instead of one (e.g. returning(literal_column("*")) )
        # to allow triggering function in db that
        # insert primary_gid column
        r = await conn.execute(users.select().where(users.c.id == user_id))
        assert r.rowcount == 1
        user = await r.first()
        assert user

        created_ids.append(user.id)

        if group:
            assert group.type == GroupType.STANDARD.name
            result = await conn.execute(
                user_to_groups.insert().values(uid=user.id, gid=group.gid)
            )
            assert result
        return user

    yield _create_user

    sync_engine = make_engine(is_async=False)
    sync_engine.execute(users.delete().where(users.c.id.in_(created_ids)))

# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import AsyncIterator, Awaitable, Callable, Iterator

import aiopg.sa
import aiopg.sa.exc
import pytest
import simcore_postgres_database.cli
import sqlalchemy as sa
import yaml
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from faker import Faker
from pytest_simcore.helpers.rawdata_fakers import (
    random_group,
    random_project,
    random_user,
)
from simcore_postgres_database.models.cluster_to_groups import cluster_to_groups
from simcore_postgres_database.models.clusters import ClusterType, clusters
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.webserver_models import (
    GroupType,
    groups,
    user_to_groups,
    users,
)

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.pytest_global_environs",
]


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip, docker_compose_file) -> str:
    """Deploys postgres and service is responsive"""
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
) -> Callable[[bool], Awaitable[Engine] | sa.engine.base.Engine]:
    dsn = postgres_service

    def _make(is_async=True) -> Awaitable[Engine] | sa.engine.base.Engine:
        engine = aiopg.sa.create_engine(dsn) if is_async else sa.create_engine(dsn)
        return engine

    return _make


def is_postgres_responsive(dsn) -> bool:
    """Check if something responds to ``url``"""
    try:
        engine = sa.create_engine(dsn)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:  # type: ignore
        return False
    return True


@pytest.fixture(scope="session")
def db_metadata() -> sa.MetaData:
    from simcore_postgres_database.models.base import metadata

    return metadata


@pytest.fixture(params=["sqlModels", "alembicMigration"])
def pg_sa_engine(
    make_engine: Callable,
    db_metadata: sa.MetaData,
    request: pytest.FixtureRequest,
) -> Iterator[sa.engine.Engine]:
    """
    Runs migration to create tables and return a sqlalchemy engine
    """
    # NOTE: Using migration to upgrade/downgrade is not
    # such a great idea since these tests are used while developing
    # the tables, i.e. when no migration mechanism are in place
    # Best is therefore to start from scratch and delete all at
    # the end
    sync_engine = make_engine(is_async=False)

    # NOTE: ALL is deleted before
    db_metadata.drop_all(sync_engine)
    if request.param == "sqlModels":
        db_metadata.create_all(sync_engine)
    else:
        assert simcore_postgres_database.cli.discover.callback
        assert simcore_postgres_database.cli.upgrade.callback
        dsn = sync_engine.url
        simcore_postgres_database.cli.discover.callback(
            user=dsn.username,
            password=dsn.password,
            host=dsn.host,
            database=dsn.database,
            port=dsn.port,
        )
        simcore_postgres_database.cli.upgrade.callback("head")

    yield sync_engine

    # NOTE: ALL is deleted after
    with sync_engine.begin() as conn:
        conn.execute(sa.DDL("DROP TABLE IF EXISTS alembic_version"))
    db_metadata.drop_all(sync_engine)
    sync_engine.dispose()


@pytest.fixture
async def pg_engine(
    pg_sa_engine: sa.engine.Engine, make_engine: Callable
) -> AsyncIterator[Engine]:
    """
    Return an aiopg.sa engine connected to a responsive and migrated pg database
    """
    async_engine = await make_engine(is_async=True)

    yield async_engine

    # closes async-engine connections and terminates
    async_engine.close()
    await async_engine.wait_closed()
    async_engine.terminate()


@pytest.fixture
async def connection(pg_engine: Engine) -> AsyncIterator[SAConnection]:
    """Returns an aiopg.sa connection from an engine to a fully furnished and ready pg database"""
    async with pg_engine.acquire() as _conn:
        yield _conn


#
# FACTORY FIXTURES
#


@pytest.fixture
def create_fake_group(
    make_engine: Callable[..., Awaitable[Engine] | sa.engine.base.Engine]
) -> Iterator[Callable]:
    """factory to create standard group"""
    created_ids = []

    async def _creator(conn: SAConnection, **overrides) -> RowProxy:
        result: ResultProxy = await conn.execute(
            groups.insert()
            .values(**random_group(type=GroupType.STANDARD, **overrides))
            .returning(sa.literal_column("*"))
        )
        group = await result.fetchone()
        assert group
        created_ids.append(group.gid)
        return group

    yield _creator

    sync_engine = make_engine(is_async=False)
    assert isinstance(sync_engine, sa.engine.Engine)
    with sync_engine.begin() as conn:
        conn.execute(sa.delete(groups).where(groups.c.gid.in_(created_ids)))


@pytest.fixture
def create_fake_user(
    make_engine: Callable[..., Awaitable[Engine] | sa.engine.base.Engine]
) -> Iterator[Callable]:
    """factory to create a user w/ or w/o a standard group"""

    created_ids = []

    async def _creator(conn, group: RowProxy | None = None, **overrides) -> RowProxy:
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

    yield _creator

    sync_engine = make_engine(is_async=False)
    assert isinstance(sync_engine, sa.engine.Engine)
    with sync_engine.begin() as conn:
        conn.execute(users.delete().where(users.c.id.in_(created_ids)))


@pytest.fixture
async def create_fake_cluster(
    pg_engine: Engine, faker: Faker
) -> AsyncIterator[Callable[..., Awaitable[int]]]:
    cluster_ids = []
    assert cluster_to_groups is not None

    async def _creator(**overrides) -> int:
        insert_values = {
            "name": "default cluster name",
            "type": ClusterType.ON_PREMISE,
            "description": None,
            "endpoint": faker.domain_name(),
            "authentication": faker.pydict(value_types=[str]),
        }
        insert_values.update(overrides)
        async with pg_engine.acquire() as conn:
            cluster_id = await conn.scalar(
                clusters.insert().values(**insert_values).returning(clusters.c.id)
            )
        cluster_ids.append(cluster_id)
        assert cluster_id
        return cluster_id

    yield _creator

    # cleanup
    async with pg_engine.acquire() as conn:
        await conn.execute(clusters.delete().where(clusters.c.id.in_(cluster_ids)))


@pytest.fixture
async def create_fake_project(pg_engine: Engine) -> AsyncIterator[Callable]:
    created_project_uuids = []

    async def _creator(conn, user: RowProxy, **overrides) -> RowProxy:
        prj_to_insert = random_project(prj_owner=user.id, **overrides)
        result = await conn.execute(
            projects.insert().values(**prj_to_insert).returning(projects)
        )
        assert result
        new_project = await result.first()
        assert new_project
        created_project_uuids.append(new_project.uuid)
        return new_project

    yield _creator

    async with pg_engine.acquire() as conn:
        await conn.execute(
            projects.delete().where(projects.c.uuid.in_(created_project_uuids))
        )

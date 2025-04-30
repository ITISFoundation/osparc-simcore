# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import uuid
import warnings
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Iterator
from pathlib import Path

import aiopg.sa
import pytest
import simcore_postgres_database.cli
import sqlalchemy as sa
import sqlalchemy.engine
import yaml
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from faker import Faker
from pytest_simcore.helpers import postgres_tools
from pytest_simcore.helpers.faker_factories import (
    random_group,
    random_project,
    random_user,
)
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNode,
    ProjectNodeCreate,
    ProjectNodesRepo,
)
from simcore_postgres_database.webserver_models import (
    GroupType,
    groups,
    user_to_groups,
    users,
)
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

pytest_plugins = [
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip, docker_compose_file) -> str:
    """Deploys postgres and service is responsive"""
    # container environment
    with Path.open(docker_compose_file) as fh:
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


@pytest.fixture(scope="session")
def sync_engine(postgres_service: str) -> Iterable[sqlalchemy.engine.Engine]:
    _engine: sqlalchemy.engine.Engine = sa.create_engine(url=postgres_service)
    yield _engine
    _engine.dispose()


@pytest.fixture
def _make_asyncpg_engine(postgres_service: str) -> Callable[[bool], AsyncEngine]:
    # NOTE: users is responsible of `await engine.dispose()`
    dsn = postgres_service.replace("postgresql://", "postgresql+asyncpg://")
    minsize = 1
    maxsize = 50

    def _(echo: bool):
        engine: AsyncEngine = create_async_engine(
            dsn,
            pool_size=minsize,
            max_overflow=maxsize - minsize,
            connect_args={
                "server_settings": {"application_name": "postgres_database_tests"}
            },
            pool_pre_ping=True,  # https://docs.sqlalchemy.org/en/14/core/pooling.html#dealing-with-disconnects
            future=True,  # this uses sqlalchemy 2.0 API, shall be removed when sqlalchemy 2.0 is released
            echo=echo,
        )
        return engine

    return _


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
    sync_engine: sqlalchemy.engine.Engine,
    db_metadata: sa.MetaData,
    request: pytest.FixtureRequest,
) -> Iterator[sqlalchemy.engine.Engine]:
    """
    Runs migration to create tables and return a sqlalchemy engine

    NOTE: use this fixture to ensure pg db:
        - up,
        - responsive,
        - init (w/ tables) and/or migrated
    """
    # NOTE: Using migration to upgrade/downgrade is not
    # such a great idea since these tests are used while developing
    # the tables, i.e. when no migration mechanism are in place
    # Best is therefore to start from scratch and delete all at
    # the end

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

    postgres_tools.force_drop_all_tables(sync_engine)


@pytest.fixture
async def aiopg_engine(
    pg_sa_engine: sqlalchemy.engine.Engine,
    postgres_service: str,
) -> AsyncIterator[Engine]:
    """
    Return an aiopg.sa engine connected to a responsive and migrated pg database
    """
    # first start sync
    assert pg_sa_engine.url.database
    assert postgres_service.endswith(pg_sa_engine.url.database)

    warnings.warn(
        "The 'aiopg_engine' is deprecated since we are replacing `aiopg` library by `sqlalchemy.ext.asyncio`."
        "SEE https://github.com/ITISFoundation/osparc-simcore/issues/4529. "
        "Please use 'asyncpg_engine' instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    async with aiopg.sa.create_engine(
        dsn=f"{postgres_service}?application_name=aiopg_engine",
    ) as aiopg_sa_engine:
        yield aiopg_sa_engine


@pytest.fixture
async def connection(aiopg_engine: Engine) -> AsyncIterator[SAConnection]:
    """Returns an aiopg.sa connection from an engine to a fully furnished and ready pg database"""
    async with aiopg_engine.acquire() as _conn:
        yield _conn


@pytest.fixture
async def asyncpg_engine(  # <-- WE SHOULD USE THIS ONE
    is_pdb_enabled: bool,
    pg_sa_engine: sqlalchemy.engine.Engine,
    _make_asyncpg_engine: Callable[[bool], AsyncEngine],
) -> AsyncIterator[AsyncEngine]:
    assert (
        pg_sa_engine
    ), "Ensures pg db up, responsive, init (w/ tables) and/or migrated"

    _apg_engine = _make_asyncpg_engine(is_pdb_enabled)

    yield _apg_engine

    await _apg_engine.dispose()


@pytest.fixture(params=["aiopg", "asyncpg"])
async def connection_factory(
    request: pytest.FixtureRequest,
    aiopg_engine: Engine,
    asyncpg_engine: AsyncEngine,
) -> AsyncIterator[SAConnection | AsyncConnection]:
    """Returns an aiopg.sa connection or an asyncpg connection from an engine to a fully furnished and ready pg database"""
    if request.param == "aiopg":
        async with aiopg_engine.acquire() as conn:
            yield conn
    else:
        async with asyncpg_engine.connect() as conn:
            # NOTE: this is the default in aiopg so we use the same here to make the tests run
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            yield conn


#
# FACTORY FIXTURES
#


@pytest.fixture
def create_fake_group(sync_engine: sqlalchemy.engine.Engine) -> Iterator[Callable]:
    """factory to create standard group"""
    created_ids = []

    async def _creator(conn: SAConnection, **overrides) -> RowProxy:
        if "type" not in overrides:
            overrides["type"] = GroupType.STANDARD
        result: ResultProxy = await conn.execute(
            groups.insert()
            .values(**random_group(**overrides))
            .returning(sa.literal_column("*"))
        )
        group = await result.fetchone()
        assert group
        created_ids.append(group.gid)
        return group

    yield _creator

    assert isinstance(sync_engine, sqlalchemy.engine.Engine)
    with sync_engine.begin() as conn:
        conn.execute(sa.delete(groups).where(groups.c.gid.in_(created_ids)))


@pytest.fixture
def create_fake_user(sync_engine: sqlalchemy.engine.Engine) -> Iterator[Callable]:
    """factory to create a user w/ or w/o a standard group"""

    created_ids = []

    async def _creator(
        conn: SAConnection, group: RowProxy | None = None, **overrides
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

    yield _creator

    assert isinstance(sync_engine, sqlalchemy.engine.Engine)
    with sync_engine.begin() as conn:
        conn.execute(users.delete().where(users.c.id.in_(created_ids)))


@pytest.fixture
async def create_fake_project(
    aiopg_engine: Engine,
) -> AsyncIterator[Callable[..., Awaitable[RowProxy]]]:
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

    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            projects.delete().where(projects.c.uuid.in_(created_project_uuids))
        )


@pytest.fixture
async def create_fake_projects_node(
    connection: aiopg.sa.connection.SAConnection,
    faker: Faker,
) -> Callable[[uuid.UUID], Awaitable[ProjectNode]]:
    async def _creator(project_uuid: uuid.UUID) -> ProjectNode:
        fake_node = ProjectNodeCreate(
            node_id=uuid.uuid4(),
            required_resources=faker.pydict(allowed_types=(str,)),
            key=faker.pystr(),
            version=faker.pystr(),
            label=faker.pystr(),
        )
        repo = ProjectNodesRepo(project_uuid=project_uuid)
        created_nodes = await repo.add(connection, nodes=[fake_node])
        assert created_nodes
        return created_nodes[0]

    return _creator


@pytest.fixture
async def create_fake_product(
    asyncpg_engine: AsyncEngine,
) -> AsyncIterator[Callable[[str], Awaitable[Row]]]:
    created_product_names = set()

    async def _creator(product_name: str) -> Row:
        async with asyncpg_engine.begin() as connection:
            result = await connection.execute(
                sa.insert(products)
                .values(name=product_name, host_regex=".*")
                .returning(sa.literal_column("*"))
            )
            assert result
            row = result.one()
        created_product_names.add(row.name)
        return row

    yield _creator

    async with asyncpg_engine.begin() as conn:
        await conn.execute(
            products.delete().where(products.c.name.in_(created_product_names))
        )

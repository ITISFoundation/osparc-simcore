# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=broad-except

import asyncio
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import aiopg.sa
import pytest
import sqlalchemy as sa
import sqlalchemy.exc as sa_exceptions
from servicelib.aiohttp.aiopg_utils import init_pg_tables, is_pg_responsive
from servicelib.common_aiopg_utils import DataSourceName, create_pg_engine

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

metadata = sa.MetaData()
tbl = sa.Table(
    "tbl",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("val", sa.String(255)),
)


@pytest.fixture
async def postgres_service_with_fake_data(
    request, postgres_service: DataSourceName
) -> DataSourceName:
    async def _create_table(engine: aiopg.sa.Engine):
        async with engine.acquire() as conn:
            await conn.execute(f"DROP TABLE IF EXISTS {tbl.name}")
            await conn.execute(
                f"""CREATE TABLE {tbl.name} (
                                    id serial PRIMARY KEY,
                                    val varchar(255))"""
            )

    dsn = deepcopy(postgres_service)
    dsn.application_name = (
        f"setup {request.module.__name__}.{request.function.__name__}"
    )

    async with aiopg.sa.create_engine(
        dsn.to_uri(), application_name=dsn.application_name
    ) as engine:
        await _create_table(engine)

    dsn.application_name = f"{request.module.__name__}.{request.function.__name__}"
    return dsn


def test_dsn_uri_with_query(postgres_service_with_fake_data: DataSourceName):
    uri = postgres_service_with_fake_data.to_uri(with_query=True)
    sa_engine = None
    try:
        sa_engine = sa.create_engine(uri, echo=True, echo_pool=True)
        assert sa_engine.name == "postgresql"
        assert sa_engine.driver == "psycopg2"

        # if url is wrong, these will fail
        metadata.create_all(sa_engine)
        metadata.drop_all(sa_engine)

    except sa_exceptions.SQLAlchemyError as ee:
        pytest.fail(f"Cannot connect with {uri}: {ee}")

    finally:
        if sa_engine:
            sa_engine.dispose()


async def test_create_pg_engine(postgres_service_with_fake_data: DataSourceName):
    dsn = postgres_service_with_fake_data

    # using raw call and dsn.asdict to fill create_engine arguments!
    engine1 = await aiopg.sa.create_engine(minsize=2, maxsize=5, **asdict(dsn))

    # just creating engine
    engine2 = await create_pg_engine(dsn)
    assert engine1.dsn == engine2.dsn

    # create engine within a managed context
    async with create_pg_engine(dsn) as engine3:
        assert engine2.dsn == engine3.dsn
        assert await is_pg_responsive(engine3)

    assert not engine1.closed
    assert not engine2.closed
    assert engine3.closed

    # checks deallocation if exception
    try:
        async with create_pg_engine(dsn) as engine4:
            assert engine4.dsn == engine3.dsn
            assert not engine4.closed
            raise ValueError()
    except ValueError:
        assert engine4.closed


@pytest.mark.skip(reason="for documentation only and needs a swarm")
async def test_engine_when_idle_for_some_time():
    # NOTE: this test needs a docker swarm and a running postgres service
    dsn = DataSourceName(
        user="test",
        password="secret",
        host="127.0.0.1",
        port=5432,
        database="db",
        application_name="test-app",
    )
    engine = await create_pg_engine(dsn, minsize=2, maxsize=2)
    init_pg_tables(dsn, metadata)
    assert not engine.closed  # does not mean anything!!!
    # pylint: disable=no-value-for-parameter
    async with engine.acquire() as conn:
        # writes
        await conn.execute(tbl.insert().values(val="first"))

    # by default docker swarm kills connections that are idle for more than 15 minutes
    await asyncio.sleep(901)

    async with engine.acquire() as conn:
        await conn.execute(tbl.insert().values(val="third"))


def test_init_tables(postgres_service_with_fake_data: DataSourceName):
    dsn = postgres_service_with_fake_data
    init_pg_tables(dsn, metadata)

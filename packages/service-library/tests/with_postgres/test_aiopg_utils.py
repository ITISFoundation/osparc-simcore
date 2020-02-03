# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=broad-except

import logging
import sys
from copy import deepcopy
from pathlib import Path

import aiopg.sa
import psycopg2
import pytest
import sqlalchemy as sa
from aiohttp import web

from servicelib.aiopg_utils import (ERROR_MSG_NON_RESPONSIVE, DatabaseError,
                                    DataSourceName,
                                    PostgresRetryPolicyUponOperation,
                                    create_pg_engine, init_pg_tables,
                                    is_pg_responsive, retry_pg_api)

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

metadata = sa.MetaData()
tbl = sa.Table('tbl', metadata,
               sa.Column('id', sa.Integer, primary_key=True),
               sa.Column('val', sa.String(255)))




@pytest.fixture
async def postgres_service_with_fake_data(request, loop, postgres_service: DataSourceName)-> DataSourceName:
    async def _create_table(engine: aiopg.sa.Engine):
        async with engine.acquire() as conn:
            await conn.execute(f'DROP TABLE IF EXISTS {tbl.name}')
            await conn.execute(f'''CREATE TABLE {tbl.name} (
                                    id serial PRIMARY KEY,
                                    val varchar(255))''')

    dsn = deepcopy(postgres_service)
    dsn.application_name = f"setup {request.module.__name__}.{request.function.__name__}"

    async with aiopg.sa.create_engine(dsn.to_uri(), application_name=dsn.application_name) as engine:
        await _create_table(engine)

    dsn.application_name = f"{request.module.__name__}.{request.function.__name__}"
    return dsn


def test_dsn_uri_with_query(postgres_service_with_fake_data):
    uri = postgres_service_with_fake_data.to_uri(with_query=True)
    try:
        sa_engine = sa.create_engine(uri, echo=True, echo_pool=True)
        assert sa_engine.name == 'postgresql'
        assert sa_engine.driver == 'psycopg2'

        # if url is wrong, these will fail
        metadata.create_all(sa_engine)
        metadata.drop_all(sa_engine)

    except sa.exc.SQLAlchemyError as ee:
        pytest.fail(f"Cannot connect with {uri}: {ee}")
    finally:
        sa_engine.dispose()


async def test_create_pg_engine(postgres_service_with_fake_data):
    dsn = postgres_service_with_fake_data

    # using raw call and dsn.asdict to fill create_engine arguments!
    engine1 = await aiopg.sa.create_engine(minsize=1, maxsize=5, **dsn.asdict())

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


async def test_engine_when_pg_not_reachable():
    dsn = DataSourceName(database='db', user='foo', password='foo', host='localhost', port=123)

    with pytest.raises(psycopg2.OperationalError):
        await create_pg_engine(dsn)


def test_init_tables(postgres_service_with_fake_data):
    dsn = postgres_service_with_fake_data
    init_pg_tables(dsn, metadata)


async def test_retry_pg_api_policy(postgres_service_with_fake_data, caplog):
    caplog.set_level(logging.ERROR)

    # pylint: disable=no-value-for-parameter
    dsn = postgres_service_with_fake_data.to_uri()
    app_name = postgres_service_with_fake_data.application_name

    async with aiopg.sa.create_engine(dsn, application_name=app_name, echo=True) as engine:

        # goes
        await dec_go(engine, gid=0)
        print(dec_go.retry.statistics)
        assert dec_go.total_retry_count() == 1

        # goes, fails and max retries
        with pytest.raises(web.HTTPServiceUnavailable):
            await dec_go(engine, gid=1, raise_cls=DatabaseError)
        assert ERROR_MSG_NON_RESPONSIVE in caplog.text

        print(dec_go.retry.statistics)
        assert dec_go.total_retry_count() == PostgresRetryPolicyUponOperation.ATTEMPTS_COUNT+1

        # goes and keeps count of all retrials
        await dec_go(engine, gid=2)
        assert dec_go.total_retry_count() == PostgresRetryPolicyUponOperation.ATTEMPTS_COUNT+2



# TODO: review tests below
@pytest.mark.skip(reason="UNDER DEVELOPMENT")
async def test_engine_when_pg_refuses(postgres_service_with_fake_data):
    dsn = postgres_service_with_fake_data
    dsn.password = "Wrong pass"

    #async with create_pg_engine(dsn) as engine:

    engine = await create_pg_engine(dsn)
    assert not engine.closed # does not mean anything!!!

    # acquiring connection must fail
    with pytest.raises(RuntimeError) as execinfo:
        async with engine.acquire() as conn:
            await conn.execute("SELECT 1 as is_alive")
    assert "Cannot acquire connection" in str(execinfo.value)

    # pg not responsive
    assert not await is_pg_responsive(engine)


@pytest.mark.skip(reason="UNDER DEVELOPMENT")
async def test_connections(postgres_service_with_fake_data):
    dsn = postgres_service_with_fake_data.to_uri()
    app_name = postgres_service_with_fake_data.application_name
    ## number of seconds after which connection is recycled, helps to deal with stale connections in pool, default value is -1, means recycling logic is disabled.
    POOL_RECYCLE_SECS = 2


    async def conn_callback(conn):
        print(f"Opening {conn.raw}")


    async with aiopg.sa.create_engine(
        dsn,
        minsize=20,
        maxsize=20,
        # timeout=1,
        pool_recycle=POOL_RECYCLE_SECS,
        echo=True,
        enable_json=True, enable_hstore=True, enable_uuid=True,
        on_connect=conn_callback,
        # extra kwargs in https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS
        application_name=app_name) as engine:

        #  used and free connections
        # size_before = engine.size

        for n in range(10):
            await go(engine, gid=n)

    assert engine
    assert engine.size == 0


# HELPERS ------------

@retry_pg_api
async def dec_go(*args, **kargs):
    return await go(*args, **kargs)


async def go(engine: aiopg.sa.Engine, gid="", raise_cls=None):
    # pylint: disable=no-value-for-parameter
    async with engine.acquire() as conn:
        # writes
        async with conn.begin():
            await conn.execute(tbl.insert().values(val=f'first-{gid}'))
            await conn.execute(tbl.insert().values(val=f'second-{gid}'))

            if raise_cls is not None:
                raise raise_cls


        # reads
        async for row in conn.execute(tbl.select()):
            print(row.id, row.val)
            assert any(prefix in row.val for prefix in ('first', 'second'))

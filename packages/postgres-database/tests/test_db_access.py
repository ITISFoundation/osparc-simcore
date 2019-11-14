# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio

import pytest
import sqlalchemy as sa

from aiopg.sa import create_engine


# HELPERS --------------

metadata = sa.MetaData()
engine_kwargs = dict(user='test', database='test', host='127.0.0.1', password='test', port='5432')

tbl = sa.Table('tbl', metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('val', sa.String(255)))

async def create_table(engine):
    async with engine.acquire() as conn:
        await conn.execute('DROP TABLE IF EXISTS tbl')
        await conn.execute('''CREATE TABLE tbl (
                                id serial PRIMARY KEY,
                                val varchar(255))''')

async def go(engine, value: str):
    async with engine.acquire() as conn:
        #pylint: disable=no-value-for-parameter
        await conn.execute(tbl.insert().values(val=value))

        async for row in conn.execute(tbl.select().where(tbl.c.val == value)):
            print(row.id, row.val)
            assert row.val == value

@pytest.fixture
async def postgres_db(loop):
    async with create_engine(application_name='db_async', **engine_kwargs) as engine:
        await create_table(engine)

        yield engine_kwargs

@pytest.fixture
def postgres_db_sync():
    DSN="postgresql://{user}:{password}@{host}:{port}/{database}?application_name={application_name}"
    sa_engine = sa.create_engine(DSN.format(application_name="db_sync", **engine_kwargs))
    metadata.create_all(sa_engine)

    yield engine_kwargs

    sa_engine.dispose()

async def test_it(postgres_db, postgres_db_sync):

    async def sleep_and_go(engine, n, wait, app_id):
        await asyncio.sleep(wait)
        await go(engine, n%20*app_id)

    async def run_app(app_id: str, wait: int):
        num_goes = 100
        async with create_engine(application_name=app_id,**engine_kwargs) as engine:
            coros = [sleep_and_go(engine, n, 0.01*n*wait, app_id) for n in range(num_goes)]
            await asyncio.gather(*coros)

    import pdb; pdb.set_trace()

    await run_app("foo", 5)

    #num_clients = 1
    #await asyncio.gather(* [ run_app( f'app{n}', 0.01*n) for n in range(num_clients)] )



async def test_db_queries(db_engine):
    import pdb; pdb.set_trace()
    for n in range(100):
        await go(db_engine, n%100*"X")

    import pdb; pdb.set_trace()

    for n in range(1000):
        await go(db_engine, n%100*"X")

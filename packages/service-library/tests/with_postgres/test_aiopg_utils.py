# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint: disable=too-many-arguments
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
import yaml
from aiopg.sa import Engine, create_engine

from servicelib.aiopg_utils import DataSourceName, retry_pg_api, DatabaseError

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope='session')
def docker_compose_file() -> Path:
    # overrides fixture from https://github.com/AndreLouisCaron/pytest-docker
    return current_dir / 'docker-compose.yml'


@pytest.fixture(scope='session')
def postgres_service(docker_services, docker_ip, docker_compose_file):
    with open(docker_compose_file) as fh:
        config = yaml.safe_load(fh)
    environ = config['services']['postgres']['environment']

    dsn = DataSourceName(
        user=environ['POSTGRES_USER'],
        password=environ['POSTGRES_PASSWORD'],
        host=docker_ip,
        port=docker_services.port_for('postgres', 5432),
        database=environ['POSTGRES_DB'],
        application_name="test-app"
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: is_postgres_responsive(dsn.to_uri()),
        timeout=30.0,
        pause=0.1,
    )
    return dsn

from copy import deepcopy

@pytest.fixture
async def pg_server(loop, postgres_service):
    async with create_engine(postgres_service.to_uri()) as engine:
        await create_table(engine)
    return deepcopy(postgres_service)

# HELPERS ------------

def is_postgres_responsive(dsn):
    try:
        engine = sa.create_engine(dsn)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True


async def create_table(engine: Engine):
    async with engine.acquire() as conn:
        await conn.execute('DROP TABLE IF EXISTS tbl')
        await conn.execute('''CREATE TABLE tbl (
                                  id serial PRIMARY KEY,
                                  val varchar(255))''')


metadata = sa.MetaData()
tbl = sa.Table('tbl', metadata,
               sa.Column('id', sa.Integer, primary_key=True),
               sa.Column('val', sa.String(255)))

async def go(gid="", raise_cls=None):
    async with engine.acquire() as conn:
        await conn.execute(tbl.insert().values(val=f'before-{gid}'))

        if raise_cls:
            raise raise_cls

        await conn.execute(tbl.insert().values(val=f'after-{gid}'))

        async for row in conn.execute(tbl.select()):
            print(row.id, row.val)
            assert any(prefix in row.val for prefix in ('before', 'after'))


# TESTS ------------

from aiohttp import web
import asyncio


## number of seconds after which connection is recycled, helps to deal with stale connections in pool, default value is -1, means recycling logic is disabled.
POOL_RECICLE_SECS = 20




@pytest.mark.skip(reason="UNDER DEVELOPMENT")
async def test_connections(pg_server):

    async with create_engine(
        pg_server.to_uri(),
        minsize=1,
        maxsize=20,
        pool_recycle=POOL_RECICLE_SECS,
        echo=True,
        application_name=pg_server.application_name) as engine:
        #  used and free connections
        size_before = engine.size

        for n in range(10):
            await go(n)

        assert size_before > engine.size



async def test_go(pg_server):
    # pylint: disable=no-value-for-parameter

    async with create_engine(pg_server.to_uri(), echo=True) as engine:
        await go()
        print(go.retry.statistics)
        assert go.total_retry_count() == 1

        with pytest.raises(web.HTTPServiceUnavailable):
            await go(fail=True)
        print(go.retry.statistics)
        assert go.total_retry_count() == 4

        await go()
        assert go.total_retry_count() == 5

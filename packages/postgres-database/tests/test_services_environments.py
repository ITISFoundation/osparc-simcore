from typing import AsyncIterator, Callable

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from simcore_postgres_database.models.services_environments import services_environments


@pytest.fixture
async def connection(pg_engine: Engine) -> AsyncIterator[SAConnection]:
    async with pg_engine.acquire() as _conn:
        yield _conn


async def test_it(connection: SAConnection, create_fake_group: Callable):

    group = await create_fake_group(connection, name="Product-A")

    await connection.execute(
        services_environments.insert().values(
            service_key="sim4life",
            gid=group["gid"],  # product's group
            osparc_environments={
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_HOST": "foo",
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_PRIMARY_PORT": 1,
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_SECONDARY_PORT": 2,
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_IP": "1.1.1.1",
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_PORT": 21,
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE": "license.txt",
            },
        )
    )

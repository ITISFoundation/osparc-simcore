# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import random
from typing import Any

import pytest
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.services import services_meta_data
from simcore_postgres_database.models.services_environments import (
    VENDOR_SECRET_PREFIX,
    services_vendor_secrets,
)
from simcore_postgres_database.utils_services_environments import get_vendor_secrets


@pytest.fixture
async def vendor_service() -> str:
    return "simcore/services/dynamic/vendor/some_service"


@pytest.fixture
async def expected_secrets(
    connection: SAConnection, vendor_service: str
) -> dict[str, Any]:

    await connection.execute(
        services_meta_data.insert().values(
            key=vendor_service,
            version="1.0.0",
            name="some-service",
            description="Some service from a vendor",
        )
    )

    await connection.execute(
        services_meta_data.insert().values(
            key="simcore/services/dynamic/vendor/other_service",
            version="1.0.0",
            name="some-service",
            description="Some service from a vendor",
        )
    )

    vendor_secrets = {
        f"{VENDOR_SECRET_PREFIX}LICENSE_SERVER_HOST": "product_a-server",
        f"{VENDOR_SECRET_PREFIX}LICENSE_SERVER_PRIMARY_PORT": 1,
        f"{VENDOR_SECRET_PREFIX}LICENSE_SERVER_SECONDARY_PORT": 2,
        f"{VENDOR_SECRET_PREFIX}LICENSE_DNS_RESOLVER_IP": "1.1.1.1",
        f"{VENDOR_SECRET_PREFIX}LICENSE_DNS_RESOLVER_PORT": "21",
        f"{VENDOR_SECRET_PREFIX}LICENSE_FILE": "license.txt",
        f"{VENDOR_SECRET_PREFIX}LICENSE_FILE_PRODUCT1": "license-p1.txt",
        f"{VENDOR_SECRET_PREFIX}LICENSE_FILE_PRODUCT2": "license-p2.txt",
        f"{VENDOR_SECRET_PREFIX}LIST": "[1, 2, 3]",
    }

    await connection.execute(
        # a vendor exposes these environs to its services to everybody
        services_vendor_secrets.insert().values(
            service_key=vendor_service,
            secrets_map={
                (
                    key.removeprefix(VENDOR_SECRET_PREFIX)
                    if bool(random.getrandbits(1))
                    else key
                ): value
                for key, value in vendor_secrets.items()
            },
        )
    )

    return vendor_secrets


async def test_get_vendor_secrets(
    connection: SAConnection, vendor_service: str, expected_secrets: dict[str, Any]
):

    assert await get_vendor_secrets(connection, vendor_service) == expected_secrets

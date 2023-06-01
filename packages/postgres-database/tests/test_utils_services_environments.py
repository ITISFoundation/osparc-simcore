# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import random
from typing import Any, NamedTuple

import pytest
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.services import services_meta_data
from simcore_postgres_database.models.services_environments import (
    VENDOR_SECRET_PREFIX,
    services_vendor_secrets,
)
from simcore_postgres_database.utils_services_environments import get_vendor_secrets


@pytest.fixture
def vendor_service() -> str:
    return "simcore/services/dynamic/vendor/some_service"


class ExpectedSecrets(NamedTuple):
    old_secrets: dict[str, Any]
    vendor_secrets: dict[str, Any]


@pytest.fixture
async def expected_secrets(
    connection: SAConnection, vendor_service: str
) -> ExpectedSecrets:
    # other-service
    await connection.execute(
        services_meta_data.insert().values(
            key="simcore/services/dynamic/vendor/other_service",
            version="1.0.0",
            name="some-service",
            description="Some service from a vendor",
        )
    )

    # Three versions of 'some_service'
    for version, description in [
        ("0.0.1", "First version from a vendor"),  # has no secrets
        ("0.0.2", "Second version from a vendor"),  # has old secrets
        ("1.0.0", "Third version from a vendor"),  # has secrets
        ("1.2.0", "Lastest version from a vendor"),
    ]:
        await connection.execute(
            services_meta_data.insert().values(
                key=vendor_service,
                version=version,
                name="some-service",
                description=description,
            )
        )

    old_secrets = {
        VENDOR_SECRET_PREFIX + "LICENSE_SERVER_HOST": "product_a-server",
        VENDOR_SECRET_PREFIX + "LICENSE_SERVER_PRIMARY_PORT": 1,
        VENDOR_SECRET_PREFIX + "LICENSE_SERVER_SECONDARY_PORT": 2,
    }

    await connection.execute(
        services_vendor_secrets.insert().values(
            service_key=vendor_service,
            service_from_version="0.0.2",
            secrets_map=old_secrets,
        )
    )

    vendor_secrets = {
        **old_secrets,
        VENDOR_SECRET_PREFIX + "LICENSE_DNS_RESOLVER_IP": "1.1.1.1",
        VENDOR_SECRET_PREFIX + "LICENSE_DNS_RESOLVER_PORT": "21",
        VENDOR_SECRET_PREFIX + "LICENSE_FILE": "license.txt",
        VENDOR_SECRET_PREFIX + "LICENSE_FILE_PRODUCT1": "license-p1.txt",
        VENDOR_SECRET_PREFIX + "LICENSE_FILE_PRODUCT2": "license-p2.txt",
        VENDOR_SECRET_PREFIX + "LIST": "[1, 2, 3]",
    }

    await connection.execute(
        # a vendor exposes these environs to its services to everybody
        services_vendor_secrets.insert().values(
            service_key=vendor_service,
            service_from_version="1.0.0",  # valid from
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

    return ExpectedSecrets(old_secrets, vendor_secrets)


def test_vendor_secret_prefix_must_end_with_underscore():
    assert VENDOR_SECRET_PREFIX.endswith("_")  # should allow


async def test_get_latest_service_vendor_secrets(
    connection: SAConnection, vendor_service: str, expected_secrets: ExpectedSecrets
):
    # latest i.e. 1.2.0
    assert (
        await get_vendor_secrets(connection, vendor_service)
        == expected_secrets.vendor_secrets
    )


@pytest.mark.parametrize(
    "service_version,expected_result",
    [("0.0.1", "Empty"), ("0.0.2", "Old"), ("1.0.0", "Latest"), ("1.2.0", "Latest")],
)
async def test_get_service_vendor_secrets(
    connection: SAConnection,
    vendor_service: str,
    expected_secrets: ExpectedSecrets,
    service_version: str,
    expected_result: str,
):
    match expected_result:
        case "Empty":
            expected = {}
        case "Old":
            expected = expected_secrets.old_secrets
        case "Latest":
            expected = expected_secrets.vendor_secrets

    assert (
        await get_vendor_secrets(connection, vendor_service, service_version)
        == expected
    )

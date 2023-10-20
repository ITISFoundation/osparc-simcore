# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import random
from typing import Any, NamedTuple, TypeAlias

import pytest
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.services import services_meta_data
from simcore_postgres_database.models.services_environments import (
    VENDOR_SECRET_PREFIX,
    services_vendor_secrets,
)
from simcore_postgres_database.utils_services_environments import get_vendor_secrets


@pytest.fixture
def vendor_services() -> list[str]:
    return [f"simcore/services/dynamic/vendor/some_service_{i}" for i in range(10)]


class ExpectedSecrets(NamedTuple):
    old_secrets: dict[str, Any]
    new_secrets: dict[str, Any]


MappedExpectedSecretes: TypeAlias = dict[str, ExpectedSecrets]


@pytest.fixture
async def product_name(connection: SAConnection) -> str:
    a_product_name = "a_prod"
    await connection.execute(
        products.insert().values(name=a_product_name, host_regex="")
    )
    yield a_product_name
    await connection.execute(products.delete())


@pytest.fixture
async def expected_secrets(
    connection: SAConnection, vendor_services: list[str], product_name: str
) -> MappedExpectedSecretes:
    expected_secrets: MappedExpectedSecretes = {}
    for k, vendor_service in enumerate(vendor_services):
        # We define old and new secrets
        old_secrets = {
            VENDOR_SECRET_PREFIX + f"LICENSE_SERVER_HOST{k}": "product_a-server",
            VENDOR_SECRET_PREFIX + f"LICENSE_SERVER_PRIMARY_PORT{k}": 1,
            VENDOR_SECRET_PREFIX + f"LICENSE_SERVER_SECONDARY_PORT{k}": 2,
        }
        new_secrets = {
            **old_secrets,
            VENDOR_SECRET_PREFIX + f"LICENSE_DNS_RESOLVER_IP{k}": "1.1.1.1",
            VENDOR_SECRET_PREFIX + f"LICENSE_DNS_RESOLVER_PORT{k}": "21",
            VENDOR_SECRET_PREFIX + f"LICENSE_FILE{k}": "license.txt",
            VENDOR_SECRET_PREFIX + f"LICENSE_FILE_PRODUCT1{k}": "license-p1.txt",
            VENDOR_SECRET_PREFIX + f"LICENSE_FILE_PRODUCT2{k}": "license-p2.txt",
            VENDOR_SECRET_PREFIX + f"LIST{k}": "[1, 2, 3]",
        }
        expected_secrets[vendor_service] = ExpectedSecrets(old_secrets, new_secrets)

        # 'other-service'
        await connection.execute(
            services_meta_data.insert().values(
                key=f"{vendor_service}_other",
                version="1.0.0",
                name="other-service",
                description="Some other service from a vendor",
            )
        )

        # Some versions of 'some_service'
        for version, description in [
            ("0.0.1", "This has no secrets"),
            ("0.0.2", "This has old_secrets"),  # defined old_secrets
            ("0.1.0", "This should inherit old_secrets"),
            ("1.0.0", "This has new_secrets"),  # defined new_secrets
            ("1.2.0", "Latest version inherits new_secrets"),
        ]:
            await connection.execute(
                services_meta_data.insert().values(
                    key=vendor_service,
                    version=version,
                    name="some-service",
                    description=description,
                )
            )

        await connection.execute(
            services_vendor_secrets.insert().values(
                service_key=vendor_service,
                service_base_version="0.0.2",
                secrets_map=old_secrets,
                product_name=product_name,
            )
        )

        await connection.execute(
            # a vendor exposes these environs to its services to everybody
            services_vendor_secrets.insert().values(
                service_key=vendor_service,
                service_base_version="1.0.0",  # valid from
                secrets_map={
                    (
                        key.removeprefix(VENDOR_SECRET_PREFIX)
                        if bool(random.getrandbits(1))
                        else key
                    ): value
                    for key, value in new_secrets.items()
                },
                product_name=product_name,
            )
        )

    return expected_secrets


def test_vendor_secret_prefix_must_end_with_underscore():
    assert VENDOR_SECRET_PREFIX.endswith("_")  # should allow


async def test_get_latest_service_vendor_secrets(
    connection: SAConnection,
    vendor_services: list[str],
    expected_secrets: MappedExpectedSecretes,
    product_name: str,
):
    # latest i.e. 1.2.0
    for vendor_service in vendor_services:
        assert (
            await get_vendor_secrets(connection, product_name, vendor_service)
            == expected_secrets[vendor_service].new_secrets
        )


@pytest.mark.parametrize(
    "service_version,expected_result",
    [
        ("0.0.1", "Empty"),
        ("0.0.2", "Old"),
        ("0.1.0", "Old"),
        ("1.0.0", "New"),
        ("1.2.0", "New"),
    ],
)
async def test_get_service_vendor_secrets(
    connection: SAConnection,
    vendor_services: list[str],
    expected_secrets: MappedExpectedSecretes,
    service_version: str,
    expected_result: str,
    product_name: str,
):
    # ("0.0.1", "This has no secrets"),
    # ("0.0.2", "This has old_secrets"),  # defined old_secrets
    # ("0.1.0", "This should inherit old_secrets"),
    # ("1.0.0", "This has new_secrets"), # defined new_secrets
    # ("1.2.0", "Latest version inherits new_secrets"),

    for vendor_service in vendor_services:
        match expected_result:
            case "Empty":
                expected = {}
            case "Old":
                expected = expected_secrets[vendor_service].old_secrets
            case "New":
                expected = expected_secrets[vendor_service].new_secrets
            case _:
                pytest.fail(f"{expected_result} not considered")

        assert (
            await get_vendor_secrets(
                connection, product_name, vendor_service, service_version
            )
            == expected
        )

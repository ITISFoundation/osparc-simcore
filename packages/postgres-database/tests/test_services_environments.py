# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Callable

from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.services_environments import services_environments
from sqlalchemy.sql import select


async def test_services_environments_table(
    connection: SAConnection, create_fake_group: Callable
):

    vendor_services_prefix = "simcore/services/dynamic/vendor-x"
    product_group = await create_fake_group(connection, name="product_a")

    await connection.execute(
        # a vendor exposes these environs to its services to everybody
        services_environments.insert().values(
            service_key_prefix=vendor_services_prefix,
            # everybody
            osparc_environments={
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_HOST": "everybody",
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE": "license-everybody.txt",
            },
        )
    )

    await connection.execute(
        # same vendor exposes different environs to its services for a given product
        services_environments.insert().values(
            service_key_prefix=vendor_services_prefix,
            gid=product_group["gid"],  # product's group
            osparc_environments={
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_HOST": "product_a-server",
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_PRIMARY_PORT": 1,
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_SECONDARY_PORT": 2,
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_IP": "1.1.1.1",
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_PORT": 21,
                "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE": "license.txt",
            },
        )
    )

    substitutions = await connection.scalar(
        select([services_environments.c.osparc_environments]).where(
            (
                services_environments.c.gid == product_group["gid"]
            )  # current product's group
            & services_environments.c.service_key_prefix.like(
                f"{vendor_services_prefix}%"
            )
        )
    )

    assert substitutions == {
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_HOST": "product_a-server",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_PRIMARY_PORT": 1,
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_SECONDARY_PORT": 2,
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_IP": "1.1.1.1",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_PORT": 21,
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE": "license.txt",
    }

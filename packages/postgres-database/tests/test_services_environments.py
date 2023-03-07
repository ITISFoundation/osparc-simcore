# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.services import services_meta_data
from simcore_postgres_database.models.services_environments import (
    OsparcEnvironmentsDict,
    services_vendor_environments,
)
from sqlalchemy.sql import select


async def test_services_environments_table(connection: SAConnection):

    vendor_service = "simcore/services/dynamic/vendor/some_service"

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

    await connection.execute(
        # a vendor exposes these environs to its services to everybody
        services_vendor_environments.insert().values(
            service_key=vendor_service,
            identifiers_map=OsparcEnvironmentsDict(
                {
                    "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_HOST": "product_a-server",
                    "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_PRIMARY_PORT": 1,
                    "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_SECONDARY_PORT": 2,
                    "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_IP": "1.1.1.1",
                    "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_PORT": "21",
                    "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE": "license.txt",
                    "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE_PRODUCT1": "license-p1.txt",
                    "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE_PRODUCT2": "license-p2.txt",
                    "OSPARC_ENVIRONMENT_VENDOR_LIST": [1, 2, 3],
                }
            ),
        )
    )

    substitutions = await connection.scalar(
        select([services_vendor_environments.c.identifiers_map]).where(
            services_vendor_environments.c.service_key == vendor_service
        )
    )

    assert substitutions == {
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_HOST": "product_a-server",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_PRIMARY_PORT": 1,
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_SECONDARY_PORT": 2,
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_IP": "1.1.1.1",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_PORT": "21",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE": "license.txt",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE_PRODUCT1": "license-p1.txt",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE_PRODUCT2": "license-p2.txt",
        "OSPARC_ENVIRONMENT_VENDOR_LIST": [1, 2, 3],
    }

    vendor_substitutions = await connection.execute(
        select([services_vendor_environments.c.identifiers_map]).where(
            services_vendor_environments.c.service_key.like("%/vendor/%")
        )
    )

    assert [row.identifiers_map for row in await vendor_substitutions.fetchall()] == [
        substitutions
    ]

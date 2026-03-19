# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=no-value-for-parameter


from collections.abc import Callable

import pytest
import sqlalchemy as sa
from pytest_simcore.helpers.webserver_fake_services_data import (
    FAKE_FILE_CONSUMER_SERVICES,
    list_supported_filetypes,
)
from simcore_postgres_database.models.services import services_meta_data
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


@pytest.fixture
def make_table() -> Callable:
    async def _make(connection: AsyncConnection):
        for service in FAKE_FILE_CONSUMER_SERVICES:
            await connection.execute(
                services_meta_data.insert().values(
                    key=service["key"],
                    version=service["version"],
                    name=service["display_name"],
                    description=service["display_name"],
                )
            )

            for n, consumable in enumerate(service["consumes"]):
                filetype, port, *_ = [*consumable.split(":"), "input_1"]

                result = await connection.execute(
                    services_consume_filetypes.insert().values(
                        service_key=service["key"],
                        service_version=service["version"],
                        service_display_name=service["display_name"],
                        service_input_port=port,
                        filetype=filetype,
                        preference_order=n,
                    )
                )

                assert not result.returns_rows

    return _make


@pytest.fixture
async def connection(asyncpg_engine: AsyncEngine, asyncpg_connection: AsyncConnection, make_table: Callable):
    assert asyncpg_engine

    # EXTENDS
    await make_table(asyncpg_connection)
    return asyncpg_connection


async def test_check_constraint(connection: AsyncConnection):
    stmt_create_services_consume_filetypes = sa.text(
        'INSERT INTO "services_consume_filetypes" ("service_key", "service_version", "service_display_name", '
        '"service_input_port", "filetype", "preference_order", "is_guest_allowed") VALUES'
        "('simcore/services/dynamic/bio-formats-web',	'1.0.20',	'bio-formats',	'input_1',	'PNG',	0, '1'),"
        "('simcore/services/dynamic/raw-graphs',	'2.11.20',	'RAWGraphs',	'input_1',	'lowerUpper',	0, '1');"
    )

    with pytest.raises(IntegrityError, match="ck_filetype_is_upper"):
        await connection.execute(stmt_create_services_consume_filetypes)


async def test_get_compatible_services(connection: AsyncConnection):
    # given a filetype, get sorted services
    # test sorting of services given a filetype
    # https://docs.sqlalchemy.org/en/13/core/tutorial.html#ordering-or-grouping-by-a-label
    stmt = (
        services_consume_filetypes.select()
        .where(services_consume_filetypes.c.filetype == "DCM")
        .order_by("preference_order")
    )
    result = await connection.execute(stmt)

    assert result.returns_rows

    rows = result.mappings().all()

    # only S4L
    assert all(row["service_key"] == "simcore/services/dynamic/sim4life" for row in rows)
    assert len(rows) == 3

    assert rows[0]["service_version"] == "1.0.29"
    assert rows[-1]["service_version"] == "2.0.0"


async def test_get_supported_filetypes(connection: AsyncConnection):
    # given a service, get supported filetypes

    stmt = (
        sa.select(
            services_consume_filetypes.c.filetype,
        )
        .where(services_consume_filetypes.c.service_key == "simcore/services/dynamic/sim4life")
        .order_by(services_consume_filetypes.c.filetype)
        .distinct()
    )

    result = await connection.execute(stmt)
    rows = result.mappings().all()
    assert rows is not None
    assert [row["filetype"] for row in rows] == ["DCM", "S4LCACHEDATA"]


async def test_list_supported_filetypes(connection: AsyncConnection):
    # given a service, get supported filetypes

    stmt = (
        sa.select(
            services_consume_filetypes.c.filetype,
        )
        .order_by(services_consume_filetypes.c.filetype)
        .distinct()
    )

    result = await connection.execute(stmt)
    rows = result.mappings().all()
    assert rows is not None
    assert [row["filetype"] for row in rows] == list_supported_filetypes()


async def test_constraints(connection: AsyncConnection):
    # test foreign key constraints with service metadata table

    await connection.execute(
        services_meta_data.delete().where(services_meta_data.c.key == "simcore/services/dynamic/sim4life")
    )

    stmt = (
        sa.select(
            sa.func.count(services_consume_filetypes.c.service_key).label("num_services"),
        )
        .where(services_consume_filetypes.c.filetype == "DCM")
        .scalar_subquery()
    )
    num_services = await connection.scalar(stmt)
    assert num_services == 0

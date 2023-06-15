# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=no-value-for-parameter


from typing import Callable

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.exc import ResourceClosedError
from aiopg.sa.result import ResultProxy, RowProxy
from pytest_simcore.helpers.utils_services import (
    FAKE_FILE_CONSUMER_SERVICES,
    list_supported_filetypes,
)
from simcore_postgres_database.errors import CheckViolation
from simcore_postgres_database.models.services import services_meta_data
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)


@pytest.fixture
def make_table() -> Callable:
    async def _make(connection: SAConnection):
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
                filetype, port, *_ = consumable.split(":") + ["input_1"]

                result: ResultProxy = await connection.execute(
                    services_consume_filetypes.insert().values(
                        service_key=service["key"],
                        service_version=service["version"],
                        service_display_name=service["display_name"],
                        service_input_port=port,
                        filetype=filetype,
                        preference_order=n,
                    )
                )

                assert result.closed
                assert not result.returns_rows
                with pytest.raises(ResourceClosedError):
                    await result.scalar()

    return _make


@pytest.fixture
async def connection(
    pg_engine: sa.engine.Engine, connection: SAConnection, make_table: Callable
):
    assert pg_engine
    # NOTE: do not remove th pg_engine, or the test will fail as pytest
    # cannot set the parameters in the fixture

    # EXTENDS
    await make_table(connection)
    yield connection


async def test_check_constraint(connection: SAConnection):
    stmt_create_services_consume_filetypes = sa.text(
        'INSERT INTO "services_consume_filetypes" ("service_key", "service_version", "service_display_name", "service_input_port", "filetype", "preference_order", "is_guest_allowed") VALUES'
        "('simcore/services/dynamic/bio-formats-web',	'1.0.20',	'bio-formats',	'input_1',	'PNG',	0, '1'),"
        "('simcore/services/dynamic/raw-graphs',	'2.11.20',	'RAWGraphs',	'input_1',	'lowerUpper',	0, '1');"
    )

    with pytest.raises(CheckViolation) as error_info:
        await connection.execute(stmt_create_services_consume_filetypes)

    error = error_info.value
    assert error.pgcode == "23514"
    assert error.pgerror
    assert "ck_filetype_is_upper" in error.pgerror


async def test_get_compatible_services(connection: SAConnection):
    # given a filetype, get sorted services
    # test sorting of services given a filetype
    # https://docs.sqlalchemy.org/en/13/core/tutorial.html#ordering-or-grouping-by-a-label
    stmt = (
        services_consume_filetypes.select()
        .where(services_consume_filetypes.c.filetype == "DCM")
        .order_by("preference_order")
    )
    result: ResultProxy = await connection.execute(stmt)

    assert result.returns_rows

    rows: list[RowProxy] = await result.fetchall()

    # only S4L
    assert all(row.service_key == "simcore/services/dynamic/sim4life" for row in rows)
    assert len(rows) == 3

    assert rows[0].service_version == "1.0.29"
    assert rows[-1].service_version == "2.0.0"


async def test_get_supported_filetypes(connection: SAConnection):
    # given a service, get supported filetypes

    stmt = (
        sa.select(
            services_consume_filetypes.c.filetype,
        )
        .where(
            services_consume_filetypes.c.service_key
            == "simcore/services/dynamic/sim4life"
        )
        .order_by(services_consume_filetypes.c.filetype)
        .distinct()
    )

    result: ResultProxy = await connection.execute(stmt)
    rows = await result.fetchall()
    assert rows is not None
    assert [v for row in rows for v in row.values()] == ["DCM", "S4LCACHEDATA"]


async def test_list_supported_filetypes(connection: SAConnection):
    # given a service, get supported filetypes

    stmt = (
        sa.select(
            services_consume_filetypes.c.filetype,
        )
        .order_by(services_consume_filetypes.c.filetype)
        .distinct()
    )

    result: ResultProxy = await connection.execute(stmt)
    rows = await result.fetchall()
    assert rows is not None
    assert [v for row in rows for v in row.values()] == list_supported_filetypes()


async def test_contraints(connection: SAConnection):
    # test foreign key contraints with service metadata table

    await connection.execute(
        services_meta_data.delete().where(
            services_meta_data.c.key == "simcore/services/dynamic/sim4life"
        )
    )

    stmt = (
        sa.select(
            sa.func.count(services_consume_filetypes.c.service_key).label(
                "num_services"
            ),
        )
        .where(services_consume_filetypes.c.filetype == "DCM")
        .scalar_subquery()
    )
    result: ResultProxy = await connection.execute(stmt)
    num_services = await result.scalar()
    assert num_services == 0

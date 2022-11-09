# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=no-value-for-parameter


import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.exc import ResourceClosedError
from aiopg.sa.result import ResultProxy, RowProxy
from pytest_simcore.helpers.utils_services import (
    FAKE_FILE_CONSUMER_SERVICES,
    list_supported_filetypes,
)
from simcore_postgres_database.models.services import services_meta_data
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)


@pytest.fixture
def make_table():
    async def _make(conn):

        for service in FAKE_FILE_CONSUMER_SERVICES:

            await conn.execute(
                services_meta_data.insert().values(
                    key=service["key"],
                    version=service["version"],
                    name=service["display_name"],
                    description=service["display_name"],
                )
            )

            for n, consumable in enumerate(service["consumes"]):
                filetype, port, *_ = consumable.split(":") + ["input_1"]

                result: ResultProxy = await conn.execute(
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
async def conn(pg_engine: Engine, make_table):
    async with pg_engine.acquire() as conn:
        await make_table(conn)
        yield conn


async def test_get_compatible_services(conn):
    # given a filetype, get sorted services
    # test sorting of services given a filetype
    # https://docs.sqlalchemy.org/en/13/core/tutorial.html#ordering-or-grouping-by-a-label
    stmt = (
        services_consume_filetypes.select()
        .where(services_consume_filetypes.c.filetype == "DCM")
        .order_by("preference_order")
    )
    result: ResultProxy = await conn.execute(stmt)

    assert result.returns_rows

    rows: list[RowProxy] = await result.fetchall()

    # only S4L
    assert all(row.service_key == "simcore/services/dynamic/sim4life" for row in rows)
    assert len(rows) == 3

    assert rows[0].service_version == "1.0.29"
    assert rows[-1].service_version == "2.0.0"


async def test_get_supported_filetypes(conn):
    # given a service, get supported filetypes

    stmt = (
        sa.select(
            [
                services_consume_filetypes.c.filetype,
            ]
        )
        .where(
            services_consume_filetypes.c.service_key
            == "simcore/services/dynamic/sim4life"
        )
        .order_by(services_consume_filetypes.c.filetype)
        .distinct()
    )

    result: ResultProxy = await conn.execute(stmt)
    rows: list[RowProxy] = await result.fetchall()
    assert [v for row in rows for v in row.values()] == ["DCM", "S4LCacheData"]


async def test_list_supported_filetypes(conn):
    # given a service, get supported filetypes

    stmt = (
        sa.select(
            [
                services_consume_filetypes.c.filetype,
            ]
        )
        .order_by(services_consume_filetypes.c.filetype)
        .distinct()
    )

    result: ResultProxy = await conn.execute(stmt)
    rows: list[RowProxy] = await result.fetchall()
    assert [v for row in rows for v in row.values()] == list_supported_filetypes()


@pytest.mark.skip(reason="Under DEV")
async def test_list_default_compatible_services():
    stmt = (
        sa.select(
            [
                services_consume_filetypes,
            ]
        )
        .group_by(services_consume_filetypes.c.filetype)
        .order_by(
            services_consume_filetypes.c.key, services_consume_filetypes.c.version
        )
        .distinct()
    )
    raise NotImplementedError()


async def test_contraints(conn):
    # test foreign key contraints with service metadata table

    await conn.execute(
        services_meta_data.delete().where(
            services_meta_data.c.key == "simcore/services/dynamic/sim4life"
        )
    )

    stmt = (
        sa.select(
            [
                sa.func.count(services_consume_filetypes.c.service_key).label(
                    "num_services"
                ),
            ]
        )
        .where(services_consume_filetypes.c.filetype == "DCM")
        .scalar_subquery()
    )
    result: ResultProxy = await conn.execute(stmt)
    num_services = await result.scalar()
    assert num_services == 0


@pytest.mark.skip(reason="Under DEV")
async def test_get_compatible_services_available_to_everyone(conn):
    # TODO: resolve when this logic is moved to catalog

    # given a filetype, get sorted services
    # test sorting of services given a filetype
    # https://docs.sqlalchemy.org/en/13/core/tutorial.html#ordering-or-grouping-by-a-label

    raise NotImplementedError()

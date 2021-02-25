# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=no-value-for-parameter


from typing import List

import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.exc import ResourceClosedError
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.services import services_meta_data
from simcore_postgres_database.webserver_models import services_consume_filetypes

FAKE_SERVICES = [
    # services support one filetype
    {
        "key": "simcore/services/dynamic/sim4life",
        "version": "1.0.29",
        "display_name": "Sim4Life",
        "consumes": [
            "DCM",
        ],
    },
    # new version
    {
        "key": "simcore/services/dynamic/sim4life",
        "version": "1.3.0",
        "display_name": "Sim4Life",
        "consumes": [
            "DCM",
        ],
    },
    # newer version, with more support
    {
        "key": "simcore/services/dynamic/sim4life",
        "version": "2.0.0",
        "display_name": "Sim4Life",
        "consumes": ["DCM", "S4LCacheData"],
    },
    # another service with multiple format support (preferred for CSV)
    {
        "key": "simcore/services/dynamic/raw-graphs",
        "version": "2.11.1",
        "display_name": "2D plot - RAWGraphs",
        "consumes": ["CSV", "XLS"],
    },
    # yet another service with also CSV support and PNG only in port 3
    {
        "key": "simcore/services/dynamic/openmicroscopy-web",
        "version": "1.0.1",
        "display_name": "Open microscopy",
        # FYI: https://docs.openmicroscopy.org/bio-formats/6.6.0/supported-formats.html
        "consumes": [
            "CSV",
            "JPEG",
            "PNG:input_3",
        ],
    },
]


@pytest.fixture
def make_table():
    async def _make(conn):

        for service in FAKE_SERVICES:

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


async def test_get_compatible_services(pg_engine: Engine, make_table):
    # given a filetype, get sorted services
    # test sorting of services given a filetype
    # https://docs.sqlalchemy.org/en/13/core/tutorial.html#ordering-or-grouping-by-a-label

    async with pg_engine.acquire() as conn:
        await make_table(conn)

        stmt = (
            services_consume_filetypes.select()
            .where(services_consume_filetypes.c.filetype == "DCM")
            .order_by("preference_order")
        )
        result: ResultProxy = await conn.execute(stmt)

        assert result.returns_rows

        rows: List[RowProxy] = await result.fetchall()

        # only S4L
        assert all(
            row.service_key == "simcore/services/dynamic/sim4life" for row in rows
        )
        assert len(rows) == 3

        assert rows[0].service_version == "1.0.29"
        assert rows[-1].service_version == "2.0.0"


async def test_get_supported_filetypes(pg_engine: Engine, make_table):
    # given a service, get supported filetypes

    async with pg_engine.acquire() as conn:
        await make_table(conn)

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
        rows: List[RowProxy] = await result.fetchall()
        assert [v for row in rows for v in row.values()] == ["DCM", "S4LCacheData"]


async def test_contraints(pg_engine: Engine, make_table):
    # test foreign key contraints with service metadata table

    async with pg_engine.acquire() as conn:
        await make_table(conn)

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
            .as_scalar()
        )
        result: ResultProxy = await conn.execute(stmt)
        num_services = await result.scalar()
        assert num_services == 0

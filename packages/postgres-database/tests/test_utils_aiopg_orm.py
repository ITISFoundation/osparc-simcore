# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from datetime import datetime
from typing import Iterator, List, Optional

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from simcore_postgres_database.models.scicrunch_resources import scicrunch_resources
from simcore_postgres_database.utils_aiopg_orm import BaseOrm


@pytest.fixture
async def fake_scicrunch_ids(pg_engine: Engine) -> List[str]:
    row1 = dict(rrid="RRID:foo", name="foo", description="fooing")
    row2 = dict(rrid="RRID:bar", name="bar", description="barring")

    row_ids = []
    async with pg_engine.acquire() as conn:
        for row in (row1, row2):
            row_id = await conn.scalar(
                scicrunch_resources.insert()
                .values(**row)
                .returning(scicrunch_resources.c.rrid)
            )
            assert row_id, f"{row} failed"
            row_ids.append(row_id)

    return row_ids


@pytest.fixture()
async def scicrunch_orm(pg_engine: Engine) -> Iterator[BaseOrm[str]]:
    # This is a table without dependencies and therefore easy to use as fixture
    class ScicrunchOrm(BaseOrm[str]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                scicrunch_resources,
                connection,
                readonly={"creation_date", "last_change_date"},
            )

    async with pg_engine.acquire() as conn:
        orm_obj = ScicrunchOrm(conn)
        yield orm_obj


async def test_orm_fetch(scicrunch_orm: BaseOrm[str], fake_scicrunch_ids: List[str]):

    # insert 1 and 2
    scicrunch_id1, scicrunch_id2 = fake_scicrunch_ids
    assert scicrunch_id1 is not None
    assert scicrunch_id1 == "RRID:foo"
    assert scicrunch_id2 is not None
    assert scicrunch_id2 == "RRID:bar"

    # fetch
    all_scicrunch_resources = await scicrunch_orm.fetchall()
    assert len(all_scicrunch_resources) == 2

    # pin-row
    scicrunch_orm.pin_row(scicrunch_id1)
    scicrunch_resource = await scicrunch_orm.fetch()
    assert scicrunch_resource
    assert scicrunch_resource.rrid == scicrunch_id1

    # overrides pin-row in a call
    scicrunch_resource = await scicrunch_orm.fetch(rowid=scicrunch_id2)
    assert scicrunch_resource
    assert scicrunch_resource.rrid == scicrunch_id2
    assert scicrunch_resource in all_scicrunch_resources

    scicrunch_resource = await scicrunch_orm.fetch()
    assert scicrunch_resource
    assert scicrunch_resource.rrid == scicrunch_id1

    # partial columns fetch
    scicrunch_resource = await scicrunch_orm.fetch("name description")
    assert scicrunch_resource
    assert scicrunch_resource.name == "foo"
    assert scicrunch_resource.description == "fooing"
    assert not hasattr(scicrunch_resource, "rrid")

    all_scicrunch_resources = await scicrunch_orm.fetchall("name description")
    assert len(all_scicrunch_resources) == 2


async def test_orm_insert(scicrunch_orm: BaseOrm[str]):

    # insert 1 and 2
    scicrunch_id1 = await scicrunch_orm.insert(
        rrid="RRID:foo", name="foo", description="fooing"
    )
    assert scicrunch_id1 == "RRID:foo"

    scicrunch_id2 = await scicrunch_orm.insert(
        rrid="RRID:bar", name="bar", description="barring"
    )
    assert scicrunch_id2 == "RRID:bar"


async def test_orm_update(scicrunch_orm: BaseOrm[str], fake_scicrunch_ids: List[str]):

    scicrunch_id1, scicrunch_id2 = fake_scicrunch_ids

    # FIXME: since no row is pinned, update applies to all rows
    # but only the first one is returned
    first_udpated_row_id = await scicrunch_orm.update(name="w/o pin")
    assert first_udpated_row_id

    rows = await scicrunch_orm.fetchall("name rrid")
    assert all(row.name == "w/o pin" for row in rows)

    # let's use pin
    scicrunch_orm.pin_row(scicrunch_id2)
    assert await scicrunch_orm.update(name="w/ pin") == scicrunch_id2

    assert (await scicrunch_orm.fetch(rowid=scicrunch_id1)).name == "w/o pin"
    assert (await scicrunch_orm.fetch(rowid=scicrunch_id2)).name == "w/ pin"

    # test read only
    with pytest.raises(ValueError):
        await scicrunch_orm.update(creation_date=datetime.now())

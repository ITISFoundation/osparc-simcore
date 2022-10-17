# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from datetime import datetime
from typing import Iterator

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.scicrunch_resources import scicrunch_resources
from simcore_postgres_database.utils_aiopg_orm import ALL_COLUMNS, BaseOrm


@pytest.fixture
async def fake_scicrunch_ids(pg_engine: Engine) -> list[str]:
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
                writeonce={"rrid"},
            )

    async with pg_engine.acquire() as conn:
        orm_obj = ScicrunchOrm(conn)
        yield orm_obj


async def test_orm_fetch(scicrunch_orm: BaseOrm[str], fake_scicrunch_ids: list[str]):

    # insert 1 and 2
    scicrunch_id1, scicrunch_id2 = fake_scicrunch_ids
    assert scicrunch_id1 is not None
    assert scicrunch_id1 == "RRID:foo"
    assert scicrunch_id2 is not None
    assert scicrunch_id2 == "RRID:bar"

    # fetch
    all_scicrunch_resources = await scicrunch_orm.fetch_all()
    assert len(all_scicrunch_resources) == 2

    scicrunch_resource = await scicrunch_orm.fetch(rowid=scicrunch_id1)
    assert scicrunch_resource
    assert scicrunch_resource.rrid == scicrunch_id1

    scicrunch_resource = await scicrunch_orm.fetch(rowid=scicrunch_id2)
    assert scicrunch_resource
    assert scicrunch_resource.rrid == scicrunch_id2
    assert scicrunch_resource in all_scicrunch_resources

    # partial columns fetch
    scicrunch_resource = await scicrunch_orm.fetch(
        "name description", rowid=scicrunch_id1
    )
    assert scicrunch_resource
    assert scicrunch_resource.name == "foo"
    assert scicrunch_resource.description == "fooing"
    assert not hasattr(scicrunch_resource, "rrid")

    # alternative arguments
    scicrunch_resource1 = await scicrunch_orm.fetch(
        returning_cols=["name", "description"],
        rowid=scicrunch_id1,
    )
    assert scicrunch_resource == scicrunch_resource1

    all_scicrunch_resources = await scicrunch_orm.fetch_all(
        returning_cols=["name", "description"],
    )
    assert len(all_scicrunch_resources) == 2


async def test_orm_fetch_defaults(
    scicrunch_orm: BaseOrm[str], fake_scicrunch_ids: list[str]
):

    # insert 1 and 2
    scicrunch_id1, scicrunch_id2 = fake_scicrunch_ids
    assert scicrunch_id1 is not None
    assert scicrunch_id1 == "RRID:foo"
    assert scicrunch_id2 is not None
    assert scicrunch_id2 == "RRID:bar"

    # pins row using default
    scicrunch_orm.set_filter(scicrunch_id1)
    scicrunch_resource = await scicrunch_orm.fetch()
    assert scicrunch_resource
    assert scicrunch_resource.rrid == scicrunch_id1

    # overrides defaults in a call
    scicrunch_resource = await scicrunch_orm.fetch(rowid=scicrunch_id2)
    assert scicrunch_resource
    assert scicrunch_resource.rrid == scicrunch_id2

    # but this call uses default again
    scicrunch_resource = await scicrunch_orm.fetch()
    assert scicrunch_resource
    assert scicrunch_resource.rrid == scicrunch_id1

    # partial columns fetch
    scicrunch_resource = await scicrunch_orm.fetch("name description")
    assert scicrunch_resource
    assert scicrunch_resource.name == "foo"
    assert scicrunch_resource.description == "fooing"
    assert not hasattr(scicrunch_resource, "rrid")


async def test_orm_fetchall_page(
    scicrunch_orm: BaseOrm[str], fake_scicrunch_ids: list[str]
):

    # insert 1 and 2
    scicrunch_id1, scicrunch_id2 = fake_scicrunch_ids
    assert scicrunch_id1 is not None
    assert scicrunch_id1 == "RRID:foo"
    assert scicrunch_id2 is not None
    assert scicrunch_id2 == "RRID:bar"

    # fetch
    all_scicrunch_resources = await scicrunch_orm.fetch_all("rrid")
    assert len(all_scicrunch_resources) == 2

    # fetch page
    page1, total_rows = await scicrunch_orm.fetch_page("rrid", offset=0, limit=1)
    assert total_rows == 2
    assert len(page1) == 1
    assert page1[0].rrid == scicrunch_id1

    page2, total_rows = await scicrunch_orm.fetch_page("rrid", offset=1)
    assert total_rows == 2
    assert len(page2) == 1
    assert page2[0].rrid == scicrunch_id2

    # same as fetchall if offset=0 and limit is None
    page, total_rows = await scicrunch_orm.fetch_page("rrid", offset=0)
    assert len(page) == total_rows
    assert all_scicrunch_resources == page

    # sorted
    # pylint: disable=protected-access
    page, total_rows = await scicrunch_orm.fetch_page(
        "rrid", offset=0, sort_by=scicrunch_orm._primary_key
    )
    assert len(page) == total_rows

    all_scicrunch_resources.reverse()
    assert all_scicrunch_resources == page


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


async def test_orm_insert_with_different_returns(scicrunch_orm: BaseOrm[str]):

    # insert 1 and 2
    scicrunch1 = await scicrunch_orm.insert(
        returning_cols=ALL_COLUMNS, rrid="RRID:foo", name="foo", description="fooing"
    )
    assert scicrunch1
    assert isinstance(scicrunch1, RowProxy)
    assert scicrunch1.rrid == "RRID:foo"
    assert {"rrid", "name", "description", "creation_date", "last_change_date"} == set(
        scicrunch1.keys()
    )

    scicrunch2 = await scicrunch_orm.insert(
        returning_cols=["rrid", "creation_date"],
        rrid="RRID:bar",
        name="bar",
        description="barring",
    )
    assert scicrunch2
    assert isinstance(scicrunch2, RowProxy)
    assert {"rrid", "creation_date"} == set(scicrunch2.keys())
    assert scicrunch2.rrid == "RRID:bar"


async def test_orm_update(scicrunch_orm: BaseOrm[str], fake_scicrunch_ids: list[str]):

    scicrunch_id1, scicrunch_id2 = fake_scicrunch_ids

    # FIXME: since no row is pinned, update applies to all rows
    # but only the first one is returned
    first_udpated_row_id = await scicrunch_orm.update(name="w/o pin")
    assert first_udpated_row_id

    rows = await scicrunch_orm.fetch_all("name rrid")
    assert all(row.name == "w/o pin" for row in rows)

    # let's use default to pin the rwo to update
    scicrunch_orm.set_filter(scicrunch_id2)
    assert await scicrunch_orm.update(name="w/ pin") == scicrunch_id2

    assert (await scicrunch_orm.fetch(rowid=scicrunch_id1)).name == "w/o pin"
    assert (await scicrunch_orm.fetch(rowid=scicrunch_id2)).name == "w/ pin"


async def test_orm_update_with_different_returns(
    scicrunch_orm: BaseOrm[str], fake_scicrunch_ids: list[str]
):

    scicrunch_id1, _ = fake_scicrunch_ids

    scicrunch_orm.set_filter(rowid=scicrunch_id1)

    scicrunch1_before = await scicrunch_orm.fetch()
    assert scicrunch1_before

    scicrunch1_after = await scicrunch_orm.update(
        name="updated name", returning_cols=ALL_COLUMNS
    )
    assert scicrunch1_after
    assert isinstance(scicrunch1_after, RowProxy)

    assert set(scicrunch1_after.keys()) == {
        "rrid",
        "name",
        "description",
        "creation_date",
        "last_change_date",
    }

    assert scicrunch1_before.last_change_date < scicrunch1_after.last_change_date


async def test_orm_fail_to_update(
    scicrunch_orm: BaseOrm[str], fake_scicrunch_ids: list[str]
):

    scicrunch_id1, scicrunch_id2 = fake_scicrunch_ids

    # read only
    with pytest.raises(ValueError):
        await scicrunch_orm.update(creation_date=datetime.now())

    # write once
    with pytest.raises(ValueError):
        await scicrunch_orm.update(rrid="RRID:NEW")


@pytest.mark.skip(reason="DEV")
async def test_rowproxy(scicrunch_orm: BaseOrm[str], fake_scicrunch_ids: list[str]):
    # insert 1 and 2
    scicrunch_id1, scicrunch_id2 = fake_scicrunch_ids
    assert scicrunch_id1 is not None
    assert scicrunch_id1 == "RRID:foo"
    assert scicrunch_id2 is not None
    assert scicrunch_id2 == "RRID:bar"

    # fetch
    rows: list[RowProxy] = await scicrunch_orm.fetch_all()
    assert len(rows) == 2

    # Exercise conversions ----

    # as dict
    row = rows[0]
    row_as_dict = dict(row.items())

    # as tuple
    row_as_tuple = row.as_tuple()
    assert set(row_as_tuple) == set(row_as_dict.values())

    # to list[dict]: warning ... sometimes rows are None when in first() or fetchone()...
    list_of_dicts = [dict(row.items()) for row in rows if row]

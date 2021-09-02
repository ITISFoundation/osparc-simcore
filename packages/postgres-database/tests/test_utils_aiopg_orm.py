from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from simcore_postgres_database.models.scicrunch_resources import scicrunch_resources
from simcore_postgres_database.utils_aiopg_orm import BaseOrm


async def test_base_orm_usage(pg_engine: Engine):

    # This is an independent table
    class ScicrunchOrm(BaseOrm[str]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                scicrunch_resources,
                connection,
                readonly={"creation_date", "last_change_date"},
            )

    async with pg_engine.acquire() as conn:
        scicrunch_orm = ScicrunchOrm(conn)

        # insert 1 and 2
        scicrunch_id1 = await scicrunch_orm.insert(
            rrid="RRID:foo", name="foo", description="fooing"
        )
        assert scicrunch_id1 == "RRID:foo"

        scicrunch_id2 = await scicrunch_orm.insert(
            rrid="RRID:bar", name="bar", description="barring"
        )
        assert scicrunch_id2 == "RRID:bar"

        # fetch
        all_scicrunch_resources = await scicrunch_orm.fetchall()
        assert len(all_scicrunch_resources) == 2

        # pin
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

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any, NamedTuple

import pytest
import sqlalchemy as sa
from simcore_postgres_database.models.tags import tags
from simcore_postgres_database.utils_repos import (
    merge_jsonb_patch_expression,
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


async def test_sa_transactions(asyncpg_engine: AsyncEngine):
    #
    # SEE https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#synopsis-core
    #

    # READ query
    total_count_query = sa.select(sa.func.count()).select_from(tags)

    # WRITE queries
    query1 = tags.insert().values(id=2, name="query1", color="blue").returning(tags.c.id)
    query11 = tags.insert().values(id=3, name="query11", color="blue").returning(tags.c.id)
    query12 = tags.insert().values(id=5, name="query12", color="blue").returning(tags.c.id)
    query2 = tags.insert().values(id=6, name="query2", color="blue").returning(tags.c.id)
    query2 = tags.insert().values(id=7, name="query2", color="blue").returning(tags.c.id)

    async with asyncpg_engine.connect() as conn, conn.begin():  # starts transaction (savepoint)
        result = await conn.execute(query1)
        assert result.scalar() == 2

        total_count = (await conn.execute(total_count_query)).scalar()
        assert total_count == 1

        rows = (await conn.execute(tags.select().where(tags.c.id == 2))).fetchall()
        assert rows
        assert rows[0].id == 2

        async with conn.begin_nested():  # savepoint
            await conn.execute(query11)

            with pytest.raises(IntegrityError):
                async with conn.begin_nested():  # savepoint
                    await conn.execute(query11)

            await conn.execute(query12)

            total_count = (await conn.execute(total_count_query)).scalar()
            assert total_count == 3  # since query11 (second time) reverted!

        await conn.execute(query2)

        total_count = (await conn.execute(total_count_query)).scalar()
        assert total_count == 4


class _PageTuple(NamedTuple):
    total_count: int
    rows: list[dict[str, Any]]


class OneResourceRepoDemo:
    # This is a PROTOTYPE of how one could implement a generic
    # repo that provides CRUD operations providing a given table
    def __init__(self, engine: AsyncEngine, table: sa.Table):
        if "id" not in table.columns:
            msg = "id column expected"
            raise ValueError(msg)
        self.table = table

        self.engine = engine

    async def create(self, connection: AsyncConnection | None = None, **kwargs) -> int:
        async with transaction_context(self.engine, connection) as conn:
            result = await conn.execute(self.table.insert().values(**kwargs))
            assert result  # nosec
            return result.inserted_primary_key[0]

    async def get_by_id(
        self,
        connection: AsyncConnection | None = None,
        *,
        row_id: int,
    ) -> dict[str, Any] | None:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(sa.select(self.table).where(self.table.c.id == row_id))
            row = result.mappings().fetchone()
            return dict(row) if row else None

    async def get_page(
        self,
        connection: AsyncConnection | None = None,
        *,
        limit: int,
        offset: int = 0,
    ) -> _PageTuple:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            # Compute total count
            total_count_query = sa.select(sa.func.count()).select_from(self.table)
            total_count_result = await conn.execute(total_count_query)
            total_count = total_count_result.scalar()

            # Fetch paginated results
            query = sa.select(self.table).limit(limit).offset(offset)
            result = await conn.execute(query)
            rows = [dict(row) for row in result.mappings().fetchall()]

            return _PageTuple(total_count=total_count or 0, rows=rows)

    async def update(
        self,
        connection: AsyncConnection | None = None,
        *,
        row_id: int,
        **values,
    ) -> bool:
        async with transaction_context(self.engine, connection) as conn:
            result = await conn.execute(self.table.update().where(self.table.c.id == row_id).values(**values))
            return result.rowcount > 0

    async def delete(
        self,
        connection: AsyncConnection | None = None,
        *,
        row_id: int,
    ) -> bool:
        async with transaction_context(self.engine, connection) as conn:
            result = await conn.execute(self.table.delete().where(self.table.c.id == row_id))
            return result.rowcount > 0


async def test_oneresourcerepodemo_prototype(asyncpg_engine: AsyncEngine):
    tags_repo = OneResourceRepoDemo(engine=asyncpg_engine, table=tags)

    # create
    tag_id = await tags_repo.create(name="cyan tag", color="cyan")
    assert tag_id > 0

    # get, list
    tag = await tags_repo.get_by_id(row_id=tag_id)
    assert tag

    page = await tags_repo.get_page(limit=10)
    assert page.total_count == 1
    assert page.rows == [tag]

    # update
    ok = await tags_repo.update(row_id=tag_id, name="changed name")
    assert ok

    updated_tag = await tags_repo.get_by_id(row_id=tag_id)
    assert updated_tag
    assert updated_tag["name"] != tag["name"]

    # delete
    ok = await tags_repo.delete(row_id=tag_id)
    assert ok

    assert not await tags_repo.get_by_id(row_id=tag_id)


async def test_transaction_context(asyncpg_engine: AsyncEngine):
    # (1) Using transaction_context and fails
    fake_error_msg = "some error"

    def _something_raises_here():
        raise RuntimeError(fake_error_msg)

    tags_repo = OneResourceRepoDemo(engine=asyncpg_engine, table=tags)

    # using external transaction_context: commits upon __aexit__
    async with transaction_context(asyncpg_engine) as conn:
        await tags_repo.create(conn, name="cyan tag", color="cyan")
        await tags_repo.create(conn, name="red tag", color="red")
        assert (await tags_repo.get_page(conn, limit=10, offset=0)).total_count == 2

    # using internal: auto-commit
    await tags_repo.create(name="red tag", color="red")
    assert (await tags_repo.get_page(limit=10, offset=0)).total_count == 3

    # auto-rollback
    with pytest.raises(RuntimeError, match=fake_error_msg):  # noqa: PT012
        async with transaction_context(asyncpg_engine) as conn:
            await tags_repo.create(conn, name="violet tag", color="violet")
            assert (await tags_repo.get_page(conn, limit=10, offset=0)).total_count == 4
            _something_raises_here()

    assert (await tags_repo.get_page(limit=10, offset=0)).total_count == 3


# Stored JSONB values used as the starting point for the merge
_STORED_SQL_NULL = sa.cast(sa.null(), JSONB)
_STORED_JSON_NULL = sa.cast(sa.literal("null"), JSONB)
_STORED_OBJECT = sa.type_coerce({"position": {"x": 1, "y": 1}, "marker": {"color": "red"}}, JSONB)


async def _eval_merge(conn: AsyncConnection, *, stored: sa.ColumnElement, patch: dict[str, Any]) -> Any:
    # wraps `stored` as a column so the expression can be evaluated without a real table
    stored_column = sa.select(stored.label("value")).subquery()
    expr = merge_jsonb_patch_expression(stored_column.c.value, patch)
    result = await conn.execute(sa.select(expr))
    return result.scalar()


async def test_merge_jsonb_patch_sets_and_preserves_sibling_keys(
    asyncpg_engine: AsyncEngine,
):
    async with asyncpg_engine.connect() as conn:
        merged = await _eval_merge(conn, stored=_STORED_OBJECT, patch={"position": {"x": 9, "y": 9}})

    # patched key is overwritten, untouched sibling is preserved
    assert merged == {"position": {"x": 9, "y": 9}, "marker": {"color": "red"}}


async def test_merge_jsonb_patch_deletes_keys_mapped_to_none(
    asyncpg_engine: AsyncEngine,
):
    async with asyncpg_engine.connect() as conn:
        merged = await _eval_merge(conn, stored=_STORED_OBJECT, patch={"marker": None})

    assert merged == {"position": {"x": 1, "y": 1}}


async def test_merge_jsonb_patch_sets_and_deletes_in_one_patch(
    asyncpg_engine: AsyncEngine,
):
    async with asyncpg_engine.connect() as conn:
        merged = await _eval_merge(
            conn,
            stored=_STORED_OBJECT,
            patch={"position": {"x": 2, "y": 2}, "marker": None},
        )

    assert merged == {"position": {"x": 2, "y": 2}}


async def test_merge_jsonb_patch_deleting_absent_key_is_noop(
    asyncpg_engine: AsyncEngine,
):
    async with asyncpg_engine.connect() as conn:
        merged = await _eval_merge(conn, stored=_STORED_OBJECT, patch={"absent": None})

    assert merged == {"position": {"x": 1, "y": 1}, "marker": {"color": "red"}}


@pytest.mark.parametrize(
    "stored",
    [_STORED_SQL_NULL, _STORED_JSON_NULL],
    ids=["sql_null", "json_null"],
)
async def test_merge_jsonb_patch_treats_null_as_empty_object(asyncpg_engine: AsyncEngine, stored: sa.ColumnElement):
    async with asyncpg_engine.connect() as conn:
        merged = await _eval_merge(conn, stored=stored, patch={"position": {"x": 1, "y": 1}})

    assert merged == {"position": {"x": 1, "y": 1}}


async def test_merge_jsonb_patch_with_empty_patch_keeps_stored_value(
    asyncpg_engine: AsyncEngine,
):
    async with asyncpg_engine.connect() as conn:
        merged = await _eval_merge(conn, stored=_STORED_OBJECT, patch={})

    assert merged == {"position": {"x": 1, "y": 1}, "marker": {"color": "red"}}

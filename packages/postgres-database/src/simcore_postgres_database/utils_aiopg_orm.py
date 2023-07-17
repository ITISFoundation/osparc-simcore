"""
    BaseOrm: A draft and basic, yet practical, aiopg-based ORM to simplify operations with postgres database

    - Aims to hide the functionality of aiopg
    - Probably in the direction of the other more sophisticated libraries like (that we might adopt)
        - the new async sqlalchemy ORM https://docs.sqlalchemy.org/en/14/orm/
        - https://piccolo-orm.readthedocs.io/en/latest/index.html
"""
# pylint: disable=no-value-for-parameter

import functools
import operator
from typing import Any, Generic, TypeVar

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from sqlalchemy import func
from sqlalchemy.sql.base import ImmutableColumnCollection
from sqlalchemy.sql.dml import Insert, Update, UpdateBase
from sqlalchemy.sql.elements import literal_column
from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.selectable import Select

RowUId = TypeVar("RowUId", int, str)  # typically id or uuid


def _normalize(names: str | list[str] | None) -> list[str]:
    if not names:
        return []
    if isinstance(names, str):
        names = names.replace(",", " ").split()
    return list(map(str, names))


# Tokens for defaults
ALL_COLUMNS = f"{__name__}.ALL_COLUMNS"
PRIMARY_KEY = f"{__name__}.PRIMARY_KEY"

QueryT = TypeVar("QueryT", bound=UpdateBase)


class BaseOrm(Generic[RowUId]):
    def __init__(
        self,
        table: sa.Table,
        connection: SAConnection,
        *,
        readonly: set | None = None,
        writeonce: set | None = None,
    ):
        """
        :param readonly: read-only columns typically created in the server side, defaults to None
        :param writeonce: columns inserted once but that cannot be updated, defaults to None
        :raises ValueError: an error in any of the arguments
        """
        self._conn = connection
        self._readonly: set = readonly or {"created", "modified", "id"}
        self._writeonce: set = writeonce or set()

        # row selection logic
        self._where_clause: Any = None
        try:
            self._primary_key: Column = next(c for c in table.columns if c.primary_key)
            # FIXME: how can I compare a concrete with a generic type??
            # assert self._primary_key.type.python_type == RowUId  # nosec
        except StopIteration as e:
            raise ValueError(f"Table {table.name} MUST define a primary key") from e

        self._table = table

    def _compose_select_query(
        self,
        columns: str | list[str],
    ) -> Select:
        column_names: list[str] = _normalize(columns)

        if ALL_COLUMNS in column_names:
            query = self._table.select()
        elif PRIMARY_KEY in column_names:
            query = sa.select(
                [
                    self._primary_key,
                ]
            )
        else:
            query = sa.select(*[self._table.c[name] for name in column_names])

        return query

    def _append_returning(
        self, columns: str | list[str], query: QueryT
    ) -> tuple[QueryT, bool]:
        column_names: list[str] = _normalize(columns)

        is_scalar: bool = len(column_names) == 1

        if PRIMARY_KEY in column_names:
            # defaults to primery key
            query = query.returning(self._primary_key)

        elif ALL_COLUMNS in column_names:
            query = query.returning(literal_column("*"))
            is_scalar = False
            # NOTE: returning = self._table would also work. less efficient?
        else:
            # selection
            query = query.returning(*[self._table.c[name] for name in column_names])

        return query, is_scalar

    @staticmethod
    def _check_access_rights(access: set, values: dict) -> None:
        not_allowed: set[str] = access.intersection(values.keys())
        if not_allowed:
            raise ValueError(f"Columns {not_allowed} are read-only")

    @property
    def columns(self) -> ImmutableColumnCollection:
        return self._table.columns

    def set_filter(self, rowid: RowUId | None = None, **unique_id) -> "BaseOrm":
        """
        Sets default for read operations either by passing a row identifier or a filter
        """
        if unique_id and rowid:
            raise ValueError("Either identifier or unique condition but not both")

        if rowid is not None:
            self._where_clause = self._primary_key == rowid
        elif unique_id:
            self._where_clause = functools.reduce(
                operator.and_,
                (
                    operator.eq(self._table.columns[name], value)
                    for name, value in unique_id.items()
                ),
            )
        if not self.is_filter_set():
            raise ValueError(
                "Either identifier or unique condition required. None provided"
            )
        return self

    def clear_filter(self) -> None:
        self._where_clause = None

    def is_filter_set(self) -> bool:
        # WARNING: self._unique_match can evaluate false. Keep explicit
        return self._where_clause is not None

    async def fetch(
        self,
        returning_cols: str | list[str] = ALL_COLUMNS,
        *,
        rowid: RowUId | None = None,
    ) -> RowProxy | None:
        query = self._compose_select_query(returning_cols)
        if rowid:
            # overrides pinned row
            query = query.where(self._primary_key == rowid)
        elif self.is_filter_set():
            assert self._where_clause is not None  # nosec
            query = query.where(self._where_clause)

        result: ResultProxy = await self._conn.execute(query)
        row: RowProxy | None = await result.first()
        return row

    async def fetch_all(
        self,
        returning_cols: str | list[str] = ALL_COLUMNS,
    ) -> list[RowProxy]:
        query = self._compose_select_query(returning_cols)
        if self.is_filter_set():
            assert self._where_clause is not None  # nosec
            query = query.where(self._where_clause)

        result: ResultProxy = await self._conn.execute(query)
        rows: list[RowProxy] = await result.fetchall()
        return rows

    async def fetch_page(
        self,
        returning_cols: str | list[str] = ALL_COLUMNS,
        *,
        offset: int,
        limit: int | None = None,
        sort_by=None,
    ) -> tuple[list[RowProxy], int]:
        """Support for paginated fetchall

        IMPORTANT: pages are sorted by primary-key

        Returns limited list and total count
        """
        assert offset >= 0  # nosec
        assert limit is None or limit > 0  # nosec

        query = self._compose_select_query(returning_cols)

        if self.is_filter_set():
            assert self._where_clause is not None  # nosec
            query = query.where(self._where_clause)

        if sort_by is not None:
            query = query.order_by(sort_by)

        total_count = None
        if offset > 0 or limit is not None:
            # eval total count if pagination options enabled
            total_count = await self._conn.scalar(
                query.with_only_columns(func.count())
                .select_from(self._table)
                .order_by(None)
            )

        if offset:
            query = query.offset(offset)

        if limit is not None and limit > 0:
            query = query.limit(limit)

        result: ResultProxy = await self._conn.execute(query)

        if not total_count:
            total_count = result.rowcount
        assert total_count is not None  # nosec
        assert total_count >= 0  # nosec

        rows: list[RowProxy] = await result.fetchall()
        return rows, total_count

    async def update(
        self, returning_cols: str | list[str] = PRIMARY_KEY, **values
    ) -> RowUId | RowProxy | None:
        self._check_access_rights(self._readonly, values)
        self._check_access_rights(self._writeonce, values)

        query: Update = self._table.update().values(**values)
        if self.is_filter_set():
            assert self._where_clause is not None  # nosec
            query = query.where(self._where_clause)

        query, is_scalar = self._append_returning(returning_cols, query)
        if is_scalar:
            return await self._conn.scalar(query)

        result: ResultProxy = await self._conn.execute(query)
        row: RowProxy | None = await result.first()
        return row

    async def insert(
        self, returning_cols: str | list[str] = PRIMARY_KEY, **values
    ) -> RowUId | RowProxy | None:
        self._check_access_rights(self._readonly, values)

        query: Insert = self._table.insert().values(**values)

        query, is_scalar = self._append_returning(returning_cols, query)
        if is_scalar:
            return await self._conn.scalar(query)

        result: ResultProxy = await self._conn.execute(query)
        row: RowProxy | None = await result.first()
        return row

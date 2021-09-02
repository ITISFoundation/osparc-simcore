"""
    A very basic aiopg-based ORM to simplify operations with postgres database
"""
# pylint: disable=no-value-for-parameter

import functools
import operator
from typing import Dict, Generic, List, Optional, Set, TypeVar

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from sqlalchemy.sql.base import ImmutableColumnCollection

RowUId = TypeVar("RowUId", int, str)  # typically id or uuid


class BaseOrm(Generic[RowUId]):
    def __init__(
        self, table: sa.Table, connection: SAConnection, readonly: Optional[Set] = None
    ):
        self._conn = connection
        self._readonly: Set = readonly or {"created", "modified", "id"}

        # row selection logic
        self._unique_match = None
        try:
            self._primary_key = next(c for c in table.columns if c.primary_key)
            # TODO: assert this column's type is in RowUId?
        except StopIteration as e:
            raise ValueError(f"Table {table.name} MUST define a primary key") from e

        self._table = table

    def _compose_select_query(
        self,
        selection: Optional[str] = None,
    ):
        """
        selection: name/s of columns to select. None defaults to all of them
        """
        if selection is None:
            query = self._table.select()
        else:
            query = sa.select([self._table.c[name] for name in selection.split()])

        return query

    def _assert_readonly(self, values: Dict):
        not_allowed: Set[str] = self._readonly.intersection(values.keys())
        if not_allowed:
            raise ValueError(f"Columns {not_allowed} are read-only")

    @property
    def columns(self) -> ImmutableColumnCollection:
        return self._table.columns

    def pin_row(self, rowid: Optional[RowUId] = None, **unique_id) -> "BaseOrm":
        if unique_id and rowid:
            raise ValueError("Either identifier or unique condition but not both")

        if rowid:
            self._unique_match = self._primary_key == rowid
        elif unique_id:
            self._unique_match = functools.reduce(
                operator.and_,
                (
                    operator.eq(self._table.columns[name], value)
                    for name, value in unique_id.items()
                ),
            )
        if self._unique_match is None:
            raise ValueError(
                "Either identifier or unique condition required. None provided"
            )
        return self

    def unpin_row(self) -> None:
        self._unique_match = None

    async def fetch(
        self,
        selection: Optional[str] = None,
        *,
        rowid: Optional[RowUId] = None,
    ) -> Optional[RowProxy]:
        """
        selection: name of one or more columns to fetch. None defaults to all of them
        """
        query = self._compose_select_query(selection)
        if rowid:
            # overrides pinned row
            query = query.where(self._primary_key == rowid)
        elif self._unique_match is not None:
            # WARNING: self._unique_match can evaluate false. Keep explicit
            query = query.where(self._unique_match)

        result: ResultProxy = await self._conn.execute(query)
        row: Optional[RowProxy] = await result.first()
        return row

    async def fetchall(
        self,
        selection: Optional[str] = None,
    ) -> List[RowProxy]:
        query = self._compose_select_query(selection)

        result: ResultProxy = await self._conn.execute(query)
        rows: List[RowProxy] = await result.fetchall()
        return rows

    async def update(self, **values) -> Optional[RowUId]:
        self._assert_readonly(values)

        query = self._table.update().values(**values)
        if self._unique_match is not None:
            query = query.where(self._unique_match)
        query = query.returning(self._primary_key)

        return await self._conn.scalar(query)

    async def insert(self, **values) -> Optional[RowUId]:
        self._assert_readonly(values)

        query = self._table.insert().values(**values).returning(self._primary_key)

        return await self._conn.scalar(query)

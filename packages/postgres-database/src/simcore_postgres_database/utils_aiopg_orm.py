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
from typing import Dict, Generic, List, Optional, Set, TypeVar

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from sqlalchemy.sql.base import ImmutableColumnCollection

RowUId = TypeVar("RowUId", int, str)  # typically id or uuid


class BaseOrm(Generic[RowUId]):
    def __init__(
        self,
        table: sa.Table,
        connection: SAConnection,
        *,
        readonly: Optional[Set] = None,
        writeonce: Optional[Set] = None,
    ):
        self._conn = connection
        self._readonly: Set = readonly or {"created", "modified", "id"}
        self._writeonce: Set = (
            writeonce or set()
        )  # can be inserted once but not updated

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

    def _check_access_rights(self, access: Set, values: Dict):
        not_allowed: Set[str] = access.intersection(values.keys())
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
        if not self.is_pinned():
            raise ValueError(
                "Either identifier or unique condition required. None provided"
            )
        return self

    def unpin_row(self) -> None:
        self._unique_match = None

    def is_pinned(self) -> bool:
        # WARNING: self._unique_match can evaluate false. Keep explicit
        return self._unique_match is not None

    async def fetch(
        self,
        returning: Optional[str] = None,
        *,
        rowid: Optional[RowUId] = None,
    ) -> Optional[RowProxy]:
        """
        selection: name of one or more columns to fetch. None defaults to all of them
        """
        query = self._compose_select_query(returning)
        if rowid:
            # overrides pinned row
            query = query.where(self._primary_key == rowid)
        elif self.is_pinned():
            assert self._unique_match is not None  # nosec
            query = query.where(self._unique_match)

        result: ResultProxy = await self._conn.execute(query)
        row: Optional[RowProxy] = await result.first()
        return row

    async def fetchall(
        self,
        returned_selection: Optional[str] = None,
    ) -> List[RowProxy]:
        query = self._compose_select_query(returned_selection)

        result: ResultProxy = await self._conn.execute(query)
        rows: List[RowProxy] = await result.fetchall()
        return rows

    async def update(self, **values) -> Optional[RowUId]:
        # TODO: add returning. default to id and add constant for all
        self._check_access_rights(self._readonly, values)
        self._check_access_rights(self._writeonce, values)

        query = self._table.update().values(**values)
        if self.is_pinned():
            assert self._unique_match is not None  # nosec
            query = query.where(self._unique_match)
        query = query.returning(self._primary_key)

        return await self._conn.scalar(query)

    async def insert(self, **values) -> Optional[RowUId]:
        self._check_access_rights(self._readonly, values)

        query = self._table.insert().values(**values).returning(self._primary_key)

        return await self._conn.scalar(query)

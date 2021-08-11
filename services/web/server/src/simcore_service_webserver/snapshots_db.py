from typing import List, Optional
from uuid import UUID

from aiopg.sa.result import RowProxy
from pydantic import PositiveInt
from simcore_postgres_database.models.snapshots import snapshots

from .db_base_repository import BaseRepository

# alias for readability
# SEE https://pydantic-docs.helpmanual.io/usage/models/#orm-mode-aka-arbitrary-class-instances
SnapshotOrm = RowProxy


class SnapshotsRepository(BaseRepository):
    """
    Abstracts access to snapshots database table

    Gets primitive/standard parameters and returns valid orm objects
    """

    async def list(self, projec_uuid: UUID) -> List[SnapshotOrm]:
        result = []
        async with self.engine.acquire() as conn:
            stmt = (
                snapshots.select()
                .where(snapshots.c.parent_uuid == projec_uuid)
                .order_by(snapshots.c.child_index)
            )
            async for row in conn.execute(stmt):
                result.append(row)
        return result

    async def _get(self, stmt) -> Optional[SnapshotOrm]:
        async with self.engine.acquire() as conn:
            return await (await conn.execute(stmt)).first()

    async def get_by_index(
        self, project_uuid: UUID, snapshot_index: PositiveInt
    ) -> Optional[SnapshotOrm]:
        stmt = snapshots.select().where(
            (snapshots.c.parent_uuid == project_uuid)
            & (snapshots.c.child_index == snapshot_index)
        )
        return await self._get(stmt)

    async def get_by_name(
        self, project_uuid: UUID, snapshot_name: str
    ) -> Optional[SnapshotOrm]:
        stmt = snapshots.select().where(
            (snapshots.c.parent_uuid == project_uuid)
            & (snapshots.c.name == snapshot_name)
        )
        return await self._get(stmt)

    async def create(self, project_uuid: UUID) -> SnapshotOrm:
        pass

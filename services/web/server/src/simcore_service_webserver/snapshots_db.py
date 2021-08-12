from typing import Dict, List, Optional
from uuid import UUID

from aiohttp import web
from aiopg.sa.result import RowProxy
from pydantic import PositiveInt
from simcore_postgres_database.models.snapshots import snapshots

from .db_base_repository import BaseRepository
from .projects.projects_db import APP_PROJECT_DBAPI

# alias for readability
# SEE https://pydantic-docs.helpmanual.io/usage/models/#orm-mode-aka-arbitrary-class-instances
SnapshotRow = RowProxy
SnapshotDict = Dict

ProjectRow = RowProxy
ProjectDict = Dict


class SnapshotsRepository(BaseRepository):
    """
    Abstracts access to snapshots database table

    Gets primitive/standard parameters and returns valid orm objects
    """

    async def list(
        self, project_uuid: UUID, limit: Optional[int] = None
    ) -> List[SnapshotRow]:
        """ Returns sorted list of snapshots in project"""
        # TODO: add pagination

        async with self.engine.acquire() as conn:
            query = (
                snapshots.select()
                .where(snapshots.c.parent_uuid == str(project_uuid))
                .order_by(snapshots.c.id)
            )
            if limit and limit > 0:
                query = query.limit(limit)

            return await (await conn.execute(query)).fetchall()

    async def _first(self, query) -> Optional[SnapshotRow]:
        async with self.engine.acquire() as conn:
            return await (await conn.execute(query)).first()

    async def get_by_index(
        self, project_uuid: UUID, snapshot_index: PositiveInt
    ) -> Optional[SnapshotRow]:
        query = snapshots.select().where(
            (snapshots.c.parent_uuid == str(project_uuid))
            & (snapshots.c.child_index == snapshot_index)
        )
        return await self._first(query)

    async def get_by_name(
        self, project_uuid: UUID, snapshot_name: str
    ) -> Optional[SnapshotRow]:
        query = snapshots.select().where(
            (snapshots.c.parent_uuid == str(project_uuid))
            & (snapshots.c.name == snapshot_name)
        )
        return await self._first(query)

    async def create(self, snapshot: SnapshotDict) -> SnapshotRow:
        # pylint: disable=no-value-for-parameter
        query = snapshots.insert().values(**snapshot).returning(snapshots)
        row = await self._first(query)
        assert row  # nosec
        return row


class ProjectsRepository(BaseRepository):
    def __init__(self, request: web.Request):
        super().__init__(request)
        self._dbapi = request.config_dict[APP_PROJECT_DBAPI]

    async def create(self, project: ProjectDict):
        await self._dbapi.add_project(project, self.user_id, force_project_uuid=True)

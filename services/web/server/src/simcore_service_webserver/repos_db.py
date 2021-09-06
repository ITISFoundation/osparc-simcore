from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.result import RowProxy

from .db_base_repository import BaseRepository
from .projects.projects_db import APP_PROJECT_DBAPI
from .repos_models import Snapshot

# alias for readability
# SEE https://pydantic-docs.helpmanual.io/usage/models/#orm-mode-aka-arbitrary-class-instances
SnapshotRow = RowProxy
SnapshotDict = Dict

ProjectRow = RowProxy
ProjectDict = Dict


###################################################
# FIXME: some temporary placeholders until next PR
# from simcore_postgres_database.models.projects_snapshots import projects_snapshots

projects_snapshots: sa.Table


class TemporaryNoDatabaseSchemasAvailable(BaseRepository):
    def __init__(self, request: web.Request):
        super().__init__(request)
        raise NotImplementedError()


###################################################


class SnapshotsRepository(TemporaryNoDatabaseSchemasAvailable):
    """
    Abstracts access to snapshots database table

    Gets primitive/standard parameters and returns valid orm objects
    """

    async def list_all(
        self, project_uuid: UUID, limit: Optional[int] = None
    ) -> List[SnapshotRow]:
        """Returns sorted list of snapshots in project"""
        # TODO: add pagination

        async with self.engine.acquire() as conn:
            query = (
                projects_snapshots.select()
                .where(projects_snapshots.c.parent_uuid == str(project_uuid))
                .order_by(projects_snapshots.c.id)
            )
            if limit and limit > 0:
                query = query.limit(limit)

            return await (await conn.execute(query)).fetchall()

    async def _first(self, query) -> Optional[SnapshotRow]:
        async with self.engine.acquire() as conn:
            return await (await conn.execute(query)).first()

    async def get_by_name(
        self, project_uuid: UUID, snapshot_name: str
    ) -> Optional[SnapshotRow]:
        query = projects_snapshots.select().where(
            (projects_snapshots.c.parent_uuid == str(project_uuid))
            & (projects_snapshots.c.name == snapshot_name)
        )
        return await self._first(query)

    async def get_by_id(
        self, parent_uuid: UUID, snapshot_id: int
    ) -> Optional[SnapshotRow]:
        query = projects_snapshots.select().where(
            (projects_snapshots.c.parent_uuid == str(parent_uuid))
            & (projects_snapshots.c.id == snapshot_id)
        )
        return await self._first(query)

    async def get(
        self, parent_uuid: UUID, created_at: datetime
    ) -> Optional[SnapshotRow]:
        snapshot_project_uuid: UUID = Snapshot.compose_project_uuid(
            parent_uuid, created_at
        )
        query = projects_snapshots.select().where(
            (projects_snapshots.c.parent_uuid == str(parent_uuid))
            & (projects_snapshots.c.project_uuid == str(snapshot_project_uuid))
        )
        return await self._first(query)

    async def list_snapshot_names(self, parent_uuid: UUID) -> List[Tuple[str, int]]:
        query = (
            sa.select([projects_snapshots.c.name, projects_snapshots.c.id])
            .where(projects_snapshots.c.parent_uuid == str(parent_uuid))
            .order_by(projects_snapshots.c.id)
        )
        async with self.engine.acquire() as conn:
            return await (await conn.execute(query)).fetchall()

    async def create(self, snapshot: Snapshot) -> SnapshotRow:
        # pylint: disable=no-value-for-parameter
        query = (
            projects_snapshots.insert()
            .values(**snapshot.dict(by_alias=True, exclude={"id"}))
            .returning(projects_snapshots)
        )
        row = await self._first(query)
        assert row  # nosec
        return row


class ProjectsRepository(TemporaryNoDatabaseSchemasAvailable):
    def __init__(self, request: web.Request):
        super().__init__(request)
        self._dbapi = request.config_dict[APP_PROJECT_DBAPI]

    async def create(self, project: ProjectDict):
        await self._dbapi.add_project(project, self.user_id, force_project_uuid=True)

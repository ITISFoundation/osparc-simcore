"""

    TODO: generic version control abstraction applicable to version rows in any table
    - starts with versioning a given project, i.e. a row in a simcore_postgres_database.models.projects table

"""
# pylint: disable=no-value-for-parameter

import logging
from abc import ABC, abstractmethod
from typing import Callable, List, Optional
from uuid import UUID

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from sqlalchemy.sql.elements import not_

from .models.projects import projects
from .models.projects_repos import projects_checkpoints, projects_repos

log = logging.getLogger(__name__)


class ProjectRepository:
    # TODO: fetch row upon construction -> ORM?

    def __init__(self, repo_id: int, conn: SAConnection):
        self._repo_id = repo_id
        self._conn = conn

    @classmethod
    async def create_repo(
        cls, project_uuid: UUID, conn: SAConnection
    ) -> "ProjectRepository":
        query = sa.select([projects_repos.c.id]).where(
            projects_repos.c.project_uuid == project_uuid
        )
        repo_id = await conn.scalar(query)

        if repo_id is None:
            query = (
                projects_repos.insert()
                .values(project_uuid=project_uuid)
                .returning(projects_repos.c.id)
            )
            repo_id = await conn.scalar(query)
        assert repo_id is not None
        return ProjectRepository(repo_id, conn)

    @property
    def id(self) -> int:
        return self._repo_id

    async def fetch(self) -> RowProxy:
        query = projects_repos.select().where(projects_repos.c.id == self._repo_id)
        repo: Optional[RowProxy] = await (await self._conn.execute(query)).first()
        assert repo
        return repo

    async def _fetch_entrypoint(self, column_id) -> Optional[RowProxy]:
        query = sa.select(
            [
                column_id,
            ]
        ).where(projects_repos.c.id == self.id)
        if entrypoint_id := await self._conn.scalar(query):
            query = projects_checkpoints.select().where(
                projects_checkpoints.c.id == entrypoint_id
            )
            checkpoint: Optional[RowProxy] = await (
                await self._conn.execute(query)
            ).first()
            return checkpoint

    async def fetch_head(self) -> Optional[RowProxy]:
        # if exists, it is valid since ondelete="RESTRICT"
        head = await self._fetch_entrypoint(projects_repos.c.head_id)
        return head

    async def fetch_staging(self) -> Optional[RowProxy]:
        # if exists, it is valid since ondelete="RESTRICT"
        staging = await self._fetch_entrypoint(projects_repos.c.staging_id)
        return staging

    async def assert_unique_staging(self):

        if staging := await self.fetch_staging():
            query = projects_checkpoints.select().where(
                (projects_checkpoints.c.id == staging.id)
            )
            result: ResultProxy = await self._conn.execute(query)
            assert result.rowcount == 1

            checkpoint: Optional[RowProxy] = await result.first()
            assert checkpoint

            assert checkpoint.repo_id == self.id
            assert not checkpoint.parent
            assert not checkpoint.tag
            assert not checkpoint.message
        else:
            query = projects_checkpoints.select().where(
                (projects_checkpoints.c.repo_id == self._repo_id)
                & not_(projects_checkpoints.c.parent)
                & not_(projects_checkpoints.c.tag)
                & not_(projects_checkpoints.c.message)
            )
            result: ResultProxy = await self._conn.execute(query)
            assert result.rowcount == 0

    async def fetch_working_copy(self) -> RowProxy:
        #
        # TODO: optimize in a single call
        # SEE subqueries: https://docs.sqlalchemy.org/en/14/core/tutorial.html#using-aliases-and-subqueries
        #
        query = sa.select(
            [
                projects_repos.c.project_uuid,
            ]
        ).where((projects_repos.c.id == self.id))
        project_uuid = await self._conn.scalar(query)
        # non-nullable project_uuid
        assert project_uuid  # nosec

        query = projects.select().where(projects.c.uuid == project_uuid)
        project: Optional[RowProxy] = await (await self._conn.execute(query)).first()

        if not project:
            raise ValueError("Invalid repository {}")

        return project

    async def log(self) -> List[RowProxy]:
        query = (
            projects_checkpoints.select()
            .where((projects_checkpoints.c.repo_id == self.id))
            .order_by(projects_checkpoints.c.created)
        )

        checkpoints = await (await self._conn.execute(query)).fetchall()
        return checkpoints


SHA1Str = str


class VersionControlPolicy(ABC):

    # policies ---

    @abstractmethod
    def eval_checksum(self, item) -> SHA1Str:
        ...

    @abstractmethod
    async def clone_row_as_snapshot(
        self, data: RowProxy, repo_id: int, data_checksum: str, conn: SAConnection
    ):
        ...


async def add_to_staging(
    repo_id: int,
    conn: SAConnection,
    eval_checksum: Callable,
    clone_as_snapshot: Callable,
) -> RowProxy:
    """Adds project wc's changes to staging"""

    # fetch project
    repo = ProjectRepository(repo_id, conn)

    # fetch a *full copy* of the project
    project: RowProxy = await repo.fetch_working_copy()  # raises

    # eval checksum
    checksum = eval_checksum(project.workbench)

    # acquire snapshot_uuid
    checkpoint_id = None
    cleanup_query = None

    head = await repo.fetch_head()
    staging = await repo.fetch_staging()
    # if exists, it is valid since ondelete="RESTRICT"

    if staging:  # something in staging

        # wc and staging snapshot are identical?
        if staging.snapshot_checksum == checksum:
            checkpoint_id = staging.id

        else:  # invalidate staging
            checkpoint_id = None
            # eliminate snapshot entrypoint and project when new-one is in place!!!!
            # del project -> projects_checkpoints
            cleanup_query = projects.delete().where(
                projects.c.uuid == staging.snapshot_uuid
            )

    if checkpoint_id is None:  # create staging
        async with conn.begin():
            # clone it
            snapshot: RowProxy = await clone_as_snapshot(
                project, repo.id, checksum, conn
            )

            # update projects_checkpoints
            query = (
                projects_checkpoints.insert()
                .values(
                    repo_id=repo.id,
                    parent=head.id if head else None,
                    snapshot_checksum=checksum,
                    snapshot_uuid=snapshot.uuid,
                )
                .returning(projects_checkpoints.c.id)
            )
            checkpoint_id = await conn.scalar(query)

            # update new stagin
            query = (
                projects_repos.update()
                .where(projects_repos.c.id == repo_id)
                .values(staging_id=checkpoint_id)
            )
            await conn.execute(query)

            if cleanup_query:
                await conn.execute(cleanup_query)

    staging = await repo.fetch_staging()
    assert staging
    return staging


async def commit(repo_id: int, tag: str, message: str, conn: SAConnection) -> RowProxy:
    """Commit staging"""

    async with conn.begin():

        query = projects_repos.select().where(projects_repos.c.id == repo_id)
        repo: Optional[RowProxy] = await (await conn.execute(query)).first()

        assert repo
        assert repo.id == repo_id

        query = sa.select(
            [
                projects_checkpoints.c.snapshot_checksum,
                projects_checkpoints.c.snapshot_uuid,
            ]
        ).where(projects_checkpoints.c.id == repo.staging_id)
        staging: Optional[RowProxy] = await (await conn.execute(query)).first()

        if staging:
            async with conn.begin():
                query = (
                    projects_checkpoints.update()
                    .values(
                        repo_id=repo.id,
                        parent=repo.head_id,
                        tag=tag,
                        message=message,
                        # redundant
                        snapshot_checksum=staging.snapshot_checksum,
                        snapshot_uuid=staging.snapshot_uuid,
                    )
                    .returning(projects_checkpoints)
                )
                head_id = await conn.scalar(query)

                query = (
                    projects_repos.update()
                    .where(projects_repos.c.id == repo_id)
                    .values(head_id=head_id, staging_id=None)
                )
                await conn.execute(query)
        else:
            log.info("Nothing to commit, working tree clean")

        query = sa.select([projects_repos.c.head_id]).where(
            projects_repos.c.id == repo_id
        )
        head_id = await conn.scalar(query)
        assert head_id  # nosec
        # TODO: use sub-query
        query = projects_checkpoints.select().where(
            projects_checkpoints.c.id == head_id
        )
        checkpoint: Optional[RowProxy] = await (await conn.execute(query)).first()
        assert checkpoint  # nosec

        return checkpoint

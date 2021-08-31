# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from abc import ABC, abstractmethod
from collections import OrderedDict
from copy import deepcopy
from typing import Callable, List, Optional, Set, Tuple
from uuid import UUID, uuid3

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.projects import Workbench
from pydantic import constr
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.errors import UniqueViolation
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_repos import (
    projects_checkpoints,
    projects_repos,
)
from simcore_postgres_database.models.users import users
from sqlalchemy.sql.elements import not_
from sqlalchemy.sql.operators import is_

SHA1Str = str
EXCLUDE = {
    "id",
    "uuid",
    "creation_date",
    "last_change_date",
    "hidden",
    "published",
}


class SnapshotPolicy(ABC):
    @abstractmethod
    def eval_checksum(self, item) -> SHA1Str:
        ...

    @abstractmethod
    async def clone_as_snapshot(
        self, data: RowProxy, repo_id: int, data_checksum: str, conn: SAConnection
    ):
        ...


def eval_checksum(workbench) -> SHA1Str:
    # pipeline = OrderedDict((key, Node(**value)) for key, value in workbench.items())
    # FIXME:  implement checksum

    # NOTE: must capture changes in the workbnehc despite possible changes in the uuids
    return "1" * 40


async def clone_as_snapshot(
    project: RowProxy, repo_id: int, snapshot_checksum: str, conn: SAConnection
):
    # create project-snapshot
    snapshot = {c: deepcopy(project[c]) for c in project if c not in EXCLUDE}

    snapshot["name"] = f"snapshot.{repo_id}.{snapshot_checksum}"
    snapshot["uuid"] = snapshot_uuid = str(
        uuid3(UUID(project.uuid), f"{repo_id}.{snapshot_checksum}")
    )
    # creation_data = state of parent upon copy! WARNING: changes can be state changes and not project definition?
    snapshot["creation_date"] = project.last_change_date
    snapshot["hidden"] = True
    snapshot["published"] = False

    # NOTE: a snapshot has no results but workbench stores some states,
    #  - input hashes
    #  - node ids

    query = projects.insert().values(**snapshot).returning(projects)
    snapshot_project: Optional[RowProxy] = await (await conn.execute(query)).first()
    assert snapshot_project
    assert snapshot_project.uuid == snapshot_uuid
    return snapshot_project


class ProjectRepository:
    def __init__(self, repo_id: int, conn: SAConnection):
        self._repo_id = repo_id
        self._conn = conn

    @property
    def id(self) -> int:
        return self._repo_id

    async def _fetch_entrypoint(self, column_id) -> Optional[RowProxy]:
        query = sa.select(
            [
                column_id,
            ]
        ).where(projects_repos.c.repo_id == self.id)
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

        if staging_id := await self.fetch_staging():
            query = projects_checkpoints.select().where(
                (projects_checkpoints.c.id == staging_id)
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
                projects_repos.c.projects_uuid,
            ]
        ).where((projects_repos.c.repo_id == self.id))
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


async def add_to_staging(repo_id: int, conn: SAConnection):
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

    staging = await repo.fetch_staging()
    # if exists, it is valid since ondelete="RESTRICT"

    if staging:

        # wc and staging snapshot are identical?
        if staging.snapshot_checksum == checksum:
            checkpoint_id = staging.id

        else:
            checkpoint_id = None
            # eliminate snapshot entrypoint and project when new-one is in place!!!!
            # del project -> projects_checkpoints
            cleanup_query = projects.delete().where(
                projects.c.uuid == staging.snapshot_uuid
            )

    # Write ---

    if not checkpoint_id:
        async with conn.begin():
            # clone it
            snapshot: RowProxy = await clone_as_snapshot(
                project, repo.id, checksum, conn
            )

            # update staged in projects_checkpoints
            query = (
                projects_checkpoints.insert()
                .values(
                    repo_id=repo.id,
                    snapshot_checksum=checksum,
                    snapshot_uuid=snapshot.uuid,
                )
                .returning(projects_checkpoints.c.id)
            )
            checkpoint_id = await conn.scalar(query)

            # update projects_repos tables
            query = (
                projects_repos.update()
                .where(projects_repos.c.id == repo_id)
                .values(staging=checkpoint_id)
            )
            await conn.execute(query)

            if cleanup_query:
                await conn.execute(cleanup_query)

    else:
        #
        async with conn.begin():
            # update projects_repos tables
            query = (
                projects_repos.update()
                .where(projects_repos.c.id == repo_id)
                .values(staging=checkpoint_id)
            )
            await conn.execute(query)

            if cleanup_query:
                await conn.execute(cleanup_query)


async def commit_staging(repo_id: int, tag: str, message: str, conn: SAConnection):
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
        ).where(projects_checkpoints.c.id == repo.staging)
        staged: Optional[RowProxy] = await (await conn.execute(query)).first()

        assert staged

        if staged:
            head_id = await conn.scalar(
                projects_checkpoints.update()
                .values(
                    repo_id=repo.id,
                    parent=repo.head,
                    tag=tag,
                    message=message,
                    # redundant
                    snapshot_checksum=staged.staged_checksum,
                    snapshot_uuid=staged.staged_project_uuid,
                )
                .returning(projects_checkpoints.c.id)
            )

            await conn.execute(
                projects_repos.update()
                .where(projects_repos.c.id == repo_id)
                .values(head=head_id, staging=None)
            )
        else:
            print("WARNING: nothing staged")

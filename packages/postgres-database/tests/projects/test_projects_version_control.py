# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import functools
import hashlib
import json
import operator
from typing import List, Optional, Set, Union
from uuid import UUID, uuid3

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_snapshots import projects_snapshots
from simcore_postgres_database.models.projects_version_control import (
    projects_vc_branches,
    projects_vc_commits,
    projects_vc_repos,
    projects_vc_tags,
)

RowUId = Union[int, str]


class BaseOrm:
    def __init__(
        self, table: sa.Table, connection: SAConnection, readonly: Optional[Set] = None
    ):
        self._conn = connection
        self._readonly: Set = readonly or {"created", "modified", "id"}

        # row selection logic
        self._unique_match = None
        try:
            self._primary_key = next(c for c in table.columns if c.primary_key)
        except StopIteration as e:
            raise ValueError(f"Table {table.name} MUST define a primary key") from e

        self._table = table

    def _compose_select_query(
        self,
        selection: Optional[str] = None,
    ):
        """
        selection: name of one or more columns to fetch. None defaults to all of them
        """
        if selection is None:
            query = self._table.select()
        else:
            query = sa.select([self._table.c[name] for name in selection.split()])

        return query

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

    def unpin_row(self):
        self._unique_match = None

    async def fetch(
        self,
        selection: Optional[str] = None,
        rowid: Optional[RowUId] = None,
    ) -> Optional[RowProxy]:
        """
        selection: name of one or more columns to fetch. None defaults to all of them
        """
        query = self._compose_select_query(selection)
        if rowid:
            # overrides pinned row
            query = query.where(self._primary_key == rowid)
        elif self._unique_match:
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
        not_allowed = self._readonly.intersection(values.keys())
        if not_allowed:
            raise ValueError(f"Columns {not_allowed} are read-only")

        query = self._table.update().values(**values)
        if self._unique_match:
            query = query.where(self._unique_match)
        query = query.returning(self._primary_key)

        return await self._conn.scalar(query)

    async def insert(self, **values) -> Optional[RowUId]:
        not_allowed = self._readonly.intersection(values.keys())
        if not_allowed:
            raise ValueError(f"Columns {not_allowed} are read-only")

        query = self._table.insert().values(**values).returning(self._primary_key)

        return await self._conn.scalar(query)


# -------------------


async def test_basic_workflow(project: RowProxy, conn: SAConnection):
    # create repo
    repo_orm = BaseOrm(projects_vc_repos, conn)
    repo_id = await repo_orm.insert(project_uuid=project.uuid)
    assert repo_id is not None

    repo_orm.pin_row(repo_id)
    repo = await repo_orm.fetch()
    assert repo
    assert repo.project_uuid == project.uuid
    assert repo.branch_id is None
    assert repo.created == repo.modified

    # create main branch
    branch_orm = BaseOrm(projects_vc_branches, conn)
    branch_id = await branch_orm.insert(repo_id=repo.id)
    assert branch_id is not None

    branch_orm.pin_row(branch_id)
    main_branch: Optional[RowProxy] = await branch_orm.fetch()
    assert main_branch
    assert main_branch.name == "main", "Expected default"
    assert main_branch.head_commit_id is None
    assert main_branch.created == main_branch.modified

    # assign
    await repo_orm.update(branch_id=branch_id)
    repo = await repo_orm.fetch("created modified")
    assert repo
    assert repo.created < repo.modified

    # create first commit -- TODO: separate tests
    def eval_checksum(workbench):
        # FIXME: prototype
        block_string = json.dumps(workbench, sort_keys=True).encode("utf-8")
        raw_hash = hashlib.sha256(block_string)
        return raw_hash.hexdigest()

    # fetch a *full copy* of the project (WC)
    repo = await repo_orm.fetch("id project_uuid project_checksum branch_id")
    assert repo

    project_orm = BaseOrm(projects, conn).pin_row(uuid=repo.project_uuid)
    project_wc = await project_orm.fetch()
    assert project_wc
    assert project == project_wc

    # eval checksum
    checksum = eval_checksum(project_wc.workbench)
    assert repo.project_checksum != checksum

    # take snapshot = add & commit
    async with conn.begin():
        snapshot_orm = BaseOrm(projects_snapshots, conn)

        snapshot_checksum = checksum
        snapshot_uuid = str(
            uuid3(UUID(repo.project_uuid), f"{repo.id}.{snapshot_checksum}")
        )

        await snapshot_orm.insert(
            uuid=snapshot_uuid, workbench=project_wc.workbench, ui=project_wc.ui
        )

        # get HEAD = repo.branch_id -> .head_id
        branch_orm = BaseOrm(projects_vc_branches, conn).pin_row(repo.branch_id)
        branch = await branch_orm.fetch("head_commit_id name")
        assert branch
        assert branch.name == "main"

        # create commit
        commits_orm = BaseOrm(projects_vc_commits, conn)
        commit_id = await commits_orm.insert(
            repo_id=repo.id,
            parent_commit_id=branch.head_commit_id,
            snapshot_checksum=snapshot_checksum,
            snapshot_uuid=snapshot_uuid,
            message="first commit",
        )
        assert commit_id
        assert isinstance(commit_id, int)

        # update branch head
        await branch_orm.update(head_commit_id=commit_id)

        # update checksum cache
        await repo_orm.update(project_checksum=snapshot_checksum)

    # log history
    commits = await commits_orm.fetchall()
    assert len(commits) == 1
    assert commits[0].id == commit_id

    # tag
    tag_orm = BaseOrm(projects_vc_tags, conn)
    tag_id = await tag_orm.insert(
        repo_id=repo.id,
        commit_id=commit_id,
        name="v1",
    )
    assert tag_id is not None

    tag = await tag_orm.fetch(rowid=tag_id)
    assert tag
    assert tag.name == "v1"

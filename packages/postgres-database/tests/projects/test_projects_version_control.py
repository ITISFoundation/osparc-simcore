# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import functools
import hashlib
import json
import operator
from typing import Dict, List, Optional, Set, Union
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
)


class Orm:
    def __init__(
        self,
        table: sa.Table,
        connection: SAConnection,
        **pre_filter,  # typically used to pin identifiers e.g. id=33 or uuid=...
    ):
        self._table = table
        # NOTE: these could also be added on every call?
        self._conn = connection

        # makes a filter with identifiers
        self._pre_match = (
            functools.reduce(
                operator.and_,
                (
                    operator.eq(self._table.columns[name], value)
                    for name, value in pre_filter.items()
                ),
            )
            if pre_filter
            else None
        )
        # TODO: shall be configurable
        self._readonly: Set = {"created", "modified", "id"}

    def _fetch_query(
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

        if self._pre_match:
            query = query.where(self._pre_match)

        print(f"Query for {self._table.name}.{selection}:", query)
        return query

    async def fetch(
        self,
        selection: Optional[str] = None,
    ) -> Optional[RowProxy]:
        """
        selection: name of one or more columns to fetch. None defaults to all of them
        """
        query = self._fetch_query(selection)

        result: ResultProxy = await self._conn.execute(query)
        row: Optional[RowProxy] = await result.first()
        return row

    async def fetchall(
        self,
        selection: Optional[str] = None,
    ) -> List[RowProxy]:
        query = self._fetch_query(selection)

        result: ResultProxy = await self._conn.execute(query)
        rows: List[RowProxy] = await result.fetchall()
        return rows

    async def update(self, **values):
        not_allowed = self._readonly.intersection(values.keys())
        if not_allowed:
            raise ValueError(f"Columns {not_allowed} are read-only")

        query = self._table.update().values(**values)
        if self._pre_match:
            query = query.where(self._pre_match)

        await self._conn.execute(query)


# -------------------


async def test_basic_workflow(project: RowProxy, conn: SAConnection):
    # create repo
    query = (
        projects_vc_repos.insert()
        .values(project_uuid=project.uuid)
        .returning(projects_vc_repos.c.id)
    )
    repo_id: Optional[int] = await conn.scalar(query)
    assert repo_id is not None

    repo_orm = Orm(projects_vc_repos, conn, id=repo_id)

    repo = await repo_orm.fetch()
    assert repo
    assert repo.project_uuid == project.uuid
    assert repo.branch_id is None
    assert repo.created == repo.modified

    # create main branch
    query = (
        projects_vc_branches.insert()
        .values(repo_id=repo.id)
        .returning(projects_vc_branches.c.id)
    )
    branch_id: Optional[int] = await conn.scalar(query)
    assert branch_id is not None

    branch_orm = Orm(projects_vc_branches, conn, id=branch_id)

    main_branch: Optional[RowProxy] = await branch_orm.fetch()
    assert main_branch
    assert main_branch.name == "main", "Expected default"
    assert main_branch.head_commit_id is None
    assert main_branch.created == main_branch.modified

    # assign
    await conn.execute(projects_vc_repos.update().values(branch_id=branch_id))

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

    project_orm = Orm(projects, conn, uuid=repo.project_uuid)
    project_wc = await project_orm.fetch()
    assert project_wc
    assert project == project_wc

    # eval checksum
    checksum = eval_checksum(project_wc.workbench)
    assert repo.project_checksum != checksum

    # take snapshot
    async with conn.begin():
        snapshot_checksum = checksum
        snapshot_uuid = str(
            uuid3(UUID(repo.project_uuid), f"{repo.id}.{snapshot_checksum}")
        )

        query = projects_snapshots.insert().values(
            uuid=snapshot_uuid, workbench=project_wc.workbench, ui=project_wc.ui
        )
        await conn.execute(query)

        # get HEAD = repo.branch_id -> .head_id
        branch_orm = Orm(projects_vc_branches, conn, id=repo.branch_id)
        branch = await branch_orm.fetch("head_commit_id name")
        assert branch
        assert branch.name == "main"

        # create commit
        query = (
            projects_vc_commits.insert()
            .values(
                repo_id=repo.id,
                parent_commit_id=branch.head_commit_id,
                snapshot_checksum=snapshot_checksum,
                snapshot_uuid=snapshot_uuid,
                message="first commit",
            )
            .returning(projects_vc_commits.c.id)
        )
        commit_id = await conn.scalar(query)
        assert commit_id
        assert isinstance(commit_id, int)

        # update branch head
        await branch_orm.update(head_commit_id=commit_id)

        # update checksum cache
        await repo_orm.update(project_checksum=snapshot_checksum)

    # log history
    commits_orm = Orm(projects_vc_commits, conn)
    commits = await commits_orm.fetchall()
    assert len(commits) == 1
    assert commits[0].id == commit_id

    print("")

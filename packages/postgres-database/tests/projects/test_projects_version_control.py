# pylint: disable=no-value-for-parameter
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import functools
import operator
from typing import Optional

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from simcore_postgres_database.models.projects_version_control import (
    projects_vc_branches,
    projects_vc_repos,
)


class Orm:
    def __init__(
        self,
        table: sa.Table,
        connection: SAConnection,
        **indentifiers,  # typically id=33
    ):
        self._table = table
        self._conn = connection
        self._where_arg = functools.reduce(
            operator.and_,
            (
                operator.eq(self._table.columns[name], value)
                for name, value in indentifiers.items()
            ),
        )

    async def fetch(
        self,
        selection: Optional[str] = None,
    ) -> Optional[RowProxy]:
        """
        selection: name of one or more columns to fetch. None defaults to all of them
        """
        if selection is None:
            query = self._table.select()
        else:
            query = sa.select([self._table.c[name] for name in selection.split()])

        query = query.where(self._where_arg)

        print(f"query for {self._table.name}.{selection}:", query)

        result: ResultProxy = await self._conn.execute(query)
        row: Optional[RowProxy] = await result.first()
        return row


# -------------------


async def test_init_repo(project: RowProxy, conn: SAConnection):
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
    assert main_branch.head_id is None
    assert main_branch.created == main_branch.modified

    # assign
    await conn.execute(projects_vc_repos.update().values(branch_id=branch_id))

    repo = await repo_orm.fetch("created modified")
    assert repo
    assert repo.created < repo.modified

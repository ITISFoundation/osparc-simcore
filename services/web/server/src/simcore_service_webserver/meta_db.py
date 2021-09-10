import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import sqlalchemy as sa
from aiopg.sa import SAConnection
from aiopg.sa.result import RowProxy
from pydantic.types import NonNegativeInt, PositiveInt
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_version_control import (
    projects_vc_branches,
    projects_vc_commits,
    projects_vc_heads,
    projects_vc_repos,
    projects_vc_snapshots,
    projects_vc_tags,
)
from simcore_postgres_database.utils_aiopg_orm import BaseOrm

from .db_base_repository import BaseRepository
from .meta_models_repos import CommitLog, CommitProxy, TagProxy


def eval_checksum(workbench: Dict[str, Any]):
    # FIXME: prototype
    block_string = json.dumps(workbench, sort_keys=True).encode("utf-8")
    raw_hash = hashlib.sha256(block_string)
    return raw_hash.hexdigest()


class VersionControlRepository(BaseRepository):
    """
    db layer to access multiple tables within projects_version_control
    """

    class ReposOrm(BaseOrm[int]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                projects_vc_repos,
                connection,
                readonly={"id", "created", "modified"},
            )

    class BranchesOrm(BaseOrm[int]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                projects_vc_branches,
                connection,
                readonly={"id", "created", "modified"},
            )

    class CommitsOrm(BaseOrm[int]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                projects_vc_commits,
                connection,
                readonly={"id", "created", "modified"},
                # pylint: disable=no-member
                writeonce=set(c for c in projects_vc_commits.columns.keys()),
            )

    class TagsOrm(BaseOrm[int]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                projects_vc_tags,
                connection,
                readonly={"id", "created", "modified"},
            )

    class ProjectsOrm(BaseOrm[str]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                projects,
                connection,
                readonly={"id", "creation_date", "last_change_date"},
                writeonce={"uuid"},
            )

    class SnapshotsOrm(BaseOrm[str]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                projects_vc_snapshots,
                connection,
                writeonce={"checksum"},  # TODO:  all? cannot delete snapshots?
            )

    class HeadsOrm(BaseOrm[int]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                projects_vc_heads,
                connection,
                writeonce={"repo_id"},
            )

    # ------------

    async def list_repos(
        self,
        offset: NonNegativeInt = 0,
        limit: Optional[PositiveInt] = None,
    ) -> Tuple[List[RowProxy], NonNegativeInt]:

        async with self.engine.acquire() as conn:
            repo_orm = self.ReposOrm(conn)

            rows: List[RowProxy]
            rows, total_count = await repo_orm.fetch_page(
                "project_uuid", offset=offset, limit=limit
            )

            return rows, total_count

    async def get_repo_id(self, project_uuid: UUID) -> Optional[int]:
        async with self.engine.acquire() as conn:
            stmt = (
                sa.select([projects_vc_repos.c.id])
                .select()
                .where(projects_vc_repos.c.project_uuid == str(project_uuid))
            )
            repo_id: Optional[int] = await conn.scalar(stmt)
            return repo_id

    async def init_repo(self, project_uuid: UUID) -> int:
        async with self.engine.acquire() as conn:

            async with conn.begin():
                # create repo
                repo_orm = self.ReposOrm(conn)
                repo_id = await repo_orm.insert(project_uuid=str(project_uuid))
                assert repo_id is not None  # nosec
                assert isinstance(repo_id, int)  # nosec

                repo = await repo_orm.fetch(rowid=repo_id)
                assert repo  # nosec

                # create main branch
                branches_orm = self.BranchesOrm(conn)
                branch_id = await branches_orm.insert(repo_id=repo.id)
                assert branch_id is not None
                assert isinstance(branch_id, int)  # nosec

                main_branch: Optional[RowProxy] = await branches_orm.fetch(
                    rowid=branch_id
                )
                assert main_branch  #  nosec
                assert main_branch.name == "main"  # nosec

                # assign head branch
                heads_orm = self.HeadsOrm(conn)
                await heads_orm.insert(repo_id=repo.id, head_branch_id=branch_id)

                return repo_id

    async def _get_HEAD(self, repo_id: int, conn: SAConnection) -> Optional[RowProxy]:
        """Returns None if detached head"""
        h = await self.HeadsOrm(conn).fetch("head_branch_id", rowid=repo_id)
        if h and h.head_branch_id:
            branches_orm = self.BranchesOrm(conn).set_default(row_id=h.head_branch_id)
            branch = await branches_orm.fetch("id name head_commit_id")
            return branch

    async def get_head_commit(self, repo_id: int) -> Optional[RowProxy]:
        async with self.engine.acquire() as conn:
            return await self._get_HEAD(repo_id, conn)

    async def commit(
        self, repo_id: int, tag: Optional[str] = None, message: Optional[str] = None
    ) -> int:
        """add changes, commits and tags (if tag is not None)

        Message is added to tag if set otherwise to commit
        """

        async with self.engine.acquire() as conn:
            # FIXME: get head commit in one execution

            # get head commit
            branch = await self._get_HEAD(repo_id, conn)
            if not branch:
                raise NotImplementedError("Detached heads still not implemented")

            branches_orm = self.BranchesOrm(conn).set_default(row_id=branch.id)

            async with conn.begin():
                commits_orm = self.CommitsOrm(conn)
                head_commit = await commits_orm.fetch(
                    "id snapshot_checksum", rowid=branch.head_commit_id
                )
                assert head_commit  # nosec

                # assume no changes => same commit
                commit_id = head_commit.id

                # take a snapshot if needed
                if snapshot_checksum := await self._add_changes(
                    repo_id, head_commit.snapshot_checksum, conn
                ):
                    # commit new snapshot in history
                    commit_id = await commits_orm.insert(
                        repo_id=repo_id,
                        parent_commit_id=head_commit.id,
                        message=None if tag else message,
                        snapshot_checksum=snapshot_checksum,
                    )
                    assert commit_id

                    # updates head/branch
                    await branches_orm.update(head_commit_id=commit_id)

                # tag it (again)
                if tag:
                    await self.TagsOrm(conn).upsert(
                        repo_id=repo_id,
                        commit_id=commit_id,
                        name=tag,
                        message=message,
                        hidden=False,
                    )

            assert isinstance(commit_id, int)
            return commit_id

    async def _add_changes(
        self, repo_id: int, previous_checksum, conn
    ) -> Optional[str]:
        """
        Snapshots current working copy and evals checksum
        Returns checksum if a snapshot is taken because it has changes wrt previous commit
        """
        # current repo
        repo_orm = self.ReposOrm(conn).set_default(id=repo_id)
        repo = await repo_orm.fetch("id project_uuid project_checksum modified")
        assert repo  #  nosec

        # fetch project
        project_orm = self.ProjectsOrm(conn).set_default(uuid=repo.project_uuid)
        project = await project_orm.fetch("workbench ui last_change_date")
        assert project  # nosec

        checksum = repo.project_checksum
        if not checksum or (checksum and repo.modified < project.last_change_date):
            checksum = eval_checksum(project.workbench)
            await repo_orm.update(project_checksum=checksum)

        if checksum != previous_checksum:
            # has changes wrt previous commit
            snapshot_orm = self.SnapshotsOrm(conn).set_default(rowid=checksum)
            # if exists, ui might change
            await snapshot_orm.upsert(
                checksum=checksum,
                content={"workbench": project.workbench, "ui": project.ui},
            )
            return checksum

        # no changes
        return None

    async def get_commit_info(self, commit_id: int) -> CommitLog:
        async with self.engine.acquire() as conn:
            commit = await self.CommitsOrm(conn).fetch(rowid=commit_id)
            if commit:
                assert isinstance(commit, RowProxy)  # nosec

                tags: List[TagProxy] = (
                    await self.TagsOrm(conn)
                    .set_default(commit_id=commit.id, hidden=False)
                    .fetch_all("name message")
                )
                return commit, tags
            raise ValueError(f"Invalid commit {commit_id}")

    async def log(
        self,
        repo_id: int,
        offset: NonNegativeInt = 0,
        limit: Optional[PositiveInt] = None,
    ) -> Tuple[List[CommitLog], NonNegativeInt]:

        async with self.engine.acquire() as conn:
            commits_orm = self.CommitsOrm(conn).set_default(repo_id=repo_id)
            tags_orm = self.TagsOrm(conn)

            commits: List[CommitProxy]
            commits, total_count = await commits_orm.fetch_page(
                "project_uuid",
                offset=offset,
                limit=limit,
                order=sa.desc(commits_orm.columns["created"]),
            )

            infos = []
            for commit in commits:
                tags: List[TagProxy]
                tags = await tags_orm.set_default(commit_id=commit.id).fetch_all()
                infos.append((commit, tags))

            return infos, total_count

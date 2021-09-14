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
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .db_base_repository import BaseRepository
from .meta_models_repos import CommitLog, CommitProxy, SHA1Str, TagProxy


def eval_checksum(workbench: Dict[str, Any]) -> SHA1Str:
    # FIXME: dump workbench correctly (i.e. spaces, quotes ... -indepenent)
    block_string = json.dumps(workbench, sort_keys=True).encode("utf-8")
    raw_hash = hashlib.sha1(block_string)
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
            repo_orm = self.ReposOrm(conn).set_filter(project_uuid=str(project_uuid))
            repo = await repo_orm.fetch("id")
            return repo.id if repo else None

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
            branches_orm = self.BranchesOrm(conn).set_filter(rowid=h.head_branch_id)
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

            branches_orm = self.BranchesOrm(conn).set_filter(rowid=branch.id)

            async with conn.begin():
                commits_orm = self.CommitsOrm(conn)
                head_commit = await commits_orm.fetch(
                    "id snapshot_checksum", rowid=branch.head_commit_id
                )

                previous_checksum = ""
                commit_id = None
                if head_commit:
                    previous_checksum = (head_commit.snapshot_checksum,)
                    commit_id = head_commit.id

                # take a snapshot if needed
                if snapshot_checksum := await self._add_changes(
                    repo_id, previous_checksum, conn
                ):
                    # commit new snapshot in history
                    commit_id = await commits_orm.insert(
                        repo_id=repo_id,
                        parent_commit_id=commit_id,
                        message=None if tag else message,
                        snapshot_checksum=snapshot_checksum,
                    )
                    assert commit_id  # nosec

                    # updates head/branch
                    await branches_orm.update(head_commit_id=commit_id)

                # tag it (again)
                if tag:
                    insert_stmt = pg_insert(projects_vc_tags).values(
                        repo_id=repo_id,
                        commit_id=commit_id,
                        name=tag,
                        message=message,
                        hidden=False,
                    )
                    upsert_tag = insert_stmt.on_conflict_do_update(
                        constraint="repo_tag_uniqueness",
                        set_=dict(message=insert_stmt.excluded.message),
                    )
                    await conn.execute(upsert_tag)

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
        repo_orm = self.ReposOrm(conn).set_filter(id=repo_id)
        repo = await repo_orm.fetch("id project_uuid project_checksum modified")
        assert repo  #  nosec

        # fetch project
        project_orm = self.ProjectsOrm(conn).set_filter(uuid=repo.project_uuid)
        project = await project_orm.fetch("workbench ui last_change_date")
        assert project  # nosec

        checksum = repo.project_checksum
        if not checksum or (checksum and repo.modified < project.last_change_date):
            checksum = eval_checksum(project.workbench)
            await repo_orm.update(project_checksum=checksum)

        if checksum != previous_checksum:
            # has changes wrt previous commit
            # if exists, ui might change
            insert_stmt = pg_insert(projects_vc_snapshots).values(
                checksum=checksum,
                content={"workbench": project.workbench, "ui": project.ui},
            )
            upsert_snapshot = insert_stmt.on_conflict_do_update(
                constraint=projects_vc_snapshots.primary_key,
                set_=dict(content=insert_stmt.excluded.content),
            )
            await conn.execute(upsert_snapshot)
            return checksum

        # no changes
        return None

    async def get_commit_log(self, commit_id: int) -> CommitLog:
        async with self.engine.acquire() as conn:
            commit = await self.CommitsOrm(conn).fetch(rowid=commit_id)
            if commit:
                assert isinstance(commit, RowProxy)  # nosec

                tags: List[TagProxy] = (
                    await self.TagsOrm(conn)
                    .set_filter(commit_id=commit.id, hidden=False)
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
            commits_orm = self.CommitsOrm(conn).set_filter(repo_id=repo_id)
            tags_orm = self.TagsOrm(conn)

            commits: List[CommitProxy]
            commits, total_count = await commits_orm.fetch_page(
                offset=offset,
                limit=limit,
                order=sa.desc(commits_orm.columns["created"]),
            )

            logs = []
            for commit in commits:
                tags: List[TagProxy]
                tags = await tags_orm.set_filter(commit_id=commit.id).fetch_all()
                logs.append((commit, tags))

            return logs, total_count

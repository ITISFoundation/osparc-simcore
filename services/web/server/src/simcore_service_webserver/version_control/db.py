import json
import logging
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa
from aiopg.sa import SAConnection
from aiopg.sa.result import RowProxy
from common_library.json_serialization import json_dumps
from models_library.basic_types import SHA1Str
from models_library.projects import ProjectIDStr
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

from ..db.base_repository import BaseRepository
from ..projects.models import ProjectProxy
from .errors import (
    CleanRequiredError,
    InvalidParameterError,
    NoCommitError,
    NotFoundError,
)
from .models import HEAD, CommitID, CommitLog, CommitProxy, RefID, RepoProxy, TagProxy
from .vc_changes import compute_workbench_checksum
from .vc_tags import parse_workcopy_project_tag_name

_logger = logging.getLogger(__name__)


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
                writeonce={
                    c for c in projects_vc_commits.columns.keys() if c != "message"
                },
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
                writeonce={"checksum"},
            )

    class HeadsOrm(BaseOrm[int]):
        def __init__(self, connection: SAConnection):
            super().__init__(
                projects_vc_heads,
                connection,
                writeonce={"repo_id"},
            )

    # ------------

    async def _get_head_branch(
        self, repo_id: int, conn: SAConnection
    ) -> RowProxy | None:
        if h := await self.HeadsOrm(conn).fetch("head_branch_id", rowid=repo_id):
            branch = (
                await self.BranchesOrm(conn)
                .set_filter(id=h.head_branch_id)
                .fetch("id name head_commit_id")
            )
            return branch
        return None

    async def _get_HEAD_commit(
        self, repo_id: int, conn: SAConnection
    ) -> CommitProxy | None:
        if branch := await self._get_head_branch(repo_id, conn):
            commit = (
                await self.CommitsOrm(conn).set_filter(id=branch.head_commit_id).fetch()
            )
            return commit
        return None

    async def _fetch_workcopy_project_id(
        self, repo_id: int, commit_id: int, conn: SAConnection
    ) -> ProjectIDStr:
        # commit has a workcopy associated?
        found = (
            await self.TagsOrm(conn).set_filter(commit_id=commit_id).fetch_all("name")
        )
        for tag in found:
            if workcopy_project_id := parse_workcopy_project_tag_name(tag.name):
                return ProjectIDStr(workcopy_project_id)

        repo = await self.ReposOrm(conn).set_filter(id=repo_id).fetch("project_uuid")
        assert repo  # nosec
        return cast(ProjectIDStr, repo.project_uuid)

    async def _update_state(
        self, repo_id: int, conn: SAConnection
    ) -> tuple[RepoProxy, CommitProxy | None, ProjectProxy]:
        head_commit: CommitProxy | None = await self._get_HEAD_commit(repo_id, conn)

        # current repo
        repo_orm = self.ReposOrm(conn).set_filter(id=repo_id)
        returning_cols = "id project_uuid project_checksum modified"
        repo = await repo_orm.fetch(returning_cols)
        assert repo  #  nosec

        # fetch working copy
        workcopy_project_id = await self._fetch_workcopy_project_id(
            repo_id, head_commit.id if head_commit else -1, conn
        )
        workcopy_project = (
            await self.ProjectsOrm(conn)
            .set_filter(uuid=workcopy_project_id)
            .fetch("last_change_date workbench ui uuid")
        )
        assert workcopy_project  # nosec

        # uses checksum cached in repo table to avoid re-computing checksum
        checksum: SHA1Str | None = repo.project_checksum
        if not checksum or (
            checksum and repo.modified < workcopy_project.last_change_date
        ):
            checksum = compute_workbench_checksum(workcopy_project.workbench)

            repo = await repo_orm.update(returning_cols, project_checksum=checksum)
            assert repo
        return repo, head_commit, workcopy_project

    @staticmethod
    async def _upsert_snapshot(
        project_checksum: str,
        project: RowProxy | SimpleNamespace,
        conn: SAConnection,
    ):
        # has changes wrt previous commit
        assert project_checksum  # nosec
        insert_stmt = pg_insert(projects_vc_snapshots).values(
            checksum=project_checksum,
            content={
                "workbench": json.loads(json_dumps(project.workbench)),
                "ui": json.loads(json_dumps(project.ui)),
            },
        )
        upsert_snapshot = insert_stmt.on_conflict_do_update(
            constraint=projects_vc_snapshots.primary_key,
            set_=dict(content=insert_stmt.excluded.content),
        )
        await conn.execute(upsert_snapshot)

    # PUBLIC

    async def list_repos(
        self,
        offset: NonNegativeInt = 0,
        limit: PositiveInt | None = None,
    ) -> tuple[list[RowProxy], NonNegativeInt]:
        async with self.engine.acquire() as conn:
            repo_orm = self.ReposOrm(conn)

            rows: list[RowProxy]
            rows, total_count = await repo_orm.fetch_page(
                "project_uuid", offset=offset, limit=limit
            )

            return rows, total_count

    async def get_repo_id(self, project_uuid: UUID) -> int | None:
        async with self.engine.acquire() as conn:
            repo_orm = self.ReposOrm(conn).set_filter(project_uuid=str(project_uuid))
            repo = await repo_orm.fetch("id")
            return int(repo.id) if repo else None

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

                main_branch: RowProxy | None = await branches_orm.fetch(rowid=branch_id)
                assert main_branch  #  nosec
                assert main_branch.name == "main"  # nosec

                # assign head branch
                heads_orm = self.HeadsOrm(conn)
                await heads_orm.insert(repo_id=repo.id, head_branch_id=branch_id)

                return repo_id

    async def commit(
        self, repo_id: int, tag: str | None = None, message: str | None = None
    ) -> int:
        """add changes, commits and tags (if tag is not None)

        Message is added to tag if set otherwise to commit
        """
        if tag in ["HEAD", HEAD]:
            raise InvalidParameterError(name="tag", reason="is a reserved word")

        async with self.engine.acquire() as conn:
            # get head branch
            branch = await self._get_head_branch(repo_id, conn)
            if not branch:
                raise NotImplementedError("Detached heads still not implemented")

            _logger.info("On branch %s", branch.name)

            # get head commit
            repo, head_commit, workcopy_project = await self._update_state(
                repo_id, conn
            )

            if head_commit is None:
                previous_checksum = None
                commit_id = None
            else:
                previous_checksum = head_commit.snapshot_checksum
                commit_id = head_commit.id

            async with conn.begin():
                # take a snapshot if changes
                if repo.project_checksum != previous_checksum:
                    await self._upsert_snapshot(
                        repo.project_checksum, workcopy_project, conn
                    )

                    # commit new snapshot in history
                    commit_id = await self.CommitsOrm(conn).insert(
                        repo_id=repo_id,
                        parent_commit_id=commit_id,
                        message=message,
                        snapshot_checksum=repo.project_checksum,
                    )
                    assert commit_id  # nosec

                    # updates head/branch to this commit
                    await self.BranchesOrm(conn).set_filter(id=branch.id).update(
                        head_commit_id=commit_id
                    )

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
                            set_=dict(name=insert_stmt.excluded.name),
                        )
                        await conn.execute(upsert_tag)
                else:
                    _logger.info("Nothing to commit, working tree clean")

            assert isinstance(commit_id, int)  # nosec
            return commit_id

    async def get_commit_log(self, commit_id: int) -> CommitLog:
        async with self.engine.acquire() as conn:
            commit = await self.CommitsOrm(conn).fetch(rowid=commit_id)
            if commit:
                assert isinstance(commit, RowProxy)  # nosec

                tags: list[TagProxy] = (
                    await self.TagsOrm(conn)
                    .set_filter(commit_id=commit.id, hidden=False)
                    .fetch_all("name message")
                )
                return commit, tags
            raise NotFoundError(name="commit", value=commit_id)

    async def log(
        self,
        repo_id: int,
        offset: NonNegativeInt = 0,
        limit: PositiveInt | None = None,
    ) -> tuple[list[CommitLog], NonNegativeInt]:
        async with self.engine.acquire() as conn:
            commits_orm = self.CommitsOrm(conn).set_filter(repo_id=repo_id)
            tags_orm = self.TagsOrm(conn)

            commits: list[CommitProxy]
            commits, total_count = await commits_orm.fetch_page(
                offset=offset,
                limit=limit,
                sort_by=sa.desc(commits_orm.columns["created"]),
            )

            logs = []
            for commit in commits:
                tags: list[TagProxy]
                tags = await tags_orm.set_filter(commit_id=commit.id).fetch_all()
                logs.append((commit, tags))

            return logs, total_count

    async def update_annotations(
        self,
        repo_id: int,
        commit_id: CommitID,
        message: str | None = None,
        tag_name: str | None = None,
    ):
        async with self.engine.acquire() as conn:
            async with conn.begin():
                if message:
                    await self.CommitsOrm(conn).set_filter(id=commit_id).update(
                        message=message
                    )

                if tag_name:
                    tag = (
                        await self.TagsOrm(conn)
                        .set_filter(repo_id=repo_id, commit_id=commit_id, hidden=False)
                        .fetch("id")
                    )

                    if tag:
                        await self.TagsOrm(conn).set_filter(rowid=tag.id).update(
                            name=tag_name
                        )

    async def as_repo_and_commit_ids(
        self, project_uuid: UUID, ref_id: RefID
    ) -> tuple[int, CommitID]:
        """Translates (project-uuid, ref-id) to (repo-id, commit-id)

        :return: tuple with repo and commit identifiers
        """
        async with self.engine.acquire() as conn:
            repo = (
                await self.ReposOrm(conn)
                .set_filter(project_uuid=str(project_uuid))
                .fetch("id")
            )
            commit_id = None
            if repo:
                if ref_id == HEAD:
                    commit = await self._get_HEAD_commit(repo.id, conn)
                    if commit:
                        commit_id = commit.id
                elif isinstance(ref_id, CommitID):
                    commit_id = ref_id
                else:
                    assert isinstance(ref_id, str)  # nosec
                    # head branch or tag
                    raise NotImplementedError(
                        f"WIP: Tag or head branches as ref_id={ref_id}"
                    )

            if not commit_id or not repo:
                raise NotFoundError(
                    name="project {project_uuid} reference", value=ref_id
                )

            return repo.id, commit_id

    async def checkout(self, repo_id: int, commit_id: int) -> int:
        """checks out working copy of project_uuid to commit ref_id

        :raises RuntimeError: if local copy has changes (i.e. dirty)
        :return: commit id
        :rtype: int
        """
        async with self.engine.acquire() as conn:
            repo, head_commit, workcopy_project = await self._update_state(
                repo_id, conn
            )

            if head_commit is None:
                raise NoCommitError(
                    details="Cannot checkout without commit changes first"
                )

            # check if working copy has changes, if so, fail
            if repo.project_checksum != head_commit.snapshot_checksum:
                raise CleanRequiredError(
                    details="Your local changes would be overwritten by checkout. "
                    "Cannot checkout without commit changes first."
                )

            # already in head commit
            if head_commit.id == commit_id:
                return commit_id

            async with conn.begin():
                commit = (
                    await self.CommitsOrm(conn)
                    .set_filter(id=commit_id)
                    .fetch("snapshot_checksum")
                )
                assert commit  # nosec

                # restores project snapshot ONLY if main workcopy project
                if workcopy_project.uuid == repo.project_uuid:
                    snapshot = (
                        await self.SnapshotsOrm(conn)
                        .set_filter(commit.snapshot_checksum)
                        .fetch("content")
                    )
                    assert snapshot  # nosec

                    await self.ProjectsOrm(conn).set_filter(
                        uuid=repo.project_uuid
                    ).update(**snapshot.content)

                # create detached branch that points to (repo_id, commit_id)
                # upsert "detached" branch
                insert_stmt = (
                    pg_insert(projects_vc_branches)
                    .values(
                        repo_id=repo_id,
                        head_commit_id=commit_id,
                        name=f"{commit_id}-DETACHED",
                    )
                    .returning(projects_vc_branches.c.id)
                )
                upsert_tag = insert_stmt.on_conflict_do_update(
                    constraint="repo_branch_uniqueness",
                    set_=dict(head_commit_id=insert_stmt.excluded.head_commit_id),
                )
                branch_id = await conn.scalar(upsert_tag)

                # updates head
                await self.HeadsOrm(conn).set_filter(repo_id=repo_id).update(
                    head_branch_id=branch_id
                )

        return commit_id

    async def get_snapshot_content(
        self, repo_id: int, commit_id: int
    ) -> dict[str, Any]:
        async with self.engine.acquire() as conn:
            if (
                commit := await self.CommitsOrm(conn)
                .set_filter(repo_id=repo_id, id=commit_id)
                .fetch("snapshot_checksum")
            ):
                if (
                    snapshot := await self.SnapshotsOrm(conn)
                    .set_filter(checksum=commit.snapshot_checksum)
                    .fetch("content")
                ):
                    content: dict[str, Any] = snapshot.content
                    return content

        raise NotFoundError(name="snapshot for commit", value=(repo_id, commit_id))

    async def get_workbench_view(self, repo_id: int, commit_id: int) -> dict[str, Any]:
        async with self.engine.acquire() as conn:
            if (
                commit := await self.CommitsOrm(conn)
                .set_filter(repo_id=repo_id, id=commit_id)
                .fetch("snapshot_checksum")
            ):
                repo = (
                    await self.ReposOrm(conn)
                    .set_filter(id=repo_id)
                    .fetch("project_uuid")
                )
                assert repo  # nosec

                # if snapshot differs from workcopy, then show working copy
                workcopy_project_id = await self._fetch_workcopy_project_id(
                    repo_id, commit_id, conn
                )

                # NOTE: For the moment, all wcopies except for the repo's main workcopy
                # (i.e. repo.project_uuid) are READ-ONLY
                if workcopy_project_id != repo.project_uuid:
                    if project := (
                        await self.ProjectsOrm(conn)
                        .set_filter(uuid=workcopy_project_id)
                        .fetch("workbench ui")
                    ):
                        return dict(project.items())
                else:
                    if (
                        snapshot := await self.SnapshotsOrm(conn)
                        .set_filter(checksum=commit.snapshot_checksum)
                        .fetch("content")
                    ):
                        assert isinstance(snapshot.content, dict)  # nosec
                        return snapshot.content

        raise NotFoundError(name="snapshot for commit", value=(repo_id, commit_id))

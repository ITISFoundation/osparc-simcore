import hashlib
import json
import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

import sqlalchemy as sa
from aiopg.sa import SAConnection
from aiopg.sa.result import RowProxy
from models_library.projects import ProjectID
from projects.test_projects_version_control import ProjectsOrm
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
from simcore_postgres_database.utils_aiopg_orm import ALL_COLUMNS, BaseOrm
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .db_base_repository import BaseRepository
from .version_control_errors import (
    CleanRequiredError,
    InvalidParameterError,
    NoCommitError,
    NotFoundError,
)
from .version_control_models import (
    HEAD,
    BranchProxy,
    CommitID,
    CommitLog,
    CommitProxy,
    ProjectDict,
    RefID,
    SHA1Str,
    TagProxy,
)

log = logging.getLogger(__name__)


def compute_checksum(workbench: Dict[str, Any]) -> SHA1Str:
    #
    # - UI is NOT accounted in the checksum
    # - TODO: review other fields to mask?
    #
    # FIXME: dump workbench correctly (i.e. spaces, quotes ... -indepenent)
    block_string = json.dumps(workbench, sort_keys=True).encode("utf-8")
    raw_hash = hashlib.sha1(block_string)
    return raw_hash.hexdigest()


class VersionControlRepository(BaseRepository):
    """
    db layer to access multiple tables within projects_version_control
    """

    # FIXME: optimize all db queries

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
                writeonce=set(
                    c for c in projects_vc_commits.columns.keys() if c != "message"
                ),
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
    ) -> Optional[RowProxy]:
        if h := await self.HeadsOrm(conn).fetch("head_branch_id", rowid=repo_id):
            branch = (
                await self.BranchesOrm(conn)
                .set_filter(id=h.head_branch_id)
                .fetch("id name head_commit_id")
            )
            return branch

    async def _get_HEAD_commit(
        self, repo_id: int, conn: SAConnection
    ) -> Optional[RowProxy]:
        if branch := await self._get_head_branch(repo_id, conn):
            commit = (
                await self.CommitsOrm(conn).set_filter(id=branch.head_commit_id).fetch()
            )
            return commit

    async def _fetch_project_wcopy(
        self, repo_id: int, commit_id: int, conn: SAConnection
    ) -> ProjectID:
        # defaults to current
        repo = (
            await self.ReposOrm(conn)
            .set_filter(id=repo_id)
            .fetch("id project_uuid project_checksum modified")
        )
        assert repo  #  nosec

        project_wcopy_id = repo.project_uuid

        # search tags for runnable-project for commit_id
        tags = (
            await self.TagsOrm(conn)
            .set_filter(commit_id=commit_id, hidden=True)
            .fetch_all("id name message")
        )
        if tags:
            try:
                # parse tag
                # TODO: define separately to achieve consistency between format/parse operations
                wc_tag = next(t for t in tags if t.name.startswith("wc:"))
                project_wcopy_id = ProjectID(wc_tag.replace("wc:", ""))
            except (StopIteration, ValueError):
                pass

        return project_wcopy_id

    async def _update_state(self, repo_id: int, conn: SAConnection):

        head_commit: Optional[RowProxy] = await self._get_HEAD_commit(repo_id, conn)

        # current repo
        repo_orm = self.ReposOrm(conn).set_filter(id=repo_id)
        returning_cols = "id project_uuid project_checksum modified"
        repo = await repo_orm.fetch(returning_cols)
        assert repo  #  nosec

        # fetch project
        project_orm = self.ProjectsOrm(conn).set_filter(uuid=repo.project_uuid)
        project = await project_orm.fetch("last_change_date workbench ui")
        assert project  # nosec

        checksum: Optional[SHA1Str] = repo.project_checksum
        if not checksum or (checksum and repo.modified < project.last_change_date):
            checksum = compute_checksum(project.workbench)

            repo = await repo_orm.update(returning_cols, project_checksum=checksum)
            assert repo
        return repo, head_commit, project

    @staticmethod
    async def _upsert_snapshot(
        project_checksum: str,
        project: Union[RowProxy, SimpleNamespace],
        conn: SAConnection,
    ):
        # has changes wrt previous commit
        assert project_checksum  # nosec
        insert_stmt = pg_insert(projects_vc_snapshots).values(
            checksum=project_checksum,
            content={"workbench": project.workbench, "ui": project.ui},
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

    async def commit(
        self, repo_id: int, tag: Optional[str] = None, message: Optional[str] = None
    ) -> int:
        """add changes, commits and tags (if tag is not None)

        Message is added to tag if set otherwise to commit
        """
        if tag in ["HEAD", HEAD]:
            raise InvalidParameterError(name="tag", reason="is a reserved word")

        async with self.engine.acquire() as conn:
            # FIXME: get head commit in one execution

            # get head branch
            branch = await self._get_head_branch(repo_id, conn)
            if not branch:
                raise NotImplementedError("Detached heads still not implemented")

            log.info("On branch %s", branch.name)

            # get head commit
            repo, head_commit, project = await self._update_state(repo_id, conn)

            if head_commit is None:
                previous_checksum = None
                commit_id = None
            else:
                previous_checksum = head_commit.snapshot_checksum
                commit_id = head_commit.id

            async with conn.begin():
                # take a snapshot if needed
                if repo.project_checksum != previous_checksum:
                    await self._upsert_snapshot(repo.project_checksum, project, conn)

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
                    log.info("Nothing to commit, working tree clean")

            assert isinstance(commit_id, int)  # nosec
            return commit_id

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
            raise NotFoundError(name="commit", value=commit_id)

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
                # TODO: sortby should have
                sort_by=sa.desc(commits_orm.columns["created"]),
            )

            logs = []
            for commit in commits:
                tags: List[TagProxy]
                tags = await tags_orm.set_filter(commit_id=commit.id).fetch_all()
                logs.append((commit, tags))

            return logs, total_count

    async def update_annotations(
        self,
        repo_id: int,
        commit_id: CommitID,
        message: Optional[str] = None,
        tag_name: Optional[str] = None,
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
    ) -> Tuple[int, CommitID]:
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
            repo, head_commit, _ = await self._update_state(repo_id, conn)

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

                # restores project snapshot
                snapshot = (
                    await self.SnapshotsOrm(conn)
                    .set_filter(commit.snapshot_checksum)
                    .fetch("content")
                )
                assert snapshot  # nosec

                await self.ProjectsOrm(conn).set_filter(uuid=repo.project_uuid).update(
                    **snapshot.content
                )

                # create detached branch that points to (repo_id, commit_id)
                # upsert "detached" branch
                insert_stmt = (
                    pg_insert(projects_vc_branches)
                    .values(
                        repo_id=repo_id,
                        head_commit_id=commit_id,
                        name="DETACHED",
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

    async def force_branch(
        self,
        repo_id: int,
        start_commit_id: int,
        project: ProjectDict,
        branch_name: str,
        tags: List[str],
    ) -> CommitID:
        """Forces a new branch with an explicit working copy 'project' on 'start_commit_id'

        For internal operation
        """
        IS_INTERNAL_OPERATION = True
        assert tags, "force_branch must be tagged"

        async with self.engine.acquire() as conn:

            for name in tags:
                # FIXME: ask commit_id of all tags at the same time and make sure they are the same
                if tag := await self.TagsOrm(conn).set_filter(name=name).fetch():
                    return tag.commit_id

            async with conn.begin():
                # creates runnable version in project
                # raises ?? if same uuid
                await self.ProjectsOrm(conn).insert(**project)

                # upsert in snapshot table
                snapshot_checksum = compute_checksum(project["workbench"])

                # TODO: check snapshot in parent_commit_id != snapshot_checksum
                await self._upsert_snapshot(
                    snapshot_checksum, SimpleNamespace(**project), conn
                )

                # commit new snapshot in history
                commit_id = await self.CommitsOrm(conn).insert(
                    repo_id=repo_id,
                    parent_commit_id=start_commit_id,
                    message="forced branch",
                    snapshot_checksum=snapshot_checksum,
                )
                assert commit_id  # nosec

                # create branch and set head to last commit_id
                branch = await self.BranchesOrm(conn).insert(
                    returning_cols="id head_commit_id",
                    repo_id=repo_id,
                    head_commit_id=commit_id,
                    name=branch_name,
                )
                assert isinstance(branch, RowProxy)  # nosec

                for tag in tags:
                    await self.TagsOrm(conn).insert(
                        repo_id=repo_id,
                        commit_id=commit_id,
                        name=tag,
                        hidden=IS_INTERNAL_OPERATION,
                    )

                return branch.head_commit_id

    async def get_snapshot_content(self, repo_id: int, commit_id: int) -> Dict:
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
                    return snapshot.content

        raise NotFoundError(name="snapshot for commit", value=(repo_id, commit_id))

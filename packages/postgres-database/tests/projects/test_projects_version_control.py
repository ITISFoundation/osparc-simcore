# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements

import hashlib
import json
from typing import Any, Optional
from uuid import UUID, uuid3

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
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
            writeonce=set(projects_vc_commits.columns.keys()),
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


# -------------


def eval_checksum(workbench: dict[str, Any]):
    # FIXME: prototype
    block_string = json.dumps(workbench, sort_keys=True).encode("utf-8")
    raw_hash = hashlib.sha256(block_string)
    return raw_hash.hexdigest()


def eval_snapshot_uuid(repo: RowProxy, commit: RowProxy) -> UUID:
    assert repo.id == commit.repo_id  # nosec
    return uuid3(UUID(repo.project_uuid), f"{repo.id}.{commit.snapshot_checksum}")


async def add_snapshot(
    project_wc: RowProxy, checksum: str, repo: RowProxy, conn: SAConnection
) -> str:
    snapshot_orm = SnapshotsOrm(conn)
    snapshot_checksum = checksum
    row_id = await snapshot_orm.insert(
        checksum=checksum,
        content={"workbench": project_wc.workbench, "ui": project_wc.ui},
    )
    assert row_id == checksum
    return checksum


async def test_basic_workflow(project: RowProxy, conn: SAConnection):

    # git init
    async with conn.begin():
        # create repo
        repo_orm = ReposOrm(conn)
        repo_id = await repo_orm.insert(project_uuid=project.uuid)
        assert repo_id is not None
        assert isinstance(repo_id, int)

        repo_orm.set_filter(rowid=repo_id)
        repo = await repo_orm.fetch()
        assert repo
        assert repo.project_uuid == project.uuid
        assert repo.project_checksum is None
        assert repo.created == repo.modified

        # create main branch
        branches_orm = BranchesOrm(conn)
        branch_id = await branches_orm.insert(repo_id=repo.id)
        assert branch_id is not None
        assert isinstance(branch_id, int)

        branches_orm.set_filter(rowid=branch_id)
        main_branch: Optional[RowProxy] = await branches_orm.fetch()
        assert main_branch
        assert main_branch.name == "main", "Expected 'main' as default branch"
        assert main_branch.head_commit_id is None, "still not assigned"
        assert main_branch.created == main_branch.modified

        # assign head branch
        heads_orm = HeadsOrm(conn)
        await heads_orm.insert(repo_id=repo.id, head_branch_id=branch_id)

        heads_orm.set_filter(rowid=repo.id)
        head = await heads_orm.fetch()
        assert head

    #
    # create first commit -- TODO: separate tests

    # fetch a *full copy* of the project (WC)
    repo = await repo_orm.fetch("id project_uuid project_checksum")
    assert repo

    project_orm = ProjectsOrm(conn).set_filter(uuid=repo.project_uuid)
    project_wc = await project_orm.fetch()
    assert project_wc
    assert project == project_wc

    # call external function to compute checksum
    checksum = eval_checksum(project_wc.workbench)
    assert repo.project_checksum != checksum

    # take snapshot <=> git add & commit
    async with conn.begin():

        snapshot_checksum = await add_snapshot(project_wc, checksum, repo, conn)

        # get HEAD = repo.branch_id -> .head_commit_id
        assert head.repo_id == repo.id
        branches_orm.set_filter(head.head_branch_id)
        branch = await branches_orm.fetch("head_commit_id name")
        assert branch
        assert branch.name == "main"
        assert branch.head_commit_id is None, "First commit"

        # create commit
        commits_orm = CommitsOrm(conn)
        commit_id = await commits_orm.insert(
            repo_id=repo.id,
            parent_commit_id=branch.head_commit_id,
            snapshot_checksum=snapshot_checksum,
            message="first commit",
        )
        assert commit_id
        assert isinstance(commit_id, int)

        # update branch head
        await branches_orm.update(head_commit_id=commit_id)

        # update checksum cache
        await repo_orm.update(project_checksum=snapshot_checksum)

    # log history
    commits = await commits_orm.fetch_all()
    assert len(commits) == 1
    assert commits[0].id == commit_id

    # tag
    tag_orm = TagsOrm(conn)
    tag_id = await tag_orm.insert(
        repo_id=repo.id,
        commit_id=commit_id,
        name="v1",
    )
    assert tag_id is not None
    assert isinstance(tag_id, int)

    tag = await tag_orm.fetch(rowid=tag_id)
    assert tag
    assert tag.name == "v1"

    ############# NEW COMMIT #####################

    # user add some changes
    repo = await repo_orm.fetch()
    assert repo

    project_orm.set_filter(uuid=repo.project_uuid)
    assert project_orm.is_filter_set()

    await project_orm.update(
        workbench={
            "node": {
                "input": 3,
            }
        }
    )

    project_wc = await project_orm.fetch("workbench ui")
    assert project_wc
    assert project.workbench != project_wc.workbench

    # get HEAD = repo.branch_id -> .head_commit_id
    head = await heads_orm.fetch()
    assert head
    branch = await branches_orm.fetch("head_commit_id", rowid=head.head_branch_id)
    assert branch
    # TODO: get subquery ... and compose
    head_commit = await commits_orm.fetch(rowid=branch.head_commit_id)
    assert head_commit

    # compare checksums between wc and HEAD
    checksum = eval_checksum(project_wc.workbench)
    assert head_commit.snapshot_checksum != checksum

    # updates wc checksum cache
    await repo_orm.update(project_checksum=checksum)

    # take snapshot = add & commit
    async with conn.begin():
        snapshot_uuid: str = await add_snapshot(project_wc, checksum, repo, conn)

        commit_id = await commits_orm.insert(
            repo_id=head_commit.repo_id,
            parent_commit_id=head_commit.id,
            snapshot_checksum=checksum,
            message="second commit",
        )
        assert commit_id
        assert isinstance(commit_id, int)

        # update branch head
        await branches_orm.update(head_commit_id=commit_id)

    # log history
    commits = await commits_orm.fetch_all()
    assert len(commits) == 2
    assert commits[1].id == commit_id

    ############# CHECKOUT TO TAG #####################


@pytest.mark.skip(reason="DEV")
def test_concurrency():
    # several repos
    # several threads
    assert False

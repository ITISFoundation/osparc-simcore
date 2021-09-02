# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import hashlib
import json
from typing import Optional
from uuid import UUID, uuid3

from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.projects_snapshots import projects_snapshots
from simcore_postgres_database.models.projects_version_control import (
    projects_vc_branches,
    projects_vc_commits,
    projects_vc_repos,
    projects_vc_tags,
)
from simcore_postgres_database.utils_aiopg_orm import BaseOrm


async def test_basic_workflow(project: RowProxy, conn: SAConnection):
    # create repo
    repo_orm = BaseOrm[int](projects_vc_repos, conn)
    repo_id = await repo_orm.insert(project_uuid=project.uuid)
    assert repo_id is not None

    repo_orm.pin_row(repo_id)
    repo = await repo_orm.fetch()
    assert repo
    assert repo.project_uuid == project.uuid
    assert repo.branch_id is None
    assert repo.created == repo.modified

    # create main branch
    branch_orm = BaseOrm[int](projects_vc_branches, conn)
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

    project_orm = BaseOrm[str](projects, conn).pin_row(uuid=repo.project_uuid)
    project_wc = await project_orm.fetch()
    assert project_wc
    assert project == project_wc

    # eval checksum
    checksum = eval_checksum(project_wc.workbench)
    assert repo.project_checksum != checksum

    # take snapshot = add & commit
    async with conn.begin():
        snapshot_orm = BaseOrm[int](projects_snapshots, conn)

        snapshot_checksum = checksum
        snapshot_uuid = str(
            uuid3(UUID(repo.project_uuid), f"{repo.id}.{snapshot_checksum}")
        )

        await snapshot_orm.insert(
            uuid=snapshot_uuid, workbench=project_wc.workbench, ui=project_wc.ui
        )

        # get HEAD = repo.branch_id -> .head_id
        branch_orm = BaseOrm[int](projects_vc_branches, conn).pin_row(repo.branch_id)
        branch = await branch_orm.fetch("head_commit_id name")
        assert branch
        assert branch.name == "main"

        # create commit
        commits_orm = BaseOrm[int](projects_vc_commits, conn)
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
    tag_orm = BaseOrm[int](projects_vc_tags, conn)
    tag_id: Optional[int] = await tag_orm.insert(
        repo_id=repo.id,
        commit_id=commit_id,
        name="v1",
    )
    assert tag_id is not None

    tag = await tag_orm.fetch(rowid=tag_id)
    assert tag
    assert tag.name == "v1"

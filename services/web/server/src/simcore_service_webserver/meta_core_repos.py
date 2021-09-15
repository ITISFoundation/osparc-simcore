"""
    A checkpoint is equivalent to a commit and can be tagged at the same time (*)

    Working copy

    HEAD revision

    (*) This is a concept introduced for the front-end to avoid using
    more fine grained concepts as tags and commits directly
"""
from typing import List, Optional, Tuple
from uuid import UUID

from aiohttp import web
from aiopg.sa.result import RowProxy
from pydantic import NonNegativeInt, PositiveInt, validate_arguments
from simcore_service_webserver.meta_db import CommitLog, VersionControlRepository

from .meta_models_repos import Checkpoint, RefID, WorkbenchView

cfg = {"arbitrary_types_allowed": True}


async def list_repos(
    vc_repo: VersionControlRepository,
    *,
    offset: NonNegativeInt = 0,
    limit: Optional[PositiveInt] = None,
) -> Tuple[List[RowProxy], PositiveInt]:

    # NOTE: this layer does NOT add much .. why not use vc_repo directly?
    repos_rows, total_number_of_repos = await vc_repo.list_repos(offset, limit)

    assert len(repos_rows) <= total_number_of_repos  # nosec
    return repos_rows, total_number_of_repos


async def list_checkpoints(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    *,
    offset: NonNegativeInt = 0,
    limit: Optional[PositiveInt] = None,
) -> Tuple[List[Checkpoint], PositiveInt]:

    repo_id = await vc_repo.get_repo_id(project_uuid)
    if not repo_id:
        return [], 0

    logs: List[CommitLog]
    logs, total_number_of_commits = await vc_repo.log(
        repo_id, offset=offset, limit=limit
    )

    checkpoints = [Checkpoint.from_commit_log(commit, tags) for commit, tags in logs]
    assert len(checkpoints) <= limit if limit else True  # nosec
    assert total_number_of_commits > 0

    return checkpoints, total_number_of_commits


async def create_checkpoint(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    *,
    tag: str,
    message: Optional[str] = None,
) -> Checkpoint:

    repo_id = await vc_repo.get_repo_id(project_uuid)
    if repo_id is None:
        repo_id = await vc_repo.init_repo(project_uuid)

    commit_id = await vc_repo.commit(repo_id, tag=tag, message=message)
    commit, tags = await vc_repo.get_commit_log(commit_id)
    assert commit  # nosec

    return Checkpoint.from_commit_log(commit, tags)


async def get_checkpoint(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    ref_id: RefID,
) -> Checkpoint:

    try:
        repo_id, commit_id = await vc_repo.as_repo_and_commit_ids(project_uuid, ref_id)

        if repo_id is None or commit_id is None:
            raise ValueError(f"Could not find reference {ref_id} for {project_uuid}")

        commit, tags = await vc_repo.get_commit_log(commit_id)
        return Checkpoint.from_commit_log(commit, tags)
    except ValueError as err:
        raise web.HTTPNotFound(reason=str(err.args) or "Entrypoint not found") from err


async def update_checkpoint(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    ref_id: RefID,
    *,
    message: Optional[str] = None,
    tag: Optional[str] = None,
) -> Checkpoint:

    if message is None and tag is None:
        raise ValueError("Nothing to update")

    repo_id, commit_id = await vc_repo.as_repo_and_commit_ids(project_uuid, ref_id)

    if repo_id is None or commit_id is None:
        raise ValueError(f"Could not find reference {ref_id} for {project_uuid}")

    await vc_repo.update_annotations(repo_id, commit_id, message, tag)

    commit, tags = await vc_repo.get_commit_log(commit_id)
    return Checkpoint.from_commit_log(commit, tags)


async def checkout_checkpoint(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    ref_id: RefID,
) -> Checkpoint:

    repo_id, commit_id = await vc_repo.as_repo_and_commit_ids(project_uuid, ref_id)

    # check if working copy has changes, if so, auto commit it
    try:
        commit_id = await vc_repo.checkout(repo_id, commit_id)
    except RuntimeError:
        await vc_repo.commit(repo_id, message="auto commit")
        commit_id = await vc_repo.checkout(repo_id, commit_id)

    commit, tags = await vc_repo.get_commit_log(commit_id)
    return Checkpoint.from_commit_log(commit, tags)


async def get_workbench(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    ref_id: RefID,
) -> WorkbenchView:

    repo_id, commit_id = await vc_repo.as_repo_and_commit_ids(project_uuid, ref_id)

    if repo_id is None or commit_id is None:
        raise web.HTTPNotFound(
            reason=f"Entrypoint {ref_id} for project {project_uuid} not found"
        )

    if content := await vc_repo.get_snapshot_content(repo_id, commit_id):
        return WorkbenchView.from_orm(content)

    raise web.HTTPNotFound(reason=f"Could not find snapshot for project {project_uuid}")


list_repos_safe = validate_arguments(list_repos, config=cfg)
list_checkpoints_safe = validate_arguments(list_checkpoints, config=cfg)
create_checkpoint_safe = validate_arguments(create_checkpoint, config=cfg)
get_checkpoint_safe = validate_arguments(get_checkpoint, config=cfg)
update_checkpoint_safe = validate_arguments(update_checkpoint, config=cfg)
checkout_checkpoint_safe = validate_arguments(checkout_checkpoint, config=cfg)
get_workbench_safe = validate_arguments(get_workbench, config=cfg)

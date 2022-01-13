"""
    A checkpoint is equivalent to a commit and can be tagged at the same time (*)

    Working copy

    HEAD revision

    (*) This is a concept introduced for the front-end to avoid using
    more fine grained concepts as tags and commits directly
"""
import logging
from typing import List, Optional, Tuple
from uuid import UUID

from aiopg.sa.result import RowProxy
from pydantic import NonNegativeInt, PositiveInt, validate_arguments
from simcore_service_webserver.version_control_db import (
    CommitLog,
    VersionControlRepository,
)

from .version_control_errors import CleanRequiredError
from .version_control_models import Checkpoint, RefID, WorkbenchView

CFG = {"arbitrary_types_allowed": True}

log = logging.getLogger(__name__)


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

    repo_id, commit_id = await vc_repo.as_repo_and_commit_ids(project_uuid, ref_id)
    assert repo_id  # nosec

    commit, tags = await vc_repo.get_commit_log(commit_id)
    return Checkpoint.from_commit_log(commit, tags)


async def update_checkpoint(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    ref_id: RefID,
    *,
    message: Optional[str] = None,
    tag: Optional[str] = None,
) -> Checkpoint:

    repo_id, commit_id = await vc_repo.as_repo_and_commit_ids(project_uuid, ref_id)

    if message is None and tag is None:
        log.warning(
            "Nothing to update. Skipping updating ref %s of %s", ref_id, project_uuid
        )
    else:
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
    except CleanRequiredError:
        log.info("Local changes found. Auto-commiting project %s", project_uuid)
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

    # prefer actual project to snapshot
    # TODO: tmp disabled
    # content: Dict = await vc_repo.get_snapshot_content(repo_id, commit_id)
    content = await vc_repo.get_workbench_view(repo_id, commit_id)
    return WorkbenchView.parse_obj(content)


#
# All above with validated arguments
#
list_repos_safe = validate_arguments(list_repos, config=CFG)
list_checkpoints_safe = validate_arguments(list_checkpoints, config=CFG)
create_checkpoint_safe = validate_arguments(create_checkpoint, config=CFG)
get_checkpoint_safe = validate_arguments(get_checkpoint, config=CFG)
update_checkpoint_safe = validate_arguments(update_checkpoint, config=CFG)
checkout_checkpoint_safe = validate_arguments(checkout_checkpoint, config=CFG)
get_workbench_safe = validate_arguments(get_workbench, config=CFG)

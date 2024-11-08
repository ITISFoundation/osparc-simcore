"""
    A checkpoint is equivalent to a commit and can be tagged at the same time (*)

    Working copy

    HEAD revision

    (*) This is a concept introduced for the front-end to avoid using
    more fine grained concepts as tags and commits directly
"""
import logging
from uuid import UUID

from aiopg.sa.result import RowProxy
from pydantic import NonNegativeInt, PositiveInt, validate_call

from .db import VersionControlRepository
from .errors import CleanRequiredError
from .models import Checkpoint, CommitLog, RefID, WorkbenchView

_logger = logging.getLogger(__name__)


async def list_repos(
    vc_repo: VersionControlRepository,
    *,
    offset: NonNegativeInt = 0,
    limit: PositiveInt | None = None,
) -> tuple[list[RowProxy], PositiveInt]:
    # NOTE: this layer does NOT add much .. why not use vc_repo directly?
    repos_rows, total_number_of_repos = await vc_repo.list_repos(offset, limit)

    assert len(repos_rows) <= total_number_of_repos  # nosec
    return repos_rows, total_number_of_repos


async def list_checkpoints(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    *,
    offset: NonNegativeInt = 0,
    limit: PositiveInt | None = None,
) -> tuple[list[Checkpoint], PositiveInt]:
    repo_id = await vc_repo.get_repo_id(project_uuid)
    if not repo_id:
        return [], 0

    logs: list[CommitLog]
    logs, total_number_of_commits = await vc_repo.log(
        repo_id, offset=offset, limit=limit
    )

    checkpoints = [Checkpoint.from_commit_log(commit, tags) for commit, tags in logs]
    assert len(checkpoints) <= limit if limit else True  # nosec
    assert total_number_of_commits > 0  # nosec

    return checkpoints, total_number_of_commits


async def create_checkpoint(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    *,
    tag: str,
    message: str | None = None,
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
    message: str | None = None,
    tag: str | None = None,
) -> Checkpoint:
    repo_id, commit_id = await vc_repo.as_repo_and_commit_ids(project_uuid, ref_id)

    if message is None and tag is None:
        _logger.warning(
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
        _logger.info("Local changes found. Auto-commiting project %s", project_uuid)
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
    content = await vc_repo.get_workbench_view(repo_id, commit_id)
    return WorkbenchView.model_validate(content)


#
# All above with validated arguments
#

_CONFIG = {"arbitrary_types_allowed": True}


list_repos_safe = validate_call(list_repos, config=_CONFIG)  # type: ignore
list_checkpoints_safe = validate_call(list_checkpoints, config=_CONFIG)  # type: ignore
create_checkpoint_safe = validate_call(create_checkpoint, config=_CONFIG)  # type: ignore
get_checkpoint_safe = validate_call(get_checkpoint, config=_CONFIG)  # type: ignore
update_checkpoint_safe = validate_call(update_checkpoint, config=_CONFIG)  # type: ignore
checkout_checkpoint_safe = validate_call(checkout_checkpoint, config=_CONFIG)  # type: ignore
get_workbench_safe = validate_call(get_workbench, config=_CONFIG)  # type: ignore

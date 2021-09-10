"""
    A checkpoint is equivalent to a commit and can be tagged at the same time (*)

    Working copy

    HEAD revision

    (*) This is a concept introduced for the front-end to avoid using
    more fine grained concepts as tags and commits directly
"""
from contextlib import suppress
from typing import List, Optional, Tuple, Union
from uuid import UUID

from aiohttp import web
from aiopg.sa.result import RowProxy
from pydantic import NonNegativeInt, PositiveInt, validate_arguments
from simcore_service_webserver.meta_db import CommitLog, VersionControlRepository

from .meta_models_repos import Checkpoint, WorkbenchView

HEAD = f"{__file__}/ref/HEAD"

RefID = Union[str, int]

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
    assert (  # nosec
        limit <= total_number_of_commits if limit else total_number_of_commits > 0
    )  # nosec

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

    repo_id = await vc_repo.get_repo_id(project_uuid)
    if repo_id:
        commit_id = None

        if ref_id == HEAD:
            commit = await vc_repo.get_head_commit(repo_id)
            if commit:
                commit_id = commit.id

        elif isinstance(ref_id, int):
            commit_id = ref_id

        else:
            assert isinstance(ref_id, str)
            # head branch or tag
            raise NotImplementedError("WIP: Tag or head branches as ref_id")

        with suppress(ValueError):
            commit, tags = await vc_repo.get_commit_log(commit_id)
            return Checkpoint.from_commit_log(commit, tags)

    raise web.HTTPNotFound(reason="Entrypoint not found")


async def update_checkpoint(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    ref_id: RefID,
    *,
    message: Optional[str] = None,
) -> Checkpoint:
    ...


async def get_working_copy(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
):
    ...


async def checkout_checkpoint(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    ref_id: RefID,
) -> Checkpoint:
    ...


async def get_workbench(
    vc_repo: VersionControlRepository,
    project_uuid: UUID,
    ref_id: RefID,
) -> WorkbenchView:
    ...


list_checkpoints_safe = validate_arguments(list_checkpoints, config=cfg)
create_checkpoint_safe = validate_arguments(create_checkpoint, config=cfg)
get_checkpoint_safe = validate_arguments(get_checkpoint, config=cfg)
update_checkpoint_safe = validate_arguments(update_checkpoint, config=cfg)
checkout_checkpoint_safe = validate_arguments(checkout_checkpoint, config=cfg)
get_workbench_safe = validate_arguments(get_workbench, config=cfg)

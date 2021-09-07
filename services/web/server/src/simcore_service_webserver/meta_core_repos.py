"""
    A checkpoint is equivalent to a commit and can be tagged at the same time (*)

    Working copy

    HEAD revision

    (*) This is a concept introduced for the front-end to avoid using
    more fine grained concepts as tags and commits directly
"""
from typing import List, Optional, Tuple, Union
from uuid import UUID

from aiohttp import web
from pydantic import NonNegativeInt, PositiveInt, validate_arguments

from .meta_models_repos import Checkpoint, WorkbenchView

HEAD = f"{__file__}/ref/HEAD"

RefID = Union[str, int]

cfg = {"arbitrary_types_allowed": True}


async def list_checkpoints(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: UUID,
    *,
    limit: Optional[PositiveInt] = None,
    offset: NonNegativeInt = 0,
) -> Tuple[List[Checkpoint], PositiveInt]:
    # list, total
    ...


async def create_checkpoint(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: UUID,
    *,
    tag: str,
    message: Optional[str] = None,
    new_branch: Optional[str] = None,
) -> Checkpoint:

    # new_branch is used to name the new branch in case
    # the checkpoint is forced to branch
    ...


async def get_checkpoint(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: UUID,
    ref_id: RefID,
) -> Checkpoint:
    ...


async def update_checkpoint(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: UUID,
    ref_id: RefID,
    *,
    tag: Optional[str] = None,
    message: Optional[str] = None,
) -> Checkpoint:
    ...


async def get_working_copy(
    app: web.Application,
    project_uuid: UUID,
    user_id: PositiveInt,
):
    ...


async def checkout_checkpoint(
    app: web.Application,
    user_id: PositiveInt,
    project_uuid: UUID,
    ref_id: RefID,
) -> Checkpoint:
    ...


async def get_workbench(
    app: web.Application,
    user_id: PositiveInt,
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

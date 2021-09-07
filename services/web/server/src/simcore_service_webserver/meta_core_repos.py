"""
    A checkpoint is equivalent to a commit and can be tagged at the same time (*)

    Working copy

    HEAD revision

    (*) This is a concept introduced for the front-end to avoid using
    more fine grained concepts as tags and commits directly
"""
from typing import Optional, Union
from uuid import UUID

from aiohttp import web
from pydantic import NonNegativeInt, PositiveInt

HEAD = f"{__file__}/ref/HEAD"

RefID = Union[str, int]


async def list_checkpoints(
    app: web.Application,
    *,
    limit: Optional[PositiveInt] = None,
    offset: NonNegativeInt = 0,
):
    ...


async def create_checkpoint(
    app: web.Application,
    project_uuid: UUID,
    *,
    tag: str,
    message: Optional[str] = None,
    new_branch: Optional[str] = None,
):
    # new_branch is used to name the new branch in case
    # the checkpoint is forced to branch
    ...


async def get_checkpoint(
    app: web.Application,
    project_uuid: UUID,
    ref_id: str,
):
    if ref_id == HEAD:
        ...


async def update_checkpoint(
    app: web.Application,
    project_uuid: UUID,
    ref_id: str,
    *,
    tag: Optional[str] = None,
    message: Optional[str] = None,
):
    if ref_id == HEAD:
        ...


async def get_working_copy(app: web.Application):
    ...


async def checkout_checkpoint(
    app: web.Application,
    project_uuid: UUID,
    ref_id: str,
):
    ...


async def get_workbench(
    app: web.Application,
    project_uuid: UUID,
    ref_id: str,
):
    ...

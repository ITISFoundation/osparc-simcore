# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, status
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._trash_handlers import (
    ProjectPathParams,
    RemoveQueryParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["trash"],
)


@router.delete(
    "/trash",
    status_code=status.HTTP_204_NO_CONTENT,
)
def empty_trash():
    ...


_extra_tags: list[str | Enum] = ["projects"]


@router.post(
    "/projects/{project_id}:trash",
    tags=_extra_tags,
    status_code=status.HTTP_204_NO_CONTENT,
)
def trash_project(
    _p: Annotated[ProjectPathParams, Depends()],
    _q: Annotated[RemoveQueryParams, Depends()],
):
    ...


@router.post(
    "/projects/{project_id}:untrash",
    tags=_extra_tags,
    status_code=status.HTTP_204_NO_CONTENT,
)
def untrash_project(
    _p: Annotated[ProjectPathParams, Depends()],
):
    ...

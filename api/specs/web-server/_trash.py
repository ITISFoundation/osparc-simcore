# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from fastapi import APIRouter, status
from models_library.projects import ProjectID
from simcore_service_webserver._meta import API_VTAG

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
    project_id: ProjectID,
):
    ...


@router.post(
    "/projects/{project_id}:untrash",
    tags=_extra_tags,
    status_code=status.HTTP_204_NO_CONTENT,
)
def untrash_project(
    project_id: ProjectID,
):
    ...

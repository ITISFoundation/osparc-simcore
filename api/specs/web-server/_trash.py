# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from fastapi import APIRouter
from models_library.projects import ProjectID
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["trash"],
)


@router.delete(
    "/trash",
)
def empty_trash():
    ...


### Projects

_extra_tags: list[str | Enum] = ["projects"]


@router.post(
    "/projects/{project_uuid}:trash",
    tags=_extra_tags,
)
def trash_project(
    project_uuid: ProjectID,
):
    ...


@router.post("/projects/{project_uuid}:untrash", tags=_extra_tags)
def untrash_project(
    project_uuid: ProjectID,
):
    ...

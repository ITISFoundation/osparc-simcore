# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from fastapi import APIRouter
from models_library.api_schemas_webserver.folders import FolderGet
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.generics import Envelope
from models_library.projects import ProjectID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.folders._folders_handlers import FolderID

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
    response_model=Envelope[ProjectGet],
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


### Folders

_extra_tags = ["folders"]


@router.post(
    "/folders/{folder_id}:trash", response_model=Envelope[FolderGet], tags=_extra_tags
)
def trash_folder(
    folder_id: FolderID,
):
    ...


@router.post("/folders/{folder_id}:untrash", tags=_extra_tags)
def untrash_folder(
    folder_id: FolderID,
):
    ...


## TODO: workspaces

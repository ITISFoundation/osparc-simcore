# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.rest_error import EnvelopedError
from models_library.trash import RemoveQueryParams
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.folders._common.models import (
    FoldersPathParams,
    FolderTrashQueryParams,
)
from simcore_service_webserver.projects._controller._rest_exceptions import (
    _TO_HTTP_ERROR_MAP,
)
from simcore_service_webserver.projects._controller.trash_rest import ProjectPathParams
from simcore_service_webserver.workspaces._common.models import (
    WorkspacesPathParams,
    WorkspaceTrashQueryParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["trash"],
    responses={
        i.status_code: {"model": EnvelopedError} for i in _TO_HTTP_ERROR_MAP.values()
    },
)


@router.post(
    "/trash:empty",
    status_code=status.HTTP_204_NO_CONTENT,
)
def empty_trash(): ...


_extra_tags: list[str | Enum] = ["projects"]


@router.post(
    "/projects/{project_id}:trash",
    tags=_extra_tags,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Not such a project",
            "model": EnvelopedError,
        },
        status.HTTP_409_CONFLICT: {
            "description": "Project is in use and cannot be trashed",
            "model": EnvelopedError,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Trash service error",
            "model": EnvelopedError,
        },
    },
)
def trash_project(
    _path: Annotated[ProjectPathParams, Depends()],
    _query: Annotated[RemoveQueryParams, Depends()],
): ...


@router.post(
    "/projects/{project_id}:untrash",
    tags=_extra_tags,
    status_code=status.HTTP_204_NO_CONTENT,
)
def untrash_project(
    _path: Annotated[ProjectPathParams, Depends()],
): ...


_extra_tags = ["folders"]


@router.post(
    "/folders/{folder_id}:trash",
    tags=_extra_tags,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not such a folder"},
        status.HTTP_409_CONFLICT: {
            "description": "One or more projects in the folder are in use and cannot be trashed"
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Trash service error"},
    },
)
def trash_folder(
    _path: Annotated[FoldersPathParams, Depends()],
    _query: Annotated[FolderTrashQueryParams, Depends()],
): ...


@router.post(
    "/folders/{folder_id}:untrash",
    tags=_extra_tags,
    status_code=status.HTTP_204_NO_CONTENT,
)
def untrash_folder(
    _path: Annotated[FoldersPathParams, Depends()],
): ...


_extra_tags = ["workspaces"]


@router.post(
    "/workspaces/{workspace_id}:trash",
    tags=_extra_tags,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Not such a workspace"},
        status.HTTP_409_CONFLICT: {
            "description": "One or more projects in the workspace are in use and cannot be trashed"
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Trash service error"},
    },
)
def trash_workspace(
    _path: Annotated[WorkspacesPathParams, Depends()],
    _query: Annotated[WorkspaceTrashQueryParams, Depends()],
): ...


@router.post(
    "/workspaces/{workspace_id}:untrash",
    tags=_extra_tags,
    status_code=status.HTTP_204_NO_CONTENT,
)
def untrash_workspace(
    _path: Annotated[WorkspacesPathParams, Depends()],
): ...

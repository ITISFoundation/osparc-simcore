"""Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Literal

from _common import assert_handler_signature_against_model
from fastapi import APIRouter, status
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_comments import CommentID, ProjectsCommentsAPI
from pydantic import NonNegativeInt
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._controller.comments_rest import (
    _ProjectCommentsBodyParams,
    _ProjectCommentsPathParams,
    _ProjectCommentsWithCommentPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
        "comments",
    ],
)


#
# API entrypoints
#


@router.post(
    "/projects/{project_uuid}/comments",
    response_model=Envelope[dict[Literal["comment_id"], CommentID]],
    description="Create a new comment for a specific project. The request body should contain the comment contents and user information.",
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
)
async def create_project_comment(
    project_uuid: ProjectID, body: _ProjectCommentsBodyParams
): ...


assert_handler_signature_against_model(
    create_project_comment, _ProjectCommentsPathParams
)


@router.get(
    "/projects/{project_uuid}/comments",
    response_model=Envelope[list[ProjectsCommentsAPI]],
    description="Retrieve all comments for a specific project.",
    deprecated=True,
)
async def list_project_comments(
    project_uuid: ProjectID, limit: int = 20, offset: NonNegativeInt = 0
): ...


assert_handler_signature_against_model(
    list_project_comments, _ProjectCommentsPathParams
)


@router.put(
    "/projects/{project_uuid}/comments/{comment_id}",
    response_model=Envelope[ProjectsCommentsAPI],
    description="Update the contents of a specific comment for a project. The request body should contain the updated comment contents.",
    deprecated=True,
)
async def update_project_comment(
    project_uuid: ProjectID,
    comment_id: CommentID,
    body: _ProjectCommentsBodyParams,
): ...


assert_handler_signature_against_model(
    update_project_comment, _ProjectCommentsWithCommentPathParams
)


@router.delete(
    "/projects/{project_uuid}/comments/{comment_id}",
    description="Delete a specific comment associated with a project.",
    status_code=status.HTTP_204_NO_CONTENT,
    deprecated=True,
)
async def delete_project_comment(project_uuid: ProjectID, comment_id: CommentID): ...


assert_handler_signature_against_model(
    delete_project_comment, _ProjectCommentsWithCommentPathParams
)


@router.get(
    "/projects/{project_uuid}/comments/{comment_id}",
    response_model=Envelope[ProjectsCommentsAPI],
    description="Retrieve a specific comment by its ID within a project.",
    deprecated=True,
)
async def get_project_comment(project_uuid: ProjectID, comment_id: CommentID): ...


assert_handler_signature_against_model(
    get_project_comment, _ProjectCommentsWithCommentPathParams
)

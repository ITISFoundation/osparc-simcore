""" Helper script to automatically generate OAS

This OAS are the source of truth
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Literal

from _common import (
    CURRENT_DIR,
    assert_handler_signature_against_model,
    create_openapi_specs,
)
from fastapi import APIRouter, FastAPI
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_comments import CommentID, ProjectsCommentsAPI
from pydantic import NonNegativeInt
from simcore_service_webserver.projects._comments_handlers import (
    _ProjectCommentsBodyParams,
    _ProjectCommentsPathParams,
    _ProjectCommentsWithCommentPathParams,
)

router = APIRouter(tags=["project", "comments"])


#
# API entrypoints
#


@router.post(
    "/projects/{project_uuid}/comments",
    response_model=Envelope[dict[Literal["comment_id"], CommentID]],
    operation_id="create_project_comment",
    summary="Create a new comment for a specific project. The request body should contain the comment contents and user information.",
    status_code=201,
)
async def create_project_comment(
    project_uuid: ProjectID, body: _ProjectCommentsBodyParams
):
    ...


assert_handler_signature_against_model(
    create_project_comment, _ProjectCommentsPathParams
)


@router.get(
    "/projects/{project_uuid}/comments",
    response_model=Envelope[list[ProjectsCommentsAPI]],
    operation_id="list_project_comments",
    summary="Retrieve all comments for a specific project.",
)
async def list_project_comments(
    project_uuid: ProjectID, limit: int = 20, offset: NonNegativeInt = 0
):
    ...


assert_handler_signature_against_model(
    list_project_comments, _ProjectCommentsPathParams
)


@router.put(
    "/projects/{project_uuid}/comments/{comment_id}",
    response_model=Envelope[ProjectsCommentsAPI],
    operation_id="update_project_comment",
    summary="Update the contents of a specific comment for a project. The request body should contain the updated comment contents.",
)
async def update_project_comment(
    project_uuid: ProjectID,
    comment_id: CommentID,
    body: _ProjectCommentsBodyParams,
):
    ...


assert_handler_signature_against_model(
    update_project_comment, _ProjectCommentsWithCommentPathParams
)


@router.delete(
    "/projects/{project_uuid}/comments/{comment_id}",
    operation_id="delete_project_comment",
    summary="Delete a specific comment associated with a project.",
    status_code=204,
)
async def delete_project_comment(project_uuid: ProjectID, comment_id: CommentID):
    ...


assert_handler_signature_against_model(
    delete_project_comment, _ProjectCommentsWithCommentPathParams
)


@router.get(
    "/projects/{project_uuid}/comments/{comment_id}",
    response_model=Envelope[ProjectsCommentsAPI],
    operation_id="get_project_comment",
    summary="Retrieve a specific comment by its ID within a project.",
)
async def get_project_comment(project_uuid: ProjectID, comment_id: CommentID):
    ...


assert_handler_signature_against_model(
    get_project_comment, _ProjectCommentsWithCommentPathParams
)


if __name__ == "__main__":
    create_openapi_specs(
        FastAPI(routes=router.routes),
        CURRENT_DIR.parent / "openapi-projects-comments.yaml",
    )

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from _common import assert_handler_signature_against_model
from fastapi import APIRouter, status
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.users import GroupID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._common_models import ProjectPathParams
from simcore_service_webserver.projects._groups_api import ProjectGroupGet
from simcore_service_webserver.projects._groups_handlers import (
    _ProjectsGroupsBodyParams,
    _ProjectsGroupsPathParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
    ],
)


### Projects groups


@router.post(
    "/projects/{project_id}/groups/{group_id}",
    response_model=Envelope[ProjectGroupGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_project_group(
    project_id: ProjectID, group_id: GroupID, body: _ProjectsGroupsBodyParams
):
    ...


assert_handler_signature_against_model(create_project_group, _ProjectsGroupsPathParams)


@router.get(
    "/projects/{project_id}/groups",
    response_model=Envelope[list[ProjectGroupGet]],
)
async def list_project_groups(project_id: ProjectID):
    ...


assert_handler_signature_against_model(list_project_groups, ProjectPathParams)


@router.put(
    "/projects/{project_id}/groups/{group_id}",
    response_model=Envelope[ProjectGroupGet],
)
async def replace_project_group(
    project_id: ProjectID, group_id: GroupID, body: _ProjectsGroupsBodyParams
):
    ...


assert_handler_signature_against_model(replace_project_group, _ProjectsGroupsPathParams)


@router.delete(
    "/projects/{project_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_group(project_id: ProjectID, group_id: GroupID):
    ...


assert_handler_signature_against_model(delete_project_group, _ProjectsGroupsPathParams)

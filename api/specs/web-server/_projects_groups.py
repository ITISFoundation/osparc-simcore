# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.projects._controller._rest_schemas import (
    ProjectPathParams,
)
from simcore_service_webserver.projects._controller.groups_rest import (
    _ProjectsGroupsBodyParams,
    _ProjectsGroupsPathParams,
)
from simcore_service_webserver.projects._groups_service import ProjectGroupGet

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=["projects", "groups"],
)


@router.post(
    "/projects/{project_id}/groups/{group_id}",
    response_model=Envelope[ProjectGroupGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_project_group(
    _path: Annotated[_ProjectsGroupsPathParams, Depends()],
    _body: _ProjectsGroupsBodyParams,
): ...


@router.get(
    "/projects/{project_id}/groups",
    response_model=Envelope[list[ProjectGroupGet]],
)
async def list_project_groups(_path: Annotated[ProjectPathParams, Depends()]): ...


@router.put(
    "/projects/{project_id}/groups/{group_id}",
    response_model=Envelope[ProjectGroupGet],
)
async def replace_project_group(
    _path: Annotated[_ProjectsGroupsPathParams, Depends()],
    _body: _ProjectsGroupsBodyParams,
): ...


@router.delete(
    "/projects/{project_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_project_group(
    _path: Annotated[_ProjectsGroupsPathParams, Depends()],
): ...

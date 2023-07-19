import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi_pagination.api import create_page
from models_library.api_schemas_webserver.projects import ProjectGet

from ...models.pagination import LimitOffsetPage, LimitOffsetParams, OnePage
from ...models.schemas.studies import Study, StudyID, StudyPort
from ...services.webserver import AuthSession
from ..dependencies.webserver import get_webserver_session
from ._common import API_SERVER_DEV_FEATURES_ENABLED

_logger = logging.getLogger(__name__)
router = APIRouter()


def _create_study_from_project(project: ProjectGet) -> Study:
    return Study.construct(
        uid=project.uuid,
        title=project.name,
        description=project.description,
        _fields_set={"uid", "title", "description"},
    )


@router.get(
    "/",
    response_model=LimitOffsetPage[Study],
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def list_studies(
    page_params: Annotated[LimitOffsetParams, Depends()],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    projects_page = await webserver_api.list_user_projects(
        limit=page_params.limit, offset=page_params.offset
    )

    studies: list[Study] = [
        _create_study_from_project(prj) for prj in projects_page.data
    ]

    return create_page(
        studies,
        total=projects_page.meta.total,
        params=page_params,
    )


@router.get(
    "/{study_id}",
    response_model=Study,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_study(
    study_id: StudyID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    # FIXME: cannot be a project associated to a job! or a template!!!
    project: ProjectGet = await webserver_api.get_project(project_id=study_id)
    return _create_study_from_project(project)


@router.get(
    "/{study_id}/ports",
    response_model=OnePage[StudyPort],
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def list_study_ports(
    study_id: StudyID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    """Lists metadata on ports of a given study

    New in *version 0.5.0* (only with API_SERVER_DEV_FEATURES_ENABLED=1)
    """
    project_ports: list[
        dict[str, Any]
    ] = await webserver_api.get_project_metadata_ports(project_id=study_id)

    return OnePage[StudyPort](items=project_ports)  # type: ignore[arg-type]

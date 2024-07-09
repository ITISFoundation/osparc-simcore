import logging
from typing import Annotated, Final

from fastapi import APIRouter, Depends, status
from fastapi_pagination.api import create_page
from models_library.api_schemas_webserver.projects import ProjectGet

from ...models.pagination import OnePage, Page, PaginationParams
from ...models.schemas.errors import ErrorGet
from ...models.schemas.studies import Study, StudyID, StudyPort
from ...services.webserver import AuthSession
from ..dependencies.webserver import get_webserver_session

_logger = logging.getLogger(__name__)
router = APIRouter()

_COMMON_ERROR_RESPONSES: Final[dict] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Study not found",
        "model": ErrorGet,
    },
}


def _create_study_from_project(project: ProjectGet) -> Study:
    assert isinstance(project, ProjectGet)  # nosec
    return Study.construct(
        uid=project.uuid,
        title=project.name,
        description=project.description,
        _fields_set={"uid", "title", "description"},
    )


@router.get(
    "",
    response_model=Page[Study],
)
async def list_studies(
    page_params: Annotated[PaginationParams, Depends()],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    """

    New in *version 0.5.0*
    """
    projects_page = await webserver_api.get_projects_page(
        limit=page_params.limit, offset=page_params.offset
    )

    studies: list[Study] = [
        _create_study_from_project(prj) for prj in projects_page.data
    ]

    return create_page(
        studies,
        projects_page.meta.total,
        page_params,
    )


@router.get(
    "/{study_id:uuid}",
    response_model=Study,
    responses={**_COMMON_ERROR_RESPONSES},
)
async def get_study(
    study_id: StudyID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    """

    New in *version 0.5.0*
    """
    project: ProjectGet = await webserver_api.get_project(project_id=study_id)
    return _create_study_from_project(project)


@router.post(
    "/{study_id:uuid}:clone",
    response_model=Study,
    status_code=status.HTTP_201_CREATED,
    responses={**_COMMON_ERROR_RESPONSES},
)
async def clone_study(
    study_id: StudyID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    project: ProjectGet = await webserver_api.clone_project(
        project_id=study_id, hidden=False
    )
    return _create_study_from_project(project)


@router.get(
    "/{study_id:uuid}/ports",
    response_model=OnePage[StudyPort],
    responses={**_COMMON_ERROR_RESPONSES},
)
async def list_study_ports(
    study_id: StudyID,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    """Lists metadata on ports of a given study

    New in *version 0.5.0*
    """
    project_ports: list[StudyPort] = await webserver_api.get_project_metadata_ports(
        project_id=study_id
    )
    return OnePage[StudyPort](items=project_ports)

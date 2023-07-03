import logging
from typing import Any

from fastapi import APIRouter, Depends

from ...core.settings import BasicSettings
from ...models.schemas.studies import Study, StudyID, StudyPort
from ...services.webserver import AuthSession
from ..dependencies.webserver import get_webserver_session

_logger = logging.getLogger(__name__)
router = APIRouter()
settings = BasicSettings.create_from_envs()


@router.get(
    "/",
    response_model=list[Study],
    include_in_schema=settings.API_SERVER_DEV_FEATURES_ENABLED,
)
async def list_studies(study_id: StudyID):
    raise NotImplementedError(
        f"list_studies {study_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )


@router.get(
    "/{study_id}",
    response_model=Study,
    include_in_schema=settings.API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_study(study_id: StudyID):
    raise NotImplementedError(
        f"get_study {study_id=}. SEE https://github.com/ITISFoundation/osparc-simcore/issues/4177"
    )


@router.get(
    "/{study_id}/ports",
    response_model=list[StudyPort],
    include_in_schema=settings.API_SERVER_DEV_FEATURES_ENABLED,
)
async def list_study_ports(
    study_id: StudyID,
    webserver_api: AuthSession = Depends(get_webserver_session),
):
    """Lists metadata on ports of a given study

    New in *version 0.5.0* (only with API_SERVER_DEV_FEATURES_ENABLED=1)
    """
    project_ports: list[
        dict[str, Any]
    ] = await webserver_api.get_project_metadata_ports(project_id=study_id)
    return project_ports

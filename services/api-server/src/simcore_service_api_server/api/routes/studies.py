""" Studies collections


"""
import logging

from fastapi import APIRouter, Depends

from ...core.settings import BasicSettings
from ...models.schemas.studies import StudyPort
from ..dependencies.webserver import AuthSession, get_webserver_session

logger = logging.getLogger(__name__)
router = APIRouter()
settings = BasicSettings.create_from_envs()

#
# studies/{project_id}
#


@router.get(
    "/{study_id}/ports",
    response_model=list[StudyPort],
    include_in_schema=settings.API_SERVER_DEV_FEATURES_ENABLED,
)
def list_study_ports(
    client: AuthSession = Depends(get_webserver_session),
):
    """Lists metadata on ports of a given study

    New in *version 0.5.0* (only with API_SERVER_DEV_FEATURES_ENABLED=1)
    """
    # GET /projects/{project_id}/metadata/ports

    raise NotImplementedError()

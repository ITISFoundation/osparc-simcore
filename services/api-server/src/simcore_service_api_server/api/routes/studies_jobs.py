import logging

from fastapi import APIRouter

from ...core.settings import BasicSettings
from ...models.schemas.studies import Study, StudyID, StudyPort

_logger = logging.getLogger(__name__)
router = APIRouter()
settings = BasicSettings.create_from_envs()


@router.post(
    "/studies/{study_uid}/job",
    response_model=list[Study],
    include_in_schema=settings.API_SERVER_DEV_FEATURES_ENABLED,
)
async def create_study_job(study_uid: StudyID):
    raise NotImplementedError(f"list_studies {study_uid=}")


@router.post(
    "/studies/{study_uid}/job/{job_id}:start",
    response_model=Study,
    include_in_schema=settings.API_SERVER_DEV_FEATURES_ENABLED,
)
async def start_study_job(study_uid: StudyID):
    raise NotImplementedError(f"get_study {study_uid=}")


@router.get(
    "/studies/{study_uid}/job",
    response_model=list[StudyPort],
    include_in_schema=settings.API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_study_job_inputs(
    study_uid: StudyID,
):
    raise NotImplementedError(f"get_study {study_uid=}")

from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from simcore_service_api_server.models.schemas.studies import StudyID

from ._service_jobs import JobService
from .models.api_resources import compose_resource_name
from .models.schemas.jobs import Job

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


class StudyService:
    _job_service: JobService

    def __init__(
        self,
        job_service: JobService,
    ):
        self._job_service = job_service

    async def list_jobs(
        self,
        *,
        # filters
        study_id: StudyID | None = None,
        # pagination
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_PAGINATION_LIMIT,
    ) -> tuple[list[Job], PageMetaInfoLimitOffset]:
        """Lists all solver jobs for a user with pagination"""

        # 1. Compose job parent resource name prefix
        collection_or_resource_ids: list[str] = [
            "study",  # study_id, "jobs",
        ]
        if study_id:
            collection_or_resource_ids.append(f"{study_id}")

        job_parent_resource_name_prefix = compose_resource_name(
            *collection_or_resource_ids
        )

        # Use the common implementation from JobService
        return await self._job_service.list_jobs_by_resource_prefix(
            offset=offset,
            limit=limit,
            job_parent_resource_name_prefix=job_parent_resource_name_prefix,
        )

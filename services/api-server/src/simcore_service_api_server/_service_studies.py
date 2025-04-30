from models_library.products import ProductName
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID
from simcore_service_api_server.models.schemas.studies import StudyID

from ._service_jobs import JobService
from .models.api_resources import compose_resource_name
from .models.schemas.jobs import Job

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


class StudyService:
    _job_service: JobService

    # context
    _user_id: UserID
    _product_name: ProductName

    def __init__(
        self,
        job_service: JobService,
        user_id: UserID,
        product_name: ProductName,
    ):
        self._job_service = job_service
        self._user_id = user_id
        self._product_name = product_name

        # context
        if user_id != self._job_service._user_id:
            msg = f"User ID {user_id} does not match job service user ID {self._job_service._user_id}"
            raise ValueError(msg)
        if product_name != self._job_service._product_name:
            msg = f"Product name {product_name} does not match job service product name {self._job_service._product_name}"
            raise ValueError(msg)

        self._user_id = user_id
        self._product_name = product_name

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

from dataclasses import dataclass

from models_library.products import ProductName
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID

from ._service_jobs import JobService
from ._service_utils import check_user_product_consistency
from .models.api_resources import compose_resource_name
from .models.schemas.jobs import Job
from .models.schemas.studies import StudyID

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


@dataclass(frozen=True, kw_only=True)
class StudyService:
    job_service: JobService
    user_id: UserID
    product_name: ProductName

    def __post_init__(self):
        check_user_product_consistency(
            service_cls_name=self.__class__.__name__,
            service_provider=self.job_service,
            user_id=self.user_id,
            product_name=self.product_name,
        )

    async def list_jobs(
        self,
        *,
        filter_by_study_id: StudyID | None = None,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[list[Job], PageMetaInfoLimitOffset]:
        """Lists all solver jobs for a user with pagination"""

        # 1. Compose job parent resource name prefix
        collection_or_resource_ids: list[str] = [
            "study",  # study_id, "jobs",
        ]
        if filter_by_study_id:
            collection_or_resource_ids.append(f"{filter_by_study_id}")

        job_parent_resource_name = compose_resource_name(*collection_or_resource_ids)

        # 2. list jobs under job_parent_resource_name
        return await self.job_service.list_jobs(
            job_parent_resource_name=job_parent_resource_name,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )

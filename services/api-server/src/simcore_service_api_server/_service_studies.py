from dataclasses import dataclass

from models_library.products import ProductName
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
)
from models_library.users import UserID

from ._service_jobs import JobService
from ._service_utils import check_user_product_consistency

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

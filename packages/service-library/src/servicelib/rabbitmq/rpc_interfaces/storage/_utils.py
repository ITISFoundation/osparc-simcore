from typing import Final

from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobFilter
from models_library.products import ProductName
from models_library.users import UserID

ASYNC_JOB_CLIENT_NAME: Final[str] = "STORAGE"


def get_async_job_filter(user_id: UserID, product_name: ProductName) -> AsyncJobFilter:
    return AsyncJobFilter(
        user_id=user_id,
        product_name=product_name,
        client_name=ASYNC_JOB_CLIENT_NAME,
    )

from dataclasses import dataclass
from functools import partial

from celery_library.async_jobs import submit_job
from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobGet,
)
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata
from servicelib.celery.task_manager import TaskManager

from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.domain.celery_models import (
    ApiServerOwnerMetadata,
)

_exception_mapper = partial(service_exception_mapper, service_name="Storage")


@dataclass(frozen=True, kw_only=True)
class StorageService:
    _task_manager: TaskManager
    _user_id: UserID
    _product_name: ProductName

    @_exception_mapper(rpc_exception_map={})
    async def start_data_export(
        self,
        paths_to_export: list[PathToExport],
    ) -> AsyncJobGet:
        return await submit_job(
            self._task_manager,
            execution_metadata=ExecutionMetadata(name="export_data_as_download_link"),
            owner_metadata=OwnerMetadata.model_validate(
                ApiServerOwnerMetadata(user_id=self._user_id, product_name=self._product_name).model_dump()
            ),
            user_id=self._user_id,
            product_name=self._product_name,
            paths_to_export=paths_to_export,
        )

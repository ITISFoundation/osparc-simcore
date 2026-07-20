import datetime
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final

from celery_library.async_jobs import submit_job, wait_and_get_job_result
from models_library.api_schemas_async_jobs.async_jobs import (
    AsyncJobGet,
)
from models_library.api_schemas_webserver.storage import PathToExport
from models_library.celery import OwnerMetadata, TaskExecutionMetadata
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID
from models_library.users import UserID
from servicelib.celery.async_jobs.storage.paths import submit_delete_paths_task
from servicelib.celery.task_manager import TaskManager

from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.domain.celery_models import (
    ApiServerOwnerMetadata,
)

_exception_mapper = partial(service_exception_mapper, service_name="Storage")
_PROJECT_DELETION_MAX_TIMEOUT: Final[datetime.timedelta] = datetime.timedelta(minutes=30)
_SIMCORE_LOCATION: Final[LocationID] = 0


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
            execution_metadata=TaskExecutionMetadata(name="export_data_as_download_link"),
            owner_metadata=OwnerMetadata.model_validate(
                ApiServerOwnerMetadata(user_id=self._user_id, product_name=self._product_name).model_dump()
            ),
            user_id=self._user_id,
            product_name=self._product_name,
            paths_to_export=paths_to_export,
        )

    @_exception_mapper(rpc_exception_map={})
    async def delete_project_s3_assets(self, project_id: ProjectID) -> None:
        owner_metadata = OwnerMetadata.model_validate(
            ApiServerOwnerMetadata(user_id=self._user_id, product_name=self._product_name).model_dump()
        )
        job_id, *_ = await submit_delete_paths_task(
            self._task_manager,
            owner_metadata=owner_metadata,
            user_id=self._user_id,
            product_name=self._product_name,
            location_id=_SIMCORE_LOCATION,
            paths={Path(f"{project_id}")},
        )
        async for _ in wait_and_get_job_result(
            self._task_manager,
            owner_metadata=owner_metadata,
            job_id=job_id,
            stop_after=_PROJECT_DELETION_MAX_TIMEOUT,
        ):
            pass

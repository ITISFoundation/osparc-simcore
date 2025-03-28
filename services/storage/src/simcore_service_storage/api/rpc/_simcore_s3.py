from celery.exceptions import CeleryError  # type: ignore[import-untyped]
from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.api_schemas_rpc_async_jobs.exceptions import JobSchedulerError
from models_library.api_schemas_storage.data_export_async_jobs import (
    AccessRightError,
    DataExportTaskStartInput,
)
from models_library.api_schemas_storage.storage_schemas import FoldersBody
from servicelib.rabbitmq import RPCRouter

from ...datcore_dsm import DatCoreDataManager
from ...dsm import get_dsm_provider
from ...exceptions.errors import FileAccessRightError
from ...modules.celery import get_celery_client
from ...modules.datcore_adapter.datcore_adapter_exceptions import DatcoreAdapterError
from ...simcore_s3_dsm import SimcoreS3DataManager
from .._worker_tasks._simcore_s3 import data_export, deep_copy_files_from_project

router = RPCRouter()


@router.expose(reraise_if_error_type=None)
async def copy_folders_from_project(
    app: FastAPI,
    job_id_data: AsyncJobNameData,
    body: FoldersBody,
) -> AsyncJobGet:
    task_uuid = await get_celery_client(app).send_task(
        deep_copy_files_from_project.__name__,
        task_context=job_id_data.model_dump(),
        user_id=job_id_data.user_id,
        body=body,
    )

    return AsyncJobGet(job_id=task_uuid)


@router.expose(
    reraise_if_error_type=(
        AccessRightError,
        JobSchedulerError,
    )
)
async def start_data_export(
    app: FastAPI,
    data_export_start: DataExportTaskStartInput,
    job_id_data: AsyncJobNameData,
) -> AsyncJobGet:
    assert app  # nosec

    dsm = get_dsm_provider(app).get(data_export_start.location_id)

    try:
        for _id in data_export_start.file_and_folder_ids:
            if isinstance(dsm, DatCoreDataManager):
                _ = await dsm.get_file(user_id=job_id_data.user_id, file_id=_id)
            elif isinstance(dsm, SimcoreS3DataManager):
                await dsm.can_read_file(user_id=job_id_data.user_id, file_id=_id)

    except (FileAccessRightError, DatcoreAdapterError) as err:
        raise AccessRightError(
            user_id=job_id_data.user_id,
            file_id=_id,
            location_id=data_export_start.location_id,
        ) from err

    try:
        task_uuid = await get_celery_client(app).send_task(
            data_export.__name__,
            task_context=job_id_data.model_dump(),
            user_id=job_id_data.user_id,
            paths_to_export=data_export_start.file_and_folder_ids,
        )
    except CeleryError as exc:
        raise JobSchedulerError(exc=f"{exc}") from exc
    return AsyncJobGet(
        job_id=task_uuid,
    )

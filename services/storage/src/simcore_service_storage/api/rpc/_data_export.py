from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobGet, AsyncJobId
from models_library.api_schemas_storage.data_export_async_jobs import (
    AccessRightError,
    DataExportError,
    DataExportTaskStartInput,
    InvalidFileIdentifierError,
)
from servicelib.rabbitmq import RPCRouter

from ...dsm import DatCoreDataManager, get_dsm_provider
from ...modules.datcore_adapter.datcore_adapter import DatcoreAdapterError
from ...simcore_s3_dsm import FileAccessRightError, SimcoreS3DataManager

router = RPCRouter()


@router.expose(
    reraise_if_error_type=(
        InvalidFileIdentifierError,
        AccessRightError,
        DataExportError,
    )
)
async def start_data_export(
    app: FastAPI, data_export_start: DataExportTaskStartInput
) -> AsyncJobGet:
    assert app  # nosec

    dsm = get_dsm_provider(app).get(data_export_start.location_id)

    try:
        for _id in data_export_start.file_and_folder_ids:
            if isinstance(dsm, DatCoreDataManager):
                _ = await dsm.get_file(user_id=data_export_start.user_id, file_id=_id)
            elif isinstance(dsm, SimcoreS3DataManager):
                await dsm.can_read_file(user_id=data_export_start.user_id, file_id=_id)

    except (FileAccessRightError, DatcoreAdapterError) as err:
        raise AccessRightError(
            user_id=data_export_start.user_id,
            file_id=_id,
            location_id=data_export_start.location_id,
        ) from err

    return AsyncJobGet(
        job_id=AsyncJobId(f"{uuid4()}"),
        job_name=", ".join(str(p) for p in data_export_start.file_and_folder_ids),
    )

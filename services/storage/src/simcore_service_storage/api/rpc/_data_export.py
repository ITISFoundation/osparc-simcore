from typing import cast
from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobGet, AsyncJobId
from models_library.api_schemas_storage.data_export_async_jobs import (
    AccessRightError,
    DataExportError,
    DataExportTaskStartInput,
    InvalidFileIdentifierError,
    InvalidLocationIdError,
)
from servicelib.rabbitmq import RPCRouter

from ...dsm import DatCoreDataManager, SimcoreS3DataManager, get_dsm_provider
from ...modules.datcore_adapter.datcore_adapter import DatcoreAdapterError
from ...simcore_s3_dsm import FileAccessRightError

router = RPCRouter()


@router.expose(
    reraise_if_error_type=(
        InvalidFileIdentifierError,
        AccessRightError,
        DataExportError,
    )
)
async def start_data_export(
    app: FastAPI, paths: DataExportTaskStartInput
) -> AsyncJobGet:
    assert app  # nosec

    if paths.location_id == SimcoreS3DataManager.get_location_id():
        dsm = cast(
            SimcoreS3DataManager,
            get_dsm_provider(app).get(SimcoreS3DataManager.get_location_id()),
        )
        try:
            for _id in paths.file_and_folder_ids:
                _ = await dsm.get_file(user_id=paths.user_id, file_id=_id)
        except FileAccessRightError as err:
            raise AccessRightError(
                user_id=paths.user_id,
                file_id=_id,
                location_id=DatCoreDataManager.get_location_id(),
            ) from err

    elif paths.location_id == DatCoreDataManager.get_location_id():
        dsm = cast(
            DatCoreDataManager,
            get_dsm_provider(app).get(DatCoreDataManager.get_location_id()),
        )
        try:
            for _id in paths.file_and_folder_ids:
                _ = await dsm.get_file(user_id=paths.user_id, file_id=_id)
        except DatcoreAdapterError as err:
            raise AccessRightError(
                user_id=paths.user_id,
                file_id=_id,
                location_id=DatCoreDataManager.get_location_id(),
            ) from err
    else:
        raise InvalidLocationIdError(location_id=paths.location_id)

    return AsyncJobGet(
        job_id=AsyncJobId(f"{uuid4()}"),
        job_name=", ".join(str(p) for p in paths.file_and_folder_ids),
    )

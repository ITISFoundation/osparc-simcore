from typing import cast
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
from simcore_service_storage.dsm import (
    DatCoreDataManager,
    SimcoreS3DataManager,
    get_dsm_provider,
)

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

    if paths.location_id != DatCoreDataManager.get_location_id():
        dsm = cast(
            SimcoreS3DataManager,
            get_dsm_provider(app).get(SimcoreS3DataManager.get_location_id()),
        )
    return AsyncJobGet(
        job_id=AsyncJobId(f"{uuid4()}"),
        job_name=", ".join(str(p) for p in paths.paths),
    )

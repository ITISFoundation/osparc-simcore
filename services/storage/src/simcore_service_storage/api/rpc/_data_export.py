from uuid import uuid4

from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobGet
from models_library.api_schemas_storage.rpc.data_export_async_jobs import (
    AccessRightError,
    DataExportError,
    DataExportTaskStartInput,
    InvalidFileIdentifierError,
)
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

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
    return AsyncJobGet(
        job_id=uuid4(),
        job_name=", ".join(str(p) for p in paths.paths),
    )


@router.expose()
async def get_user_jobs(app: FastAPI, user_id: UserID) -> list[AsyncJobGet]:
    assert app  # nosec
    assert user_id  # nosec
    return [AsyncJobGet(job_id=uuid4(), job_name="myjob")]

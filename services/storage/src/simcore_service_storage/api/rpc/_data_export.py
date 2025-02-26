from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobGet, AsyncJobId
from models_library.api_schemas_storage.data_export_async_jobs import (
    AccessRightError,
    DataExportError,
    DataExportTaskStartInput,
    InvalidFileIdentifierError,
)
from servicelib.rabbitmq import RPCRouter

from ...modules.celery.client import CeleryTaskQueueClient, TaskIDParts
from ...modules.celery.utils import get_celery_client

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

    client: CeleryTaskQueueClient = get_celery_client(app)

    task_id = await client.send_task(
        task_name="sync_archive",
        task_id_parts=TaskIDParts(
            user_id=paths.user_id, product_name=paths.product_name
        ),
        files=paths.paths,
    )

    return AsyncJobGet(
        job_id=AsyncJobId(task_id),
        job_name=", ".join(str(p) for p in paths.paths),
    )

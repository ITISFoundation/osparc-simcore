import logging

from celery import Task  # type: ignore[import-untyped]
from celery_library.models import TaskID
from celery_library.utils import get_fastapi_app
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompletionBody,
)
from models_library.projects_nodes_io import LocationID, StorageFileID
from models_library.users import UserID
from servicelib.logging_utils import log_context

from ...dsm import get_dsm_provider
from ...models import FileMetaData

_logger = logging.getLogger(__name__)


async def complete_upload_file(
    task: Task,
    task_id: TaskID,
    user_id: UserID,
    location_id: LocationID,
    file_id: StorageFileID,
    body: FileUploadCompletionBody,
) -> FileMetaData:
    assert task_id  # nosec
    with log_context(
        _logger,
        logging.INFO,
        msg=f"completing upload of file {user_id=}, {location_id=}, {file_id=}",
    ):
        dsm = get_dsm_provider(get_fastapi_app(task.app)).get(location_id)
        # NOTE: completing a multipart upload on AWS can take up to several minutes
        # if it returns slow we return a 202 - Accepted, the client will have to check later
        # for completeness
        return await dsm.complete_file_upload(file_id, user_id, body.parts)

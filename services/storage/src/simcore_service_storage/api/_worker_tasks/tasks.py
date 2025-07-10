import logging

from celery import Celery  # type: ignore[import-untyped]
from celery_library.task import register_task
from celery_library.types import register_celery_types, register_pydantic_types
from models_library.api_schemas_storage.export_data_async_jobs import AccessRightError
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompletionBody,
    FoldersBody,
)
from servicelib.logging_utils import log_context

from ...models import FileMetaData
from ._files import complete_upload_file
from ._paths import compute_path_size, delete_paths
from ._simcore_s3 import (
    deep_copy_files_from_project,
    export_data,
    export_data_as_download_link,
)

_logger = logging.getLogger(__name__)


def setup_worker_tasks(app: Celery) -> None:
    register_celery_types()
    register_pydantic_types(FileUploadCompletionBody, FileMetaData, FoldersBody)

    with log_context(_logger, logging.INFO, msg="worker task registration"):
        register_task(app, export_data, dont_autoretry_for=(AccessRightError,))
        register_task(
            app, export_data_as_download_link, dont_autoretry_for=(AccessRightError,)
        )
        register_task(app, compute_path_size)
        register_task(app, complete_upload_file)
        register_task(app, delete_paths)
        register_task(app, deep_copy_files_from_project)

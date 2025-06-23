from celery_library.common import create_app, create_task_manager
from celery_library.task_manager import CeleryTaskManager
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompletionBody,
    FoldersBody,
)
from settings_library.celery import CelerySettings

from ...models import FileMetaData


def setup_task_manager(app: FastAPI, celery_settings: CelerySettings) -> None:
    async def on_startup() -> None:
        app.state.celery_client = await create_task_manager(
            create_app(celery_settings), celery_settings
        )

        register_celery_types()
        register_pydantic_types(FileUploadCompletionBody, FileMetaData, FoldersBody)

    app.add_event_handler("startup", on_startup)


def get_task_manager_from_app(app: FastAPI) -> CeleryTaskManager:
    assert hasattr(app.state, "celery_client")  # nosec
    celery_client = app.state.celery_client
    assert isinstance(celery_client, CeleryTaskManager)  # nosec
    return celery_client

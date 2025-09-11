from celery_library.common import create_app, create_task_manager
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from settings_library.celery import CelerySettings

from ..celery_worker.worker_tasks.tasks import pydantic_types_to_register


def setup_task_manager(app: FastAPI, celery_settings: CelerySettings) -> None:
    async def on_startup() -> None:
        app.state.task_manager = await create_task_manager(
            create_app(celery_settings), celery_settings
        )

        register_celery_types()
        register_pydantic_types(*pydantic_types_to_register)

    app.add_event_handler("startup", on_startup)

from celery_library.common import create_app, create_task_manager
from celery_library.types import register_celery_types, register_pydantic_types
from fastapi import FastAPI
from models_library.api_schemas_rpc_async_jobs.async_jobs import AsyncJobFilter
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.celery.models import TaskFilter
from settings_library.celery import CelerySettings

from .._meta import APP_NAME
from ..celery_worker.worker_tasks.tasks import pydantic_types_to_register


def get_job_filter(user_id: UserID, product_name: ProductName) -> AsyncJobFilter:
    return AsyncJobFilter(
        user_id=user_id, product_name=product_name, client_name=APP_NAME
    )


def get_task_filter(user_id: UserID, product_name: ProductName) -> TaskFilter:
    job_filter = get_job_filter(user_id=user_id, product_name=product_name)
    return TaskFilter.model_validate(job_filter.model_dump())


def setup_task_manager(app: FastAPI, celery_settings: CelerySettings) -> None:
    async def on_startup() -> None:
        app.state.task_manager = await create_task_manager(
            create_app(celery_settings), celery_settings
        )

        register_celery_types()
        register_pydantic_types(*pydantic_types_to_register)

    app.add_event_handler("startup", on_startup)

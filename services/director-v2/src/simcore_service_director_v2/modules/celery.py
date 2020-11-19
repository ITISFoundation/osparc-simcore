import logging
from dataclasses import dataclass
from typing import List

from celery import Celery, Task
from celery.contrib.abortable import AbortableAsyncResult
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.settings.celery import CeleryConfig

from ..models.schemas.constants import UserID
from ..utils.client_decorators import handle_retry

logger = logging.getLogger(__name__)


def setup(app: FastAPI, settings: CeleryConfig) -> None:
    if not settings:
        settings = CeleryConfig.create_from_env()

    def on_startup() -> None:
        CeleryClient.create(
            app,
            client=Celery(
                settings.task_name,
                broker=settings.broker_url,
                backend=settings.result_backend,
            ),
            settings=settings,
        )

    async def on_shutdown() -> None:
        del app.state.celery_client

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class CeleryClient:
    client: Celery
    settings: CeleryConfig

    @classmethod
    def create(cls, app: FastAPI, *args, **kwargs) -> "CeleryClient":
        app.state.celery_client = cls(*args, **kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI) -> "CeleryClient":
        return app.state.celery_client

    @handle_retry(logger)
    def send_task(self, task_name: str, *args, **kwargs) -> Task:
        # TODO: check what can happen when exceptions are thrown (see [https://docs.celeryproject.org/en/2.4-archived/reference/celery.exceptions.html?highlight=exceptions#module-celery.exceptions])
        return self.client.send_task(task_name, *args, **kwargs)

    def send_computation_task(self, user_id: UserID, project_id: ProjectID) -> Task:
        return self.send_task(
            self.settings.task_name,
            expires=self.settings.publication_timeout,
            kwargs={"user_id": user_id, "project_id": str(project_id)},
        )

    @classmethod
    def abort_computation_tasks(cls, task_ids: List[str]) -> None:
        for task_id in task_ids:
            task_result = AbortableAsyncResult(task_id)
            if task_result:
                task_result.abort()

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from celery import Celery, Task, signature
from celery.canvas import Signature
from celery.contrib.abortable import AbortableAsyncResult
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.settings.celery import CeleryConfig

from ..core.errors import ConfigurationError
from ..models.schemas.constants import UserID

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


def _computation_task_signature(
    settings: CeleryConfig,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    routing_queue: str,
) -> Signature:
    """returns the signature of the computation task (see celery canvas)"""
    task_signature = signature(
        settings.task_name,
        queue=f"{settings.task_name}.{routing_queue}",
        kwargs={
            "user_id": user_id,
            "project_id": str(project_id),
            "node_id": str(node_id),
        },
    )
    return task_signature


@dataclass
class CeleryClient:
    client: Celery
    settings: CeleryConfig

    @classmethod
    def create(cls, app: FastAPI, *args, **kwargs) -> "CeleryClient":
        app.state.celery_client = cls(*args, **kwargs)
        app.state.celery_client.client.conf.update(result_extended=True)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI) -> "CeleryClient":
        if not hasattr(app.state, "celery_client"):
            raise ConfigurationError(
                "Celery client is not available. Please check the configuration."
            )
        return app.state.celery_client

    def send_single_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        single_tasks: Dict[str, Any],
        callback: Callable,
    ) -> Dict[str, Task]:
        async_tasks = {}
        for node_id, node_data in single_tasks.items():
            celery_task_signature = _computation_task_signature(
                self.settings,
                user_id,
                project_id,
                node_id,
                node_data["runtime_requirements"],
            )
            async_tasks[node_id] = celery_task = celery_task_signature.apply_async()
            logger.info("Published celery task %s", celery_task)
            celery_task.then(callback)
        return async_tasks

    @classmethod
    def abort_computation_tasks(cls, task_ids: List[str]) -> None:
        for task_id in task_ids:
            task_result = AbortableAsyncResult(task_id)
            if task_result:
                task_result.abort()

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List

from celery import Celery, Task, signature
from celery.canvas import Signature
from celery.contrib.abortable import AbortableAsyncResult
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from settings_library.celery import CelerySettings

from ..core.errors import ConfigurationError
from ..models.domains.comp_tasks import Image
from ..models.schemas.constants import UserID

logger = logging.getLogger(__name__)


def setup(app: FastAPI, settings: CelerySettings) -> None:
    def on_startup() -> None:
        CeleryClient.create(
            app,
            client=Celery(
                settings.CELERY_TASK_NAME,
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
    settings: CelerySettings,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    routing_queue: str,
) -> Signature:
    """returns the signature of the computation task (see celery canvas)"""
    task_signature = signature(
        settings.CELERY_TASK_NAME,
        queue=f"{settings.CELERY_TASK_NAME}.{routing_queue}",
        kwargs={
            "user_id": user_id,
            "project_id": str(project_id),
            "node_id": str(node_id),
        },
    )
    return task_signature


@dataclass
class CeleryTaskIn:
    node_id: NodeID
    runtime_requirements: str

    @classmethod
    def from_node_image(cls, node_id: NodeID, node_image: Image) -> "CeleryTaskIn":
        # NOTE: to keep compatibility the queues are currently defined as .cpu, .gpu, .mpi.
        reqs = []
        if node_image.requires_gpu:
            reqs.append("gpu")
        if node_image.requires_mpi:
            reqs.append("mpi")
        req = ":".join(reqs)

        return cls(node_id=node_id, runtime_requirements=req or "cpu")


CeleryTaskOut = Task


@dataclass
class CeleryClient:
    client: Celery
    settings: CelerySettings

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

    def send_computation_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        single_tasks: List[CeleryTaskIn],
        callback: Callable,
    ) -> Dict[NodeID, CeleryTaskOut]:
        async_tasks = {}
        for task in single_tasks:
            celery_task_signature = _computation_task_signature(
                self.settings,
                user_id,
                project_id,
                task.node_id,
                task.runtime_requirements,
            )
            async_tasks[
                task.node_id
            ] = celery_task = celery_task_signature.apply_async()
            logger.info("Published celery task %s", celery_task)
            celery_task.then(callback)
        return async_tasks

    @classmethod
    def abort_computation_tasks(cls, task_ids: List[str]) -> None:
        for task_id in task_ids:
            task_result = AbortableAsyncResult(task_id)
            if task_result:
                task_result.abort()
                logger.info(
                    "Aborted celery task %s, status: %s",
                    task_id,
                    task_result.is_aborted(),
                )

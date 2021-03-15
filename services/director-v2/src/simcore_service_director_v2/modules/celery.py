import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from celery import Celery, Task, group, signature
from celery.canvas import Signature, chord
from celery.contrib.abortable import AbortableAsyncResult
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.settings.celery import CeleryConfig

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

    def send_computation_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        topologically_sorted_nodes: List[Dict[str, Dict[str, Any]]],
    ) -> Task:
        def _create_task_signature(
            self,
            user_id: UserID,
            project_id: ProjectID,
            node_id: NodeID,
            routing_queue: str,
        ) -> Signature:
            task_signature = signature(
                self.settings.task_name,
                queue=f"{self.settings.task_name}.{routing_queue}",
                kwargs={
                    "user_id": user_id,
                    "project_id": str(project_id),
                    "node_id": str(node_id),
                },
            )
            return task_signature

        # create the // tasks
        celery_groups = []
        for node_group in topologically_sorted_nodes:
            celery_groups.append(
                group(
                    [
                        _create_task_signature(
                            self,
                            user_id,
                            project_id,
                            node_id,
                            node_data["runtime_requirements"],
                        )
                        for node_id, node_data in node_group.items()
                    ]
                )
            )

        def _create_celery_flow(grps, index: int = 0):
            if index < len(grps):
                body = _create_celery_flow(grps, index + 1)
                return chord(header=grps[index], body=body) if body else grps[index]
            return None

        celery_flow = _create_celery_flow(celery_groups)

        # publish the tasks through Celery
        task = celery_flow.apply_async()
        logger.debug("created celery workflow: %s", str(celery_flow))
        return task

    @classmethod
    def abort_computation_tasks(cls, task_ids: List[str]) -> None:
        for task_id in task_ids:
            task_result = AbortableAsyncResult(task_id)
            if task_result:
                task_result.abort()

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List
from uuid import uuid4

from dask.distributed import Client, Future, fire_and_forget
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ..core.errors import ConfigurationError
from ..core.settings import DaskSchedulerSettings
from ..models.domains.comp_tasks import Image
from ..models.schemas.constants import UserID

logger = logging.getLogger(__name__)


def setup(app: FastAPI, settings: DaskSchedulerSettings) -> None:
    def on_startup() -> None:
        DaskClient.create(
            app,
            client=Client(
                f"tcp://{settings.DASK_SCHEDULER_HOST}:{settings.DASK_SCHEDULER_PORT}",
            ),
            settings=settings,
        )

    async def on_shutdown() -> None:
        app.state.dask_client.client.close()
        del app.state.dask_client  # type: ignore

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class DaskTaskIn:
    node_id: NodeID
    runtime_requirements: str

    @classmethod
    def from_node_image(cls, node_id: NodeID, node_image: Image) -> "DaskTaskIn":
        # NOTE: to keep compatibility the queues are currently defined as .cpu, .gpu, .mpi.
        reqs = []
        if node_image.requires_gpu:
            reqs.append("gpu")
        if node_image.requires_mpi:
            reqs.append("mpi")
        req = ":".join(reqs)

        return cls(node_id=node_id, runtime_requirements=req or "cpu")


@dataclass
class DaskClient:
    client: Client
    settings: DaskSchedulerSettings

    _taskid_to_future_map: Dict[str, Future] = field(default_factory=dict)

    @classmethod
    def create(cls, app: FastAPI, *args, **kwargs) -> "DaskClient":
        app.state.dask_client = cls(*args, **kwargs)
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI) -> "DaskClient":
        if not hasattr(app.state, "dask_client"):
            raise ConfigurationError(
                "Dask client is not available. Please check the configuration."
            )
        return app.state.dask_client

    def send_computation_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        single_tasks: List[DaskTaskIn],
        _callback: Callable,
    ):
        def sidecar_fun(job_id: str, user_id: str, project_id: str, node_id: str):

            import asyncio

            from dask.distributed import get_worker
            from simcore_service_sidecar.cli import run_sidecar

            def _is_aborted_cb() -> bool:
                w = get_worker()
                t = w.tasks.get(w.get_current_task())
                return t is None

            asyncio.run(
                run_sidecar(
                    job_id, user_id, project_id, node_id, is_aborted_cb=_is_aborted_cb
                )
            )

        def _done_callback(dask_future: Future):
            logger.debug("Dask future %s completed", dask_future.key)
            _callback()

        for task in single_tasks:
            job_id = f"dask_{uuid4()}"
            task_future = self.client.submit(
                sidecar_fun,
                job_id,
                f"{user_id}",
                f"{project_id}",
                f"{task.node_id}",
                key=job_id,
            )
            task_future.add_done_callback(_done_callback)
            self._taskid_to_future_map[job_id] = task_future
            fire_and_forget(task_future)  # this should ensure the task will run
            logger.debug("Dask task %s started", task_future.key)

    def abort_computation_tasks(self, task_ids: List[str]) -> None:

        for task_id in task_ids:
            task_future = self._taskid_to_future_map.pop(task_id, None)
            if task_future:
                task_future.cancel()
                logger.debug("Dask task %s cancelled", task_future.key)

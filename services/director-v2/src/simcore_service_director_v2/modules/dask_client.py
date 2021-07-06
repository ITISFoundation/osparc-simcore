from dataclasses import dataclass
from typing import Callable, List

from dask.distributed import Client, fire_and_forget
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ..core.errors import ConfigurationError
from ..core.settings import DaskSchedulerSettings
from ..models.domains.comp_tasks import Image
from ..models.schemas.constants import UserID


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
        del app.state.dask_client

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
        callback: Callable,
    ):
        def sidecar_fun(job_id: str, user_id: str, project_id: str, node_id: str):
            from simcore_service_sidecar.cli import run_sidecar
            from simcore_service_sidecar.utils import wrap_async_call

            wrap_async_call(run_sidecar(job_id, user_id, project_id, node_id))

        for task in single_tasks:
            task_future = self.client.submit(
                sidecar_fun, "dask", f"{user_id}", f"{project_id}", f"{task.node_id}"
            )
            fire_and_forget(task_future)

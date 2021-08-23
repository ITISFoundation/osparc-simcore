import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Union
from uuid import uuid4

from dask.distributed import Client, Future, fire_and_forget
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_random

from ..core.errors import ConfigurationError
from ..core.settings import DaskSchedulerSettings
from ..models.schemas.constants import UserID
from ..models.schemas.services import NodeRequirements

logger = logging.getLogger(__name__)


dask_retry_policy = dict(
    wait=wait_random(5, 8),
    stop=stop_after_attempt(20),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def setup(app: FastAPI, settings: DaskSchedulerSettings) -> None:
    @retry(**dask_retry_policy)
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
        tasks: Dict[NodeID, NodeRequirements],
        callback: Callable[[], None],
        remote_fct: Callable = None,
    ):
        """actually sends the function remote_fct to be remotely executed. if None is kept then the default
        function that runs container will be started."""

        def _done_dask_callback(dask_future: Future):
            job_id = dask_future.key
            logger.debug("Dask future %s completed", job_id)
            # remove the future from the dict to remove any handle to the future, so the worker can free the memory
            self._taskid_to_future_map.pop(job_id)
            callback()

        def comp_sidecar_fct(
            job_id: str, user_id: str, project_id: str, node_id: str
        ) -> None:
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

        if remote_fct is None:
            remote_fct = comp_sidecar_fct

        def _from_node_reqs_to_dask_resources(
            node_reqs: NodeRequirements,
        ) -> Dict[str, Union[int, float]]:
            """Dask resources are set such as {"CPU": X.X, "GPU": Y.Y, "RAM": INT}"""
            dask_resources = node_reqs.dict(exclude_unset=True, by_alias=True)
            logger.debug("transformed to dask resources: %s", dask_resources)
            return dask_resources

        for node_id, node_reqs in tasks.items():
            job_id = f"dask_{uuid4()}"
            task_future = self.client.submit(
                remote_fct,
                job_id,
                f"{user_id}",
                f"{project_id}",
                f"{node_id}",
                key=job_id,
                resources=_from_node_reqs_to_dask_resources(node_reqs),
                retries=2,
            )
            task_future.add_done_callback(_done_dask_callback)
            self._taskid_to_future_map[job_id] = task_future
            fire_and_forget(
                task_future
            )  # this should ensure the task will run even if the future goes out of scope
            logger.debug("Dask task %s started", task_future.key)

    def abort_computation_tasks(self, task_ids: List[str]) -> None:

        for task_id in task_ids:
            task_future = self._taskid_to_future_map.get(task_id)
            if task_future:
                task_future.cancel()
                logger.debug("Dask task %s cancelled", task_future.key)

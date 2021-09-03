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
from ..models.domains.comp_tasks import Image
from ..models.schemas.constants import ClusterID, UserID
from ..models.schemas.services import NodeRequirements

logger = logging.getLogger(__name__)


dask_retry_policy = dict(
    wait=wait_random(5, 8),
    stop=stop_after_attempt(20),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

CLUSTER_RESOURCE_MOCK_USAGE: float = 1e-9


def setup(app: FastAPI, settings: DaskSchedulerSettings) -> None:
    @retry(**dask_retry_policy)
    async def on_startup() -> None:
        DaskClient.create(
            app,
            client=await Client(
                f"tcp://{settings.DASK_SCHEDULER_HOST}:{settings.DASK_SCHEDULER_PORT}",
                asynchronous=True,
                name="director-v2-client",
            ),
            settings=settings,
        )

    async def on_shutdown() -> None:
        await app.state.dask_client.client.close()
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
        cluster_id: ClusterID,
        tasks: Dict[NodeID, Image],
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

        def _comp_sidecar_fct(
            job_id: str, user_id: int, project_id: ProjectID, node_id: NodeID
        ) -> None:
            """This function is serialized by the Dask client and sent over to the Dask sidecar(s)
            Therefore, (screaming here) DO NOT MOVE THAT IMPORT ANYWHERE ELSE EVER!!"""
            from simcore_service_dask_sidecar.tasks import run_task_in_service

            run_task_in_service(job_id, user_id, project_id, node_id)

        if remote_fct is None:
            remote_fct = _comp_sidecar_fct

        def _from_node_reqs_to_dask_resources(
            node_reqs: NodeRequirements,
        ) -> Dict[str, Union[int, float]]:
            """Dask resources are set such as {"CPU": X.X, "GPU": Y.Y, "RAM": INT}"""
            dask_resources = node_reqs.dict(exclude_unset=True, by_alias=True)
            logger.debug("transformed to dask resources: %s", dask_resources)
            return dask_resources

        for node_id, node_image in tasks.items():
            # NOTE: the job id is used to create a folder in the sidecar,
            # so it must be a valid file name too
            # Also, it must be unique
            # and it is shown in the Dask scheduler dashboard website
            job_id = f"{node_image.name}_{node_image.tag}__projectid_{project_id}__nodeid_{node_id}__{uuid4()}"
            dask_resources = _from_node_reqs_to_dask_resources(
                node_image.node_requirements
            )
            # add the cluster ID here
            dask_resources.update(
                {
                    f"{self.settings.DASK_CLUSTER_ID_PREFIX}{cluster_id}": CLUSTER_RESOURCE_MOCK_USAGE
                }
            )
            task_future = self.client.submit(
                remote_fct,
                job_id,
                user_id,
                project_id,
                node_id,
                key=job_id,
                resources=dask_resources,
                retries=0,
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

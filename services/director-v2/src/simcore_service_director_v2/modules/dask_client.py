import collections
import logging
from dataclasses import dataclass, field
from pprint import pformat
from typing import Any, Callable, Dict, List, Union
from uuid import uuid4

from dask.distributed import Client, Future, fire_and_forget
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_random

from ..core.errors import (
    ConfigurationError,
    DaskClientNotConnectedError,
    InsuficientComputationalResourcesError,
    MissingComputationalResourcesError,
)
from ..core.settings import DaskSchedulerSettings
from ..models.domains.comp_tasks import Image
from ..models.schemas.constants import ClusterID, UserID
from ..models.schemas.services import NodeRequirements

logger = logging.getLogger(__name__)


dask_retry_policy = dict(
    wait=wait_random(5, 10),
    stop=stop_after_attempt(60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

CLUSTER_RESOURCE_MOCK_USAGE: float = 1e-9


def _check_cluster_able_to_run_pipeline(
    node_id: NodeID,
    scheduler_info: Dict[str, Any],
    task_resources: Dict[str, Any],
    node_image: Image,
    cluster_id_prefix: str,
    cluster_id: ClusterID,
):
    logger.debug("Dask scheduler infos: %s", pformat(scheduler_info))
    workers = scheduler_info.get("workers", {})

    def can_task_run_on_worker(
        task_resources: Dict[str, Any], worker_resources: Dict[str, Any]
    ) -> bool:
        def gen_check(task_resources: Dict[str, Any], worker_resources: Dict[str, Any]):
            for r in task_resources:
                yield worker_resources.get(r, 0) >= task_resources[r]

        return all(gen_check(task_resources, worker_resources))

    def cluster_missing_resources(
        task_resources: Dict[str, Any], cluster_resources: Dict[str, Any]
    ) -> List[str]:
        return [r for r in task_resources if r not in cluster_resources]

    cluster_resources_counter = collections.Counter()
    can_a_worker_run_task = False
    for worker in workers:
        worker_resources = workers[worker].get("resources", {})
        if worker_resources.get(f"{cluster_id_prefix}{cluster_id}"):
            cluster_resources_counter.update(worker_resources)
            if can_task_run_on_worker(task_resources, worker_resources):
                can_a_worker_run_task = True
    all_available_resources_in_cluster = dict(cluster_resources_counter)

    logger.debug(
        "Dask scheduler total available resources in cluster %s: %s, task needed resources %s",
        cluster_id,
        pformat(all_available_resources_in_cluster),
        pformat(task_resources),
    )

    if can_a_worker_run_task:
        return

    # check if we have missing resources
    if missing_resources := cluster_missing_resources(
        task_resources, all_available_resources_in_cluster
    ):
        raise MissingComputationalResourcesError(
            node_id=node_id,
            msg=f"Service {node_image.name}:{node_image.tag} cannot be scheduled on cluster {cluster_id}: missing resource {missing_resources}",
        )

    # well then our workers are not powerful enough
    raise InsuficientComputationalResourcesError(
        node_id=node_id,
        msg=f"Service {node_image.name}:{node_image.tag} cannot be scheduled on cluster {cluster_id}: insuficient resources",
    )


def _from_node_reqs_to_dask_resources(
    node_reqs: NodeRequirements,
) -> Dict[str, Union[int, float]]:
    """Dask resources are set such as {"CPU": X.X, "GPU": Y.Y, "RAM": INT}"""
    dask_resources = node_reqs.dict(exclude_unset=True, by_alias=True)
    logger.debug("transformed to dask resources: %s", dask_resources)
    return dask_resources


def setup(app: FastAPI, settings: DaskSchedulerSettings) -> None:
    @retry(**dask_retry_policy)
    async def on_startup() -> None:
        await DaskClient.create(
            app,
            settings=settings,
        )

    async def on_shutdown() -> None:
        await DaskClient.delete(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class DaskClient:
    app: FastAPI
    client: Client
    settings: DaskSchedulerSettings

    _taskid_to_future_map: Dict[str, Future] = field(default_factory=dict)

    @classmethod
    async def create(
        cls, app: FastAPI, settings: DaskSchedulerSettings
    ) -> "DaskClient":
        app.state.dask_client = cls(
            app=app,
            client=await Client(
                f"tcp://{settings.DASK_SCHEDULER_HOST}:{settings.DASK_SCHEDULER_PORT}",
                asynchronous=True,
                name="director-v2-client",
            ),  # type: ignore
            settings=settings,
        )
        return cls.instance(app)

    @classmethod
    def instance(cls, app: FastAPI) -> "DaskClient":
        if not hasattr(app.state, "dask_client"):
            raise ConfigurationError(
                "Dask client is not available. Please check the configuration."
            )
        return app.state.dask_client

    @classmethod
    async def delete(cls, app: FastAPI) -> None:
        if not hasattr(app.state, "dask_client"):
            raise ConfigurationError(
                "Dask client is not available. Please check the configuration."
            )
        await app.state.dask_client.client.close()
        del app.state.dask_client  # type: ignore

    async def reconnect_client(self):
        await self.client.close()
        self.client = await Client(
            f"tcp://{self.settings.DASK_SCHEDULER_HOST}:{self.settings.DASK_SCHEDULER_PORT}",
            asynchronous=True,
            name="director-v2-client",
        )  # type: ignore

    async def send_computation_tasks(
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
            from simcore_service_dask_sidecar.tasks import (
                run_task_in_service,  # type: ignore
            )

            run_task_in_service(job_id, user_id, project_id, node_id)

        if remote_fct is None:
            remote_fct = _comp_sidecar_fct

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

            client_status = self.client.status
            if client_status not in "running":
                raise DaskClientNotConnectedError()
                # await self.reconnect_client()

            _check_cluster_able_to_run_pipeline(
                node_id=node_id,
                scheduler_info=scheduler_info,
                task_resources=dask_resources,
                node_image=node_image,
                cluster_id_prefix=self.settings.DASK_CLUSTER_ID_PREFIX,  # type: ignore
                cluster_id=cluster_id,
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

    async def abort_computation_tasks(self, task_ids: List[str]) -> None:

        for task_id in task_ids:
            task_future = self._taskid_to_future_map.get(task_id)
            if task_future:
                await task_future.cancel()
                logger.debug("Dask task %s cancelled", task_future.key)

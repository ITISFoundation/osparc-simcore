import asyncio
import collections
import contextlib
import functools
import logging
import os
import socket
from dataclasses import dataclass, field
from pprint import pformat
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Tuple, Union

import dask.distributed
import distributed
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import (
    TaskCancelEvent,
    TaskLogEvent,
    TaskProgressEvent,
    TaskStateEvent,
)
from dask_task_models_library.container_tasks.io import (
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic.networks import AnyUrl
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.wait import wait_random

from ..core.errors import (
    ComputationalBackendNotConnectedError,
    ConfigurationError,
    InsuficientComputationalResourcesError,
    MissingComputationalResourcesError,
)
from ..core.settings import DaskSchedulerSettings
from ..models.domains.comp_tasks import Image
from ..models.schemas.constants import ClusterID, UserID
from ..models.schemas.services import NodeRequirements
from ..utils.dask import (
    UserCompleteCB,
    compute_input_data,
    compute_output_data_schema,
    compute_service_log_file_upload_link,
    done_dask_callback,
    generate_dask_job_id,
)

logger = logging.getLogger(__name__)


dask_retry_policy = dict(
    wait=wait_random(5, 10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

CLUSTER_RESOURCE_MOCK_USAGE: float = 1e-9


def setup(app: FastAPI, settings: DaskSchedulerSettings) -> None:
    @retry(**dask_retry_policy)
    async def on_startup() -> None:
        await DaskClient.create(
            app,
            settings=settings,
        )

    async def on_shutdown() -> None:
        if app.state.dask_client:
            await app.state.dask_client.delete()
            del app.state.dask_client  # type: ignore

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


@dataclass
class DaskClient:
    app: FastAPI
    client: dask.distributed.Client
    settings: DaskSchedulerSettings

    _taskid_to_future_map: Dict[str, dask.distributed.Future] = field(
        default_factory=dict
    )
    _subscribed_tasks: List[asyncio.Task] = field(default_factory=list)
    _cancellation_dask_pub: distributed.Pub = field(init=False)

    @classmethod
    async def create(
        cls, app: FastAPI, settings: DaskSchedulerSettings
    ) -> "DaskClient":
        app.state.dask_client = cls(
            app=app,
            client=await dask.distributed.Client(
                f"tcp://{settings.DASK_SCHEDULER_HOST}:{settings.DASK_SCHEDULER_PORT}",
                asynchronous=True,
                name=f"director-v2-client_{socket.gethostname()}_{os.getpid()}",
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

    def __post_init__(self) -> None:
        self._cancellation_dask_pub = distributed.Pub(TaskCancelEvent.topic_name())

    async def delete(self) -> None:
        for task in self._subscribed_tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        await self.app.state.dask_client.client.close()

    @retry(
        **dask_retry_policy,
        retry=retry_if_exception_type((OSError, ComputationalBackendNotConnectedError)),
    )
    async def reconnect_client(self):
        if self.client:
            await self.client.close()  # type: ignore
        self.client = await distributed.Client(
            f"tcp://{self.settings.DASK_SCHEDULER_HOST}:{self.settings.DASK_SCHEDULER_PORT}",
            asynchronous=True,
            name="director-v2-client",
        )  # type: ignore

        _check_valid_connection_to_scheduler(self.client)
        logger.info("Connection to Dask-scheduler completed, reconnection successful!")

    def register_handlers(
        self,
        task_change_handler: Callable[[str], Awaitable[None]],
        task_progress_handler: Callable[[str], Awaitable[None]],
        task_log_handler: Callable[[str], Awaitable[None]],
    ) -> None:
        async def _dask_sub_handler(
            dask_sub_topic_name: str, handler: Callable[[str], Awaitable[None]]
        ):
            while True:
                try:
                    dask_sub = distributed.Sub(dask_sub_topic_name)
                    async for event in dask_sub:
                        logger.debug("received event %s", event)
                        await handler(event)
                except asyncio.CancelledError:
                    logger.debug(
                        "cancelled dask sub handler for %s", dask_sub_topic_name
                    )
                    raise
                except Exception:  # pylint: disable=broad-except
                    logger.exception(
                        "unknown exception in dask sub handler for %s",
                        dask_sub_topic_name,
                        exc_info=True,
                    )

        for dask_sub, handler in [
            (
                TaskStateEvent.topic_name(),
                task_change_handler,
            ),
            (
                TaskProgressEvent.topic_name(),
                task_progress_handler,
            ),
            (
                TaskLogEvent.topic_name(),
                task_log_handler,
            ),
        ]:
            self._subscribed_tasks.append(
                asyncio.create_task(
                    _dask_sub_handler(dask_sub, handler),
                    name=f"{dask_sub}_subscriber_to_handler",
                )
            )

    async def send_computation_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        tasks: Dict[NodeID, Image],
        callback: UserCompleteCB,
        remote_fct: Callable = None,
    ) -> List[Tuple[NodeID, str]]:
        """actually sends the function remote_fct to be remotely executed. if None is kept then the default
        function that runs container will be started."""

        def _comp_sidecar_fct(
            docker_auth: DockerBasicAuth,
            service_key: str,
            service_version: str,
            input_data: TaskInputData,
            output_data_keys: TaskOutputDataSchema,
            log_file_url: AnyUrl,
            command: List[str],
        ) -> TaskOutputData:
            """This function is serialized by the Dask client and sent over to the Dask sidecar(s)
            Therefore, (screaming here) DO NOT MOVE THAT IMPORT ANYWHERE ELSE EVER!!"""
            from simcore_service_dask_sidecar.tasks import (  # type: ignore
                run_computational_sidecar,
            )

            return run_computational_sidecar(
                docker_auth,
                service_key,
                service_version,
                input_data,
                output_data_keys,
                log_file_url,
                command,
            )

        if remote_fct is None:
            remote_fct = _comp_sidecar_fct
        list_of_node_id_to_job_id: List[Tuple[NodeID, str]] = []
        for node_id, node_image in tasks.items():
            job_id = generate_dask_job_id(
                service_key=node_image.name,
                service_version=node_image.tag,
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
            )
            dask_resources = _from_node_reqs_to_dask_resources(
                node_image.node_requirements
            )
            # add the cluster ID here
            dask_resources.update(
                {
                    f"{self.settings.DASK_CLUSTER_ID_PREFIX}{cluster_id}": CLUSTER_RESOURCE_MOCK_USAGE
                }
            )

            _check_valid_connection_to_scheduler(self.client)
            _check_cluster_able_to_run_pipeline(
                node_id=node_id,
                scheduler_info=self.client.scheduler_info(),
                task_resources=dask_resources,
                node_image=node_image,
                cluster_id_prefix=self.settings.DASK_CLUSTER_ID_PREFIX,  # type: ignore
                cluster_id=cluster_id,
            )

            input_data = await compute_input_data(
                self.app, user_id, project_id, node_id
            )
            output_data_keys = await compute_output_data_schema(
                self.app, user_id, project_id, node_id
            )
            log_file_url = await compute_service_log_file_upload_link(
                user_id, project_id, node_id
            )
            try:
                task_future = self.client.submit(
                    remote_fct,
                    docker_auth=DockerBasicAuth(
                        server_address=self.app.state.settings.DIRECTOR_V2_DOCKER_REGISTRY.resolved_registry_url,
                        username=self.app.state.settings.DIRECTOR_V2_DOCKER_REGISTRY.REGISTRY_USER,
                        password=self.app.state.settings.DIRECTOR_V2_DOCKER_REGISTRY.REGISTRY_PW,
                    ),
                    service_key=node_image.name,
                    service_version=node_image.tag,
                    input_data=input_data,
                    output_data_keys=output_data_keys,
                    log_file_url=log_file_url,
                    command=["run"],
                    key=job_id,
                    resources=dask_resources,
                    retries=0,
                )
                task_future.add_done_callback(
                    functools.partial(
                        done_dask_callback,
                        task_to_future_map=self._taskid_to_future_map,
                        user_callback=callback,
                        main_loop=asyncio.get_event_loop(),
                    )
                )

                self._taskid_to_future_map[job_id] = task_future
                list_of_node_id_to_job_id.append((node_id, job_id))
                dask.distributed.fire_and_forget(
                    task_future
                )  # this should ensure the task will run even if the future goes out of scope
                logger.debug("Dask task %s started", task_future.key)
            except Exception:
                # Dask raises a base Exception here in case of connection error, this will raise a more precise one
                _check_valid_connection_to_scheduler(self.client)
                # if the connection is good, then the problem is different, so we re-raise
                raise
        return list_of_node_id_to_job_id

    async def abort_computation_tasks(self, job_ids: List[str]) -> None:
        logger.debug("cancelling tasks with job_ids: [%s]", job_ids)
        for job_id in job_ids:
            task_future = self._taskid_to_future_map.get(job_id)
            if task_future:
                self._cancellation_dask_pub.put(  # type: ignore
                    TaskCancelEvent(job_id=job_id).json()
                )
                await task_future.cancel()
                logger.debug("Dask task %s cancelled", task_future.key)


def _check_valid_connection_to_scheduler(client: dask.distributed.Client):
    client_status = client.status
    if client_status not in "running":
        logger.error(
            "The computational backend is not connected!",
        )
        raise ComputationalBackendNotConnectedError()


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
        def gen_check(
            task_resources: Dict[str, Any], worker_resources: Dict[str, Any]
        ) -> Iterable[bool]:
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

import asyncio
import collections
import concurrent.futures
import functools
import logging
from dataclasses import dataclass, field
from pprint import pformat
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)

import dask.distributed
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.events import TaskStateEvent
from dask_task_models_library.container_tasks.io import (
    FileUrl,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic import AnyUrl
from simcore_sdk import node_ports_v2
from simcore_sdk.node_ports_v2 import DBManager, port_utils
from simcore_sdk.node_ports_v2.links import ItemValue
from simcore_sdk.node_ports_v2.nodeports_v2 import Nodeports
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
from ..utils.dask import generate_dask_job_id, parse_dask_job_id

logger = logging.getLogger(__name__)


dask_retry_policy = dict(
    wait=wait_random(5, 10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

CLUSTER_RESOURCE_MOCK_USAGE: float = 1e-9


async def _create_node_ports(
    app: FastAPI, user_id: UserID, project_id: ProjectID, node_id: NodeID
) -> Nodeports:
    db_manager = DBManager(db_engine=app.state.engine)
    return await node_ports_v2.ports(
        user_id=user_id,
        project_id=f"{project_id}",
        node_uuid=f"{node_id}",
        db_manager=db_manager,
    )


async def _parse_output_data(app: FastAPI, job_id: str, data: TaskOutputData) -> None:
    (
        service_key,
        service_version,
        user_id,
        project_id,
        node_id,
    ) = parse_dask_job_id(job_id)
    logger.debug(
        "parsing output %s of dask task for %s:%s of user %s on project '%s' and node '%s'",
        pformat(data),
        service_key,
        service_version,
        user_id,
        project_id,
        node_id,
    )

    ports = await _create_node_ports(
        app=app, user_id=user_id, project_id=project_id, node_id=node_id
    )
    for port_key, port_value in data.items():
        value_to_transfer: Optional[ItemValue] = None
        if isinstance(port_value, FileUrl):
            value_to_transfer = port_value.url
        else:
            value_to_transfer = port_value
        await (await ports.outputs)[port_key].set_value(value_to_transfer)


async def _compute_input_data(
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> TaskInputData:
    ports = await _create_node_ports(
        app=app, user_id=user_id, project_id=project_id, node_id=node_id
    )
    input_data = {}
    for port in (await ports.inputs).values():
        value_link = await port.get_value()
        if isinstance(value_link, AnyUrl):
            input_data[port.key] = FileUrl(
                url=value_link,
                file_mapping=(
                    next(iter(port.file_to_key_map)) if port.file_to_key_map else None
                ),
            )
        else:
            input_data[port.key] = value_link
    return TaskInputData.parse_obj(input_data)


async def _compute_output_data_schema(
    app: FastAPI,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
) -> TaskOutputDataSchema:
    ports = await _create_node_ports(
        app=app, user_id=user_id, project_id=project_id, node_id=node_id
    )
    output_data_schema = {}
    for port in (await ports.outputs).values():
        output_data_schema[port.key] = {"required": port.default_value is None}

        if port.property_type.startswith("data:"):
            value_link = await port_utils.get_upload_link_from_storage(
                user_id=user_id,
                project_id=f"{project_id}",
                node_id=f"{node_id}",
                file_name=next(iter(port.file_to_key_map))
                if port.file_to_key_map
                else port.key,
            )
            output_data_schema[port.key].update(
                {
                    "mapping": next(iter(port.file_to_key_map))
                    if port.file_to_key_map
                    else None,
                    "url": value_link,
                }
            )

    return TaskOutputDataSchema.parse_obj(output_data_schema)


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
    client: dask.distributed.Client
    settings: DaskSchedulerSettings

    _taskid_to_future_map: Dict[str, dask.distributed.Future] = field(
        default_factory=dict
    )

    @classmethod
    async def create(
        cls, app: FastAPI, settings: DaskSchedulerSettings
    ) -> "DaskClient":
        app.state.dask_client = cls(
            app=app,
            client=await dask.distributed.Client(
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

    @retry(
        **dask_retry_policy,
        retry=retry_if_exception_type((OSError, ComputationalBackendNotConnectedError)),
    )
    async def reconnect_client(self):
        if self.client:
            await self.client.close()  # type: ignore
        self.client = await dask.distributed.Client(
            f"tcp://{self.settings.DASK_SCHEDULER_HOST}:{self.settings.DASK_SCHEDULER_PORT}",
            asynchronous=True,
            name="director-v2-client",
        )  # type: ignore

        _check_valid_connection_to_scheduler(self.client)
        logger.info("Connection to Dask-scheduler completed, reconnection successful!")

    async def send_computation_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        tasks: Dict[NodeID, Image],
        callback: Callable[[], None],
        task_change_handler: Callable[[Tuple[str, str]], Awaitable],
        remote_fct: Callable = None,
    ):
        """actually sends the function remote_fct to be remotely executed. if None is kept then the default
        function that runs container will be started."""

        def _done_dask_callback(
            dask_future: dask.distributed.Future, loop: asyncio.AbstractEventLoop
        ):
            # NOTE: here we are called in a separate task
            job_id = dask_future.key
            try:
                if dask_future.status == "error":
                    self.client.log_event(
                        TaskStateEvent.topic_name(),
                        TaskStateEvent(job_id=job_id, state=RunningState.FAILED).json(),
                    )
                elif dask_future.cancelled():
                    self.client.log_event(
                        TaskStateEvent.topic_name(),
                        TaskStateEvent(
                            job_id=job_id, state=RunningState.ABORTED
                        ).json(),
                    )
                else:
                    # this gets the data out of the dask backend
                    task_output_data = dask_future.result(timeout=5)
                    try:
                        # this callback is called in a secondary thread so we need to get back to the main
                        # thread for database accesses or else we ge into loop issues
                        future = asyncio.run_coroutine_threadsafe(
                            _parse_output_data(self.app, job_id, task_output_data), loop
                        )
                        future.result(timeout=5)
                        self.client.log_event(
                            TaskStateEvent.topic_name(),
                            TaskStateEvent(
                                job_id=job_id, state=RunningState.SUCCESS
                            ).json(),
                        )

                    except concurrent.futures.TimeoutError:
                        logger.error(
                            "parsing output data of job %s timed-out, please check.",
                            job_id,
                            exc_info=True,
                        )
                        self.client.log_event(
                            TaskStateEvent.topic_name(),
                            TaskStateEvent(
                                job_id=job_id, state=RunningState.FAILED
                            ).json(),
                        )
                    except concurrent.futures.CancelledError:
                        logger.warning(
                            "parsing output data of job %s was cancelled, please check.",
                            job_id,
                            exc_info=True,
                        )
                        self.client.log_event(
                            TaskStateEvent.topic_name(),
                            TaskStateEvent(
                                job_id=job_id, state=RunningState.FAILED
                            ).json(),
                        )

            except dask.distributed.TimeoutError:
                logger.error(
                    "fetching result of '%s' timed-out, please check",
                    job_id,
                    exc_info=True,
                )
            finally:
                # remove the future from the dict to remove any handle to the future, so the worker can free the memory
                self._taskid_to_future_map.pop(job_id)
                callback()

        def _comp_sidecar_fct(
            docker_auth: DockerBasicAuth,
            service_key: str,
            service_version: str,
            input_data: TaskInputData,
            output_data_keys: TaskOutputDataSchema,
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
                command,
            )

        if remote_fct is None:
            remote_fct = _comp_sidecar_fct

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

            input_data = await _compute_input_data(
                self.app, user_id, project_id, node_id
            )
            output_data_keys = await _compute_output_data_schema(
                self.app, user_id, project_id, node_id
            )
            try:
                self.client.subscribe_topic(
                    TaskStateEvent.topic_name(), task_change_handler
                )

                task_future = self.client.submit(
                    remote_fct,
                    docker_auth=DockerBasicAuth(
                        server_address=self.app.state.settings.DOCKER_REGISTRY_SETTINGS.REGISTRY_URL,
                        username=self.app.state.settings.DOCKER_REGISTRY_SETTINGS.REGISTRY_USER,
                        password=self.app.state.settings.DOCKER_REGISTRY_SETTINGS.REGISTRY_PW,
                    ),
                    service_key=node_image.name,
                    service_version=node_image.tag,
                    input_data=input_data,
                    output_data_keys=output_data_keys,
                    command=["run"],
                    key=job_id,
                    resources=dask_resources,
                    retries=0,
                )
            except Exception:
                # Dask raises a base Exception here in case of connection error, this will raise a more precise one
                _check_valid_connection_to_scheduler(self.client)
                # if the connection is good, then the problem is different, so we re-raise
                raise

            task_future.add_done_callback(
                functools.partial(_done_dask_callback, loop=asyncio.get_event_loop())
            )
            self._taskid_to_future_map[job_id] = task_future
            dask.distributed.fire_and_forget(
                task_future
            )  # this should ensure the task will run even if the future goes out of scope
            logger.debug("Dask task %s started", task_future.key)

    async def abort_computation_tasks(self, task_ids: List[str]) -> None:

        for task_id in task_ids:
            task_future = self._taskid_to_future_map.get(task_id)
            if task_future:
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

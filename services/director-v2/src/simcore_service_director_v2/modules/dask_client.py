import asyncio
import json
import logging
import os
import socket
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional, Tuple, Union

import dask_gateway
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
from models_library.clusters import (
    ClusterAuthentication,
    JupyterHubTokenAuthentication,
    KerberosAuthentication,
    NoAuthentication,
    SimpleAuthentication,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic.networks import AnyUrl
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from ..core.errors import (
    ConfigurationError,
    DaskClientRequestError,
    DaskClusterError,
    DaskGatewayServerError,
)
from ..core.settings import DaskSchedulerSettings
from ..models.domains.comp_tasks import Image
from ..models.schemas.constants import ClusterID, UserID
from ..utils.dask import (
    check_communication_with_scheduler_is_open,
    check_if_cluster_is_able_to_run_pipeline,
    check_scheduler_is_still_the_same,
    check_scheduler_status,
    compute_input_data,
    compute_output_data_schema,
    compute_service_log_file_upload_link,
    dask_sub_consumer_task,
    from_node_reqs_to_dask_resources,
    generate_dask_job_id,
    parse_dask_future_results,
)

logger = logging.getLogger(__name__)


_DASK_TASK_STATUS_RUNNING_STATE_MAP = {
    "new": RunningState.PENDING,
    "released": RunningState.PENDING,
    "waiting": RunningState.PENDING,
    "no-worker": RunningState.PENDING,
    "processing": RunningState.STARTED,
    "memory": RunningState.SUCCESS,
    "erred": RunningState.FAILED,
}


@dataclass
class DaskSubSystem:
    client: distributed.Client
    scheduler_id: str
    gateway: Optional[dask_gateway.Gateway]
    gateway_cluster: Optional[dask_gateway.GatewayCluster]

    async def close(self):
        if self.client:
            await self.client.close()  # type: ignore
        if self.gateway_cluster:
            await self.gateway_cluster.close()  # type: ignore
        if self.gateway:
            await self.gateway.close()  # type: ignore


async def _connect_to_dask_scheduler(endpoint: AnyUrl) -> DaskSubSystem:
    try:
        client = await distributed.Client(
            f"{endpoint}",
            asynchronous=True,
            name=f"director-v2_{socket.gethostname()}_{os.getpid()}",
        )
        return DaskSubSystem(
            client=client,
            scheduler_id=client.scheduler_info()["id"],
            gateway=None,
            gateway_cluster=None,
        )
    except (TypeError) as exc:
        raise ConfigurationError(
            f"Scheduler has invalid configuration: {endpoint=}"
        ) from exc


DaskGatewayAuths = Union[
    dask_gateway.BasicAuth, dask_gateway.KerberosAuth, dask_gateway.JupyterHubAuth
]


async def _get_gateway_auth_from_params(
    auth_params: ClusterAuthentication,
) -> DaskGatewayAuths:
    try:
        if isinstance(auth_params, SimpleAuthentication):
            return dask_gateway.BasicAuth(**auth_params.dict(exclude={"type"}))
        if isinstance(auth_params, KerberosAuthentication):
            return dask_gateway.KerberosAuth()
        if isinstance(auth_params, JupyterHubTokenAuthentication):
            return dask_gateway.JupyterHubAuth(auth_params.api_token)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(
            f"Cluster has invalid configuration: {auth_params}"
        ) from exc
    raise ConfigurationError(f"Cluster has invalid configuration: {auth_params=}")


async def _connect_with_gateway_and_create_cluster(
    endpoint: AnyUrl, auth_params: ClusterAuthentication
) -> DaskSubSystem:
    try:
        gateway_auth = await _get_gateway_auth_from_params(auth_params)
        gateway = dask_gateway.Gateway(
            address=f"{endpoint}", auth=gateway_auth, asynchronous=True
        )
        # if there is already a cluster that means we can re-connect to it,
        # and IT SHALL BE the first in the list
        cluster_reports_list = await gateway.list_clusters()
        cluster = None
        if cluster_reports_list:
            assert (
                len(cluster_reports_list) == 1
            ), "More than 1 cluster at this location, that is unexpected!!"  # nosec
            cluster = await gateway.connect(
                cluster_reports_list[0].name, shutdown_on_close=False
            )
        else:
            cluster = await gateway.new_cluster(shutdown_on_close=False)
        assert cluster  # nosec
        logger.info("Cluster dashboard available: %s", cluster.dashboard_link)
        # NOTE: we scale to 1 worker as they are global
        await cluster.adapt(active=True)
        client = await cluster.get_client()
        assert client  # nosec
        return DaskSubSystem(
            client=client,
            scheduler_id=client.scheduler_info()["id"],
            gateway=gateway,
            gateway_cluster=cluster,
        )
    except (TypeError) as exc:
        raise ConfigurationError(
            f"Cluster has invalid configuration: {endpoint=}, {auth_params=}"
        ) from exc
    except (ValueError) as exc:
        # this is when a 404=NotFound,422=MalformedData comes up
        raise DaskClientRequestError(endpoint=endpoint, error=exc) from exc
    except (dask_gateway.GatewayClusterError) as exc:
        # this is when a 409=Conflict/Cannot complete request comes up
        raise DaskClusterError(endpoint=endpoint, error=exc) from exc
    except (dask_gateway.GatewayServerError) as exc:
        # this is when a 500 comes up
        raise DaskGatewayServerError(endpoint=endpoint, error=exc) from exc


async def _create_internal_client_based_on_auth(
    endpoint: AnyUrl, authentication: ClusterAuthentication
) -> DaskSubSystem:
    if isinstance(authentication, NoAuthentication):
        # if no auth then we go for a standard scheduler connection
        return await _connect_to_dask_scheduler(endpoint)
    # we do have some auth, so it is going through a gateway
    return await _connect_with_gateway_and_create_cluster(endpoint, authentication)


@dataclass
class TaskHandlers:
    task_change_handler: Callable[[str], Awaitable[None]]
    task_progress_handler: Callable[[str], Awaitable[None]]
    task_log_handler: Callable[[str], Awaitable[None]]


@dataclass
class DaskClient:
    app: FastAPI
    dask_subsystem: DaskSubSystem
    settings: DaskSchedulerSettings
    cancellation_dask_pub: distributed.Pub

    _subscribed_tasks: List[asyncio.Task] = field(default_factory=list)

    @classmethod
    async def create(
        cls,
        app: FastAPI,
        settings: DaskSchedulerSettings,
        endpoint: AnyUrl,
        authentication: ClusterAuthentication,
    ) -> "DaskClient":
        logger.info(
            "Initiating connection to %s with auth: %s",
            f"dask-scheduler/gateway at {endpoint}",
            authentication,
        )
        async for attempt in AsyncRetrying(
            reraise=True,
            before_sleep=before_sleep_log(logger, logging.WARNING),
            wait=wait_fixed(0.3),
            stop=stop_after_attempt(3),
        ):
            with attempt:
                logger.debug(
                    "Connecting to %s, attempt %s...",
                    endpoint,
                    attempt.retry_state.attempt_number,
                )
                dask_subsystem = await _create_internal_client_based_on_auth(
                    endpoint, authentication
                )
                check_scheduler_status(dask_subsystem.client)
                instance = cls(
                    app=app,
                    dask_subsystem=dask_subsystem,
                    settings=settings,
                    cancellation_dask_pub=distributed.Pub(
                        TaskCancelEvent.topic_name(), client=dask_subsystem.client
                    ),
                )
                logger.info(
                    "Connection to %s succeeded [%s]",
                    f"dask-scheduler/gateway at {endpoint}",
                    json.dumps(attempt.retry_state.retry_object.statistics),
                )
                logger.info(
                    "Scheduler info:\n%s",
                    json.dumps(dask_subsystem.client.scheduler_info(), indent=2),
                )
                return instance
        # this is to satisfy pylance
        raise ValueError("Could not create client")

    async def delete(self) -> None:
        logger.debug("closing dask client...")
        for task in self._subscribed_tasks:
            task.cancel()
        await asyncio.gather(*self._subscribed_tasks, return_exceptions=True)
        await self.dask_subsystem.close()
        logger.info("dask client properly closed")

    def register_handlers(self, task_handlers: TaskHandlers) -> None:
        _EVENT_CONSUMER_MAP = [
            (TaskStateEvent, task_handlers.task_change_handler),
            (TaskProgressEvent, task_handlers.task_progress_handler),
            (TaskLogEvent, task_handlers.task_log_handler),
        ]
        self._subscribed_tasks = [
            asyncio.create_task(
                dask_sub_consumer_task(event, handler, self.dask_subsystem.client),
                name=f"{event.topic_name()}_dask_sub_consumer_task",
            )
            for event, handler in _EVENT_CONSUMER_MAP
        ]

    async def send_computation_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        tasks: Dict[NodeID, Image],
        callback: Callable,
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
            dask_resources = from_node_reqs_to_dask_resources(
                node_image.node_requirements
            )
            check_scheduler_is_still_the_same(
                self.dask_subsystem.scheduler_id, self.dask_subsystem.client
            )
            check_communication_with_scheduler_is_open(self.dask_subsystem.client)
            check_scheduler_status(self.dask_subsystem.client)
            # NOTE: in case it's a gateway we do not check a priori if the task
            # is runnable because we CAN'T. A cluster might auto-scale, the worker(s)
            # might also auto-scale and the gateway does not know that a priori.
            # So, we'll just send the tasks over and see what happens after a while.
            # TODO: one idea is to do a lazy checking. A cluster might take a few seconds to run a
            # sidecar, which will then populate the scheduler with resources available on the cluster
            if not self.dask_subsystem.gateway:
                check_if_cluster_is_able_to_run_pipeline(
                    node_id=node_id,
                    scheduler_info=self.dask_subsystem.client.scheduler_info(),
                    task_resources=dask_resources,
                    node_image=node_image,
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
                task_future = self.dask_subsystem.client.submit(
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

                def done_callback(_: distributed.Future):
                    callback()

                task_future.add_done_callback(done_callback)

                list_of_node_id_to_job_id.append((node_id, job_id))
                await self.dask_subsystem.client.publish_dataset(
                    task_future, name=job_id
                )  # type: ignore

                logger.debug("Dask task %s started", task_future.key)
            except Exception:
                # Dask raises a base Exception here in case of connection error, this will raise a more precise one
                check_scheduler_status(self.dask_subsystem.client)
                # if the connection is good, then the problem is different, so we re-raise
                raise
        return list_of_node_id_to_job_id

    async def get_tasks_status(self, job_ids: List[str]) -> List[RunningState]:
        task_statuses = []
        # try to get the task from the scheduler
        task_statuses = await self.dask_subsystem.client.run_on_scheduler(
            lambda dask_scheduler: dask_scheduler.get_task_status(keys=job_ids)
        )  # type: ignore
        logger.debug("found dask task statuses: %s", f"{task_statuses=}")

        running_states = []
        for job_id in job_ids:
            dask_status = task_statuses.get(job_id, "lost")
            if dask_status == "memory":
                if dask_future := distributed.Future(job_id):
                    # NOTE: this is necessary so we get the results of the future (cancelled or done)
                    await dask_future.result(timeout=2)
                    if dask_future.cancelled():
                        running_states.append(RunningState.ABORTED)
                    elif dask_future.done():
                        running_states.append(RunningState.SUCCESS)
                    logger.debug(
                        "task status is in memory, future status is %s",
                        f"{dask_future=}",
                    )
            else:
                running_states.append(
                    _DASK_TASK_STATUS_RUNNING_STATE_MAP.get(
                        dask_status, RunningState.UNKNOWN
                    )
                )

        return running_states

    async def abort_computation_tasks(self, job_ids: List[str]) -> None:
        # Dask future may be cancelled, but only a future that was not already taken by
        # a sidecar can be cancelled that way.
        # If the sidecar has already taken the job, then the cancellation must be user-defined.
        # therefore the dask PUB is used, and the dask-sidecar will then let the abort
        # process, and report when it is finished and properly cancelled.
        logger.debug("cancelling tasks with job_ids: [%s]", job_ids)
        for job_id in job_ids:
            if task_future := distributed.Future(job_id, self.dask_subsystem.client):
                await task_future.cancel(force=True)  # type: ignore
                self.cancellation_dask_pub.put(  # type: ignore
                    TaskCancelEvent(job_id=job_id).json()  # type: ignore
                )

                logger.debug("Dask task %s cancelled", task_future.key)

    async def get_tasks_results(self, job_ids: List[str]) -> List[TaskStateEvent]:
        logger.debug("getting results for %s", f"{job_ids=}")
        results = []
        for job_id in job_ids:
            if task_future := distributed.Future(job_id, self.dask_subsystem.client):
                state = await parse_dask_future_results(task_future)
                results.append(state)
        return results

    async def release_tasks_results(self, job_ids: List[str]) -> None:
        logger.debug("releasing results for %s", f"{job_ids=}")
        for job_id in job_ids:
            await self.dask_subsystem.client.unpublish_dataset(name=job_id)  # type: ignore

"""The dask client is the osparc part that communicates with a
dask-scheduler/worker backend directly or through a dask-gateway.

From dask documentation any Data or function must follow the criteria to be
usable in dask [http://distributed.dask.org/en/stable/limitations.html?highlight=cloudpickle#assumptions-on-functions-and-data]:
from cloudpickle import dumps, loads
loads(dumps(my_object))

"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import distributed
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.io import (
    TaskCancelEventName,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from fastapi import FastAPI
from models_library.clusters import ClusterAuthentication
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from pydantic.networks import AnyUrl
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from ..core.errors import (
    ComputationalBackendTaskNotFoundError,
    ComputationalBackendTaskResultsNotReadyError,
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
)
from ..utils.dask_client_utils import (
    DaskSubSystem,
    TaskHandlers,
    create_internal_client_based_on_auth,
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

DASK_DEFAULT_TIMEOUT_S = 1


ServiceKey = str
ServiceVersion = str
LogFileUploadURL = AnyUrl
Commands = List[str]
RemoteFct = Callable[
    [
        DockerBasicAuth,
        ServiceKey,
        ServiceVersion,
        TaskInputData,
        TaskOutputDataSchema,
        LogFileUploadURL,
        Commands,
    ],
    TaskOutputData,
]
UserCallbackInSepThread = Callable[[], None]


@dataclass
class DaskClient:
    app: FastAPI
    dask_subsystem: DaskSubSystem
    settings: DaskSchedulerSettings

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
                dask_subsystem = await create_internal_client_based_on_auth(
                    endpoint, authentication
                )
                check_scheduler_status(dask_subsystem.client)
                instance = cls(
                    app=app,
                    dask_subsystem=dask_subsystem,
                    settings=settings,
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
            (self.dask_subsystem.state_sub, task_handlers.task_change_handler),
            (self.dask_subsystem.progress_sub, task_handlers.task_progress_handler),
            (self.dask_subsystem.logs_sub, task_handlers.task_log_handler),
        ]
        self._subscribed_tasks = [
            asyncio.create_task(
                dask_sub_consumer_task(dask_sub, handler),
                name=f"{dask_sub.name}_dask_sub_consumer_task",
            )
            for dask_sub, handler in _EVENT_CONSUMER_MAP
        ]

    async def send_computation_tasks(
        self,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        tasks: Dict[NodeID, Image],
        callback: UserCallbackInSepThread,
        remote_fct: Optional[RemoteFct] = None,
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

                task_future.add_done_callback(lambda: callback())

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

    async def get_task_status(self, job_id: str) -> RunningState:
        return (await self.get_tasks_status(job_ids=[job_id]))[0]

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
            if dask_status == "erred":
                # find out if this was a cancellation
                exception = await distributed.Future(job_id).exception(timeout=DASK_DEFAULT_TIMEOUT_S)  # type: ignore
                if isinstance(exception, TaskCancelledError):
                    running_states.append(RunningState.ABORTED)
                else:
                    running_states.append(RunningState.FAILED)
            else:
                running_states.append(
                    _DASK_TASK_STATUS_RUNNING_STATE_MAP.get(
                        dask_status, RunningState.UNKNOWN
                    )
                )

        return running_states

    async def abort_computation_task(self, job_id: str) -> None:
        # Dask future may be cancelled, but only a future that was not already taken by
        # a sidecar can be cancelled that way.
        # If the sidecar has already taken the job, then the cancellation must be user-defined.
        # therefore the dask PUB is used, and the dask-sidecar will then let the abort
        # process, and report when it is finished and properly cancelled.
        logger.debug("cancelling task with %s", f"{job_id=}")
        try:
            task_future = await self.dask_subsystem.client.get_dataset(name=job_id)  # type: ignore
            # NOTE: It seems there is a bug in the pubsub system in dask
            # Event are more robust to connections/disconnections
            cancel_event = await distributed.Event(
                name=TaskCancelEventName.format(job_id)
            )
            await cancel_event.set()  # type: ignore
            await task_future.cancel()  # type: ignore
            logger.debug("Dask task %s cancelled", task_future.key)
        except KeyError:
            logger.warning("Unknown task cannot be aborted: %s", f"{job_id=}")

    async def get_task_result(self, job_id: str) -> TaskOutputData:
        logger.debug("getting result of %s", f"{job_id=}")
        try:
            task_future = await self.dask_subsystem.client.get_dataset(name=job_id)  # type: ignore
            return await task_future.result(timeout=DASK_DEFAULT_TIMEOUT_S)  # type: ignore
        except KeyError as exc:
            raise ComputationalBackendTaskNotFoundError(job_id=job_id) from exc
        except distributed.TimeoutError as exc:
            raise ComputationalBackendTaskResultsNotReadyError from exc

    async def release_task_result(self, job_id: str) -> None:
        logger.debug("releasing results for %s", f"{job_id=}")
        try:
            # first check if the key exists
            await self.dask_subsystem.client.get_dataset(name=job_id)  # type: ignore
            await self.dask_subsystem.client.unpublish_dataset(name=job_id)  # type: ignore
        except KeyError:
            logger.warning("Unknown task cannot be unpublished: %s", f"{job_id=}")

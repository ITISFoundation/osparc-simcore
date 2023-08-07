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
import traceback
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from http.client import HTTPException
from typing import Any

import distributed
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.io import (
    TaskCancelEventName,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerCommands,
    ContainerEnvsDict,
    ContainerImage,
    ContainerLabelsDict,
    ContainerRemoteFct,
    ContainerTag,
    LogFileUploadURL,
)
from fastapi import FastAPI
from models_library.api_schemas_directorv2.clusters import ClusterDetails, Scheduler
from models_library.clusters import ClusterAuthentication, ClusterID
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.services_resources import BootMode
from models_library.users import UserID
from pydantic import parse_obj_as
from pydantic.networks import AnyUrl
from servicelib.logging_utils import log_catch
from settings_library.s3 import S3Settings
from simcore_sdk.node_ports_v2 import FileLinkType
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from ..core.errors import (
    ComputationalBackendNoS3AccessError,
    ComputationalBackendTaskNotFoundError,
    ComputationalBackendTaskResultsNotReadyError,
)
from ..core.settings import AppSettings, ComputationalBackendSettings
from ..models.comp_runs import MetadataDict
from ..models.comp_tasks import Image
from ..modules.storage import StorageClient
from ..utils.dask import (
    check_communication_with_scheduler_is_open,
    check_if_cluster_is_able_to_run_pipeline,
    check_maximize_workers,
    check_scheduler_is_still_the_same,
    check_scheduler_status,
    compute_input_data,
    compute_output_data_schema,
    compute_service_log_file_upload_link,
    compute_task_envs,
    compute_task_labels,
    create_node_ports,
    dask_sub_consumer_task,
    from_node_reqs_to_dask_resources,
    generate_dask_job_id,
    wrap_client_async_routine,
)
from ..utils.dask_client_utils import (
    DaskSubSystem,
    TaskHandlers,
    create_internal_client_based_on_auth,
)

_logger = logging.getLogger(__name__)


_DASK_TASK_STATUS_RUNNING_STATE_MAP = {
    "new": RunningState.PENDING,
    "released": RunningState.PENDING,
    "waiting": RunningState.PENDING,
    "no-worker": RunningState.WAITING_FOR_RESOURCES,
    "processing": RunningState.STARTED,
    "memory": RunningState.SUCCESS,
    "erred": RunningState.FAILED,
}

_DASK_DEFAULT_TIMEOUT_S = 1


_UserCallbackInSepThread = Callable[[], None]


@dataclass
class DaskClient:
    app: FastAPI
    backend: DaskSubSystem
    settings: ComputationalBackendSettings
    tasks_file_link_type: FileLinkType

    _subscribed_tasks: list[asyncio.Task] = field(default_factory=list)

    @classmethod
    async def create(
        cls,
        app: FastAPI,
        settings: ComputationalBackendSettings,
        endpoint: AnyUrl,
        authentication: ClusterAuthentication,
        tasks_file_link_type: FileLinkType,
    ) -> "DaskClient":
        _logger.info(
            "Initiating connection to %s with auth: %s",
            f"dask-scheduler/gateway at {endpoint}",
            authentication,
        )
        async for attempt in AsyncRetrying(
            reraise=True,
            before_sleep=before_sleep_log(_logger, logging.INFO),
            wait=wait_fixed(0.3),
            stop=stop_after_attempt(3),
        ):
            with attempt:
                _logger.debug(
                    "Connecting to %s, attempt %s...",
                    endpoint,
                    attempt.retry_state.attempt_number,
                )
                backend = await create_internal_client_based_on_auth(
                    endpoint, authentication
                )
                check_scheduler_status(backend.client)
                instance = cls(
                    app=app,
                    backend=backend,
                    settings=settings,
                    tasks_file_link_type=tasks_file_link_type,
                )
                _logger.info(
                    "Connection to %s succeeded [%s]",
                    f"dask-scheduler/gateway at {endpoint}",
                    json.dumps(attempt.retry_state.retry_object.statistics),
                )
                _logger.info(
                    "Scheduler info:\n%s",
                    json.dumps(backend.client.scheduler_info(), indent=2),
                )
                return instance
        # this is to satisfy pylance
        err_msg = "Could not create client"
        raise ValueError(err_msg)

    async def delete(self) -> None:
        _logger.debug("closing dask client...")
        for task in self._subscribed_tasks:
            task.cancel()
        await asyncio.gather(*self._subscribed_tasks, return_exceptions=True)
        await self.backend.close()
        _logger.info("dask client properly closed")

    def register_handlers(self, task_handlers: TaskHandlers) -> None:
        _event_consumer_map = [
            (self.backend.progress_sub, task_handlers.task_progress_handler),
            (self.backend.logs_sub, task_handlers.task_log_handler),
        ]
        self._subscribed_tasks = [
            asyncio.create_task(
                dask_sub_consumer_task(dask_sub, handler),
                name=f"{dask_sub.name}_dask_sub_consumer_task",
            )
            for dask_sub, handler in _event_consumer_map
        ]

    async def send_computation_tasks(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        tasks: dict[NodeID, Image],
        callback: _UserCallbackInSepThread,
        remote_fct: ContainerRemoteFct | None = None,
        metadata: MetadataDict,
    ) -> list[tuple[NodeID, str]]:
        """actually sends the function remote_fct to be remotely executed. if None is kept then the default
        function that runs container will be started."""

        def _comp_sidecar_fct(  # noqa: PLR0913
            *,
            docker_auth: DockerBasicAuth,
            service_key: ContainerImage,
            service_version: ContainerTag,
            input_data: TaskInputData,
            output_data_keys: TaskOutputDataSchema,
            log_file_url: LogFileUploadURL,
            command: ContainerCommands,
            task_envs: ContainerEnvsDict,
            task_labels: ContainerLabelsDict,
            s3_settings: S3Settings | None,
            boot_mode: BootMode,
        ) -> TaskOutputData:
            """This function is serialized by the Dask client and sent over to the Dask sidecar(s)
            Therefore, (screaming here) DO NOT MOVE THAT IMPORT ANYWHERE ELSE EVER!!"""
            from simcore_service_dask_sidecar.tasks import run_computational_sidecar

            return run_computational_sidecar(
                docker_auth=docker_auth,
                service_key=service_key,
                service_version=service_version,
                input_data=input_data,
                output_data_keys=output_data_keys,
                log_file_url=log_file_url,
                command=command,
                task_envs=task_envs,
                task_labels=task_labels,
                s3_settings=s3_settings,
                boot_mode=boot_mode,
            )

        if remote_fct is None:
            remote_fct = _comp_sidecar_fct
        list_of_node_id_to_job_id: list[tuple[NodeID, str]] = []
        for node_id, node_image in tasks.items():
            job_id = generate_dask_job_id(
                service_key=node_image.name,
                service_version=node_image.tag,
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
            )
            assert node_image.node_requirements  # nosec
            dask_resources = from_node_reqs_to_dask_resources(
                node_image.node_requirements
            )

            check_scheduler_is_still_the_same(
                self.backend.scheduler_id, self.backend.client
            )
            check_communication_with_scheduler_is_open(self.backend.client)
            check_scheduler_status(self.backend.client)
            await check_maximize_workers(self.backend.gateway_cluster)
            # NOTE: in case it's a gateway we do not check a priori if the task
            # is runnable because we CAN'T. A cluster might auto-scale, the worker(s)
            # might also auto-scale and the gateway does not know that a priori.
            # So, we'll just send the tasks over and see what happens after a while.
            if not self.backend.gateway:
                check_if_cluster_is_able_to_run_pipeline(
                    project_id=project_id,
                    node_id=node_id,
                    scheduler_info=self.backend.client.scheduler_info(),
                    task_resources=dask_resources,
                    node_image=node_image,
                    cluster_id=cluster_id,
                )

            s3_settings = None
            if self.tasks_file_link_type == FileLinkType.S3:
                try:
                    s3_settings = await StorageClient.instance(self.app).get_s3_access(
                        user_id
                    )
                except HTTPException as err:
                    raise ComputationalBackendNoS3AccessError from err

            # This instance is created only once so it can be reused in calls below
            node_ports = await create_node_ports(
                db_engine=self.app.state.engine,
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
            )
            # NOTE: for download there is no need to go with S3 links
            input_data = await compute_input_data(
                project_id=project_id,
                node_id=node_id,
                node_ports=node_ports,
                file_link_type=FileLinkType.PRESIGNED,
            )
            output_data_keys = await compute_output_data_schema(
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                node_ports=node_ports,
                file_link_type=self.tasks_file_link_type,
            )
            log_file_url = await compute_service_log_file_upload_link(
                user_id,
                project_id,
                node_id,
                file_link_type=self.tasks_file_link_type,
            )
            task_labels = compute_task_labels(
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                run_metadata=metadata,
                node_requirements=node_image.node_requirements,
            )
            task_envs = await compute_task_envs(
                self.app,
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                node_image=node_image,
                metadata=metadata,
            )

            try:
                assert self.app.state  # nosec
                assert self.app.state.settings  # nosec
                settings: AppSettings = self.app.state.settings
                task_future = self.backend.client.submit(
                    remote_fct,
                    docker_auth=DockerBasicAuth(
                        server_address=settings.DIRECTOR_V2_DOCKER_REGISTRY.resolved_registry_url,
                        username=settings.DIRECTOR_V2_DOCKER_REGISTRY.REGISTRY_USER,
                        password=settings.DIRECTOR_V2_DOCKER_REGISTRY.REGISTRY_PW,
                    ),
                    service_key=node_image.name,
                    service_version=node_image.tag,
                    input_data=input_data,
                    output_data_keys=output_data_keys,
                    log_file_url=log_file_url,
                    command=node_image.command,
                    task_envs=task_envs,
                    task_labels=task_labels,
                    s3_settings=s3_settings,
                    boot_mode=node_image.boot_mode,
                    key=job_id,
                    resources=dask_resources,
                    retries=0,
                )
                # NOTE: the callback is running in a secondary thread, and takes a future as arg
                task_future.add_done_callback(lambda _: callback())

                list_of_node_id_to_job_id.append((node_id, job_id))
                await wrap_client_async_routine(
                    self.backend.client.publish_dataset(task_future, name=job_id)
                )

                _logger.debug(
                    "Dask task %s started [%s]",
                    f"{task_future.key=}",
                    f"{node_image.command=}",
                )
            except Exception:
                # Dask raises a base Exception here in case of connection error, this will raise a more precise one
                check_scheduler_status(self.backend.client)
                # if the connection is good, then the problem is different, so we re-raise
                raise
        return list_of_node_id_to_job_id

    async def get_tasks_status(self, job_ids: list[str]) -> list[RunningState]:
        check_scheduler_is_still_the_same(
            self.backend.scheduler_id, self.backend.client
        )
        check_communication_with_scheduler_is_open(self.backend.client)
        check_scheduler_status(self.backend.client)

        # try to get the task from the scheduler
        def _get_pipeline_statuses(
            dask_scheduler: distributed.Scheduler,
        ) -> dict[str, str | None]:
            statuses: dict[str, str | None] = dask_scheduler.get_task_status(
                keys=job_ids
            )
            return statuses

        task_statuses = await wrap_client_async_routine(
            self.backend.client.run_on_scheduler(_get_pipeline_statuses)
        )
        _logger.debug("found dask task statuses: %s", f"{task_statuses=}")

        running_states: list[RunningState] = []
        for job_id in job_ids:
            dask_status = task_statuses.get(job_id, "lost")
            if dask_status == "erred":
                # find out if this was a cancellation
                exception = await wrap_client_async_routine(
                    distributed.Future(job_id).exception(
                        timeout=_DASK_DEFAULT_TIMEOUT_S
                    )
                )

                if isinstance(exception, TaskCancelledError):
                    running_states.append(RunningState.ABORTED)
                else:
                    assert exception  # nosec
                    _logger.warning(
                        "Task  %s completed in error:\n%s\nTrace:\n%s",
                        job_id,
                        exception,
                        "".join(traceback.format_exception(exception)),
                    )
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
        _logger.debug("cancelling task with %s", f"{job_id=}")
        try:
            task_future: distributed.Future = await wrap_client_async_routine(
                self.backend.client.get_dataset(name=job_id)
            )
            # NOTE: It seems there is a bug in the pubsub system in dask
            # Event are more robust to connections/disconnections
            cancel_event = await distributed.Event(
                name=TaskCancelEventName.format(job_id), client=self.backend.client
            )
            await wrap_client_async_routine(cancel_event.set())
            await wrap_client_async_routine(task_future.cancel())
            _logger.debug("Dask task %s cancelled", task_future.key)
        except KeyError:
            _logger.warning("Unknown task cannot be aborted: %s", f"{job_id=}")

    async def get_task_result(self, job_id: str) -> TaskOutputData:
        _logger.debug("getting result of %s", f"{job_id=}")
        try:
            task_future: distributed.Future = await wrap_client_async_routine(
                self.backend.client.get_dataset(name=job_id)
            )
            return await wrap_client_async_routine(
                task_future.result(timeout=_DASK_DEFAULT_TIMEOUT_S)
            )
        except KeyError as exc:
            raise ComputationalBackendTaskNotFoundError(job_id=job_id) from exc
        except distributed.TimeoutError as exc:
            raise ComputationalBackendTaskResultsNotReadyError from exc

    async def release_task_result(self, job_id: str) -> None:
        _logger.debug("releasing results for %s", f"{job_id=}")
        try:
            # first check if the key exists
            await wrap_client_async_routine(
                self.backend.client.get_dataset(name=job_id)
            )
            await wrap_client_async_routine(
                self.backend.client.unpublish_dataset(name=job_id)
            )
        except KeyError:
            _logger.warning("Unknown task cannot be unpublished: %s", f"{job_id=}")

    async def get_cluster_details(self) -> ClusterDetails:
        check_scheduler_is_still_the_same(
            self.backend.scheduler_id, self.backend.client
        )
        check_communication_with_scheduler_is_open(self.backend.client)
        check_scheduler_status(self.backend.client)
        scheduler_info = self.backend.client.scheduler_info()
        scheduler_status = self.backend.client.status
        dashboard_link = self.backend.client.dashboard_link

        def _get_worker_used_resources(
            dask_scheduler: distributed.Scheduler,
        ) -> dict[str, dict]:
            used_resources = {}
            for worker_name, worker_state in dask_scheduler.workers.items():
                used_resources[worker_name] = worker_state.used_resources
            return used_resources

        with log_catch(_logger, reraise=False):
            # NOTE: this runs directly on the dask-scheduler and may rise exceptions
            used_resources_per_worker: dict[
                str, dict[str, Any]
            ] = await wrap_client_async_routine(
                self.backend.client.run_on_scheduler(_get_worker_used_resources)
            )

            # let's update the scheduler info, with default to 0s since sometimes
            # workers are destroyed/created without us knowing right away
            for worker_name, worker_info in scheduler_info.get("workers", {}).items():
                used_resources: dict[str, float] = deepcopy(
                    worker_info.get("resources", {})
                )
                # reset default values
                for res_name in used_resources:
                    used_resources[res_name] = 0
                # if the scheduler has info, let's override them
                used_resources = used_resources_per_worker.get(
                    worker_name, used_resources
                )
                worker_info.update(used_resources=used_resources)

        assert dashboard_link  # nosec
        return ClusterDetails(
            scheduler=Scheduler(status=scheduler_status, **scheduler_info),
            dashboard_link=parse_obj_as(AnyUrl, dashboard_link),
        )

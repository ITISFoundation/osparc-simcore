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
from typing import Any, cast

import dask.typing
import distributed
from aiohttp import ClientResponseError
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.io import (
    TaskCancelEventName,
    TaskInputData,
    TaskOutputData,
    TaskOutputDataSchema,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerEnvsDict,
    ContainerLabelsDict,
    ContainerRemoteFct,
    ContainerTaskParameters,
    LogFileUploadURL,
    TaskOwner,
)
from dask_task_models_library.resource_constraints import (
    create_ec2_resource_constraint_key,
)
from distributed.scheduler import TaskStateState as DaskSchedulerTaskState
from fastapi import FastAPI
from models_library.api_schemas_directorv2.clusters import ClusterDetails, Scheduler
from models_library.clusters import ClusterAuthentication, ClusterID, ClusterTypeInModel
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import HardwareInfo
from models_library.users import UserID
from pydantic import TypeAdapter, ValidationError
from pydantic.networks import AnyUrl
from servicelib.logging_utils import log_catch
from settings_library.s3 import S3Settings
from simcore_sdk.node_ports_common.exceptions import NodeportsException
from simcore_sdk.node_ports_v2 import FileLinkType
from tenacity.asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from ..core.errors import (
    ComputationalBackendNoS3AccessError,
    ComputationalBackendTaskNotFoundError,
    ComputationalBackendTaskResultsNotReadyError,
    TaskSchedulingError,
)
from ..core.settings import AppSettings, ComputationalBackendSettings
from ..models.comp_runs import RunMetadataDict
from ..models.comp_tasks import Image
from ..models.dask_subsystem import DaskClientTaskState, DaskJobID, DaskResources
from ..modules.storage import StorageClient
from ..utils import dask as dask_utils
from ..utils.dask_client_utils import (
    DaskSubSystem,
    TaskHandlers,
    create_internal_client_based_on_auth,
)

_logger = logging.getLogger(__name__)


# NOTE: processing does not mean the task is currently being computed, it means
# the task was accepted by a worker, but might still be queud in it
# see https://distributed.dask.org/en/stable/scheduling-state.html#task-state


_DASK_TASK_STATUS_DASK_CLIENT_TASK_STATE_MAP: dict[
    DaskSchedulerTaskState, DaskClientTaskState
] = {
    "queued": DaskClientTaskState.PENDING,
    "released": DaskClientTaskState.PENDING,
    "waiting": DaskClientTaskState.PENDING,
    "no-worker": DaskClientTaskState.NO_WORKER,
    "processing": DaskClientTaskState.PENDING_OR_STARTED,
    "memory": DaskClientTaskState.SUCCESS,
    "erred": DaskClientTaskState.ERRED,
    "forgotten": DaskClientTaskState.LOST,
}


_DASK_DEFAULT_TIMEOUT_S = 1


_UserCallbackInSepThread = Callable[[], None]


@dataclass(frozen=True, kw_only=True, slots=True)
class PublishedComputationTask:
    node_id: NodeID
    job_id: DaskJobID


@dataclass
class DaskClient:
    app: FastAPI
    backend: DaskSubSystem
    settings: ComputationalBackendSettings
    tasks_file_link_type: FileLinkType
    cluster_type: ClusterTypeInModel

    _subscribed_tasks: list[asyncio.Task] = field(default_factory=list)

    @classmethod
    async def create(
        cls,
        app: FastAPI,
        settings: ComputationalBackendSettings,
        endpoint: AnyUrl,
        authentication: ClusterAuthentication,
        tasks_file_link_type: FileLinkType,
        cluster_type: ClusterTypeInModel,
    ) -> "DaskClient":
        _logger.info(
            "Initiating connection to %s with auth: %s, type: %s",
            f"dask-scheduler/gateway at {endpoint}",
            authentication,
            cluster_type,
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
                dask_utils.check_scheduler_status(backend.client)
                instance = cls(
                    app=app,
                    backend=backend,
                    settings=settings,
                    tasks_file_link_type=tasks_file_link_type,
                    cluster_type=cluster_type,
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
                dask_utils.dask_sub_consumer_task(dask_sub, handler),
                name=f"{dask_sub.name}_dask_sub_consumer_task",
            )
            for dask_sub, handler in _event_consumer_map
        ]

    async def _publish_in_dask(  # noqa: PLR0913 # pylint: disable=too-many-arguments
        self,
        *,
        remote_fct: ContainerRemoteFct | None = None,
        node_image: Image,
        input_data: TaskInputData,
        output_data_keys: TaskOutputDataSchema,
        log_file_url: AnyUrl,
        task_envs: ContainerEnvsDict,
        task_labels: ContainerLabelsDict,
        task_owner: TaskOwner,
        s3_settings: S3Settings | None,
        dask_resources: DaskResources,
        node_id: NodeID,
        job_id: DaskJobID,
        callback: _UserCallbackInSepThread,
    ) -> PublishedComputationTask:
        def _comp_sidecar_fct(
            *,
            task_parameters: ContainerTaskParameters,
            docker_auth: DockerBasicAuth,
            log_file_url: LogFileUploadURL,
            s3_settings: S3Settings | None,
        ) -> TaskOutputData:
            """This function is serialized by the Dask client and sent over to the Dask sidecar(s)
            Therefore, (screaming here) DO NOT MOVE THAT IMPORT ANYWHERE ELSE EVER!!"""
            from simcore_service_dask_sidecar.tasks import (  # type: ignore[import-not-found]  # this runs inside the dask-sidecar
                run_computational_sidecar,
            )

            return run_computational_sidecar(  # type: ignore[no-any-return] # this runs inside the dask-sidecar
                task_parameters=task_parameters,
                docker_auth=docker_auth,
                log_file_url=log_file_url,
                s3_settings=s3_settings,
            )

        if remote_fct is None:
            remote_fct = _comp_sidecar_fct
        try:
            assert self.app.state  # nosec
            assert self.app.state.settings  # nosec
            settings: AppSettings = self.app.state.settings
            task_future = self.backend.client.submit(
                remote_fct,
                task_parameters=ContainerTaskParameters(
                    image=node_image.name,
                    tag=node_image.tag,
                    input_data=input_data,
                    output_data_keys=output_data_keys,
                    command=node_image.command,
                    envs=task_envs,
                    labels=task_labels,
                    boot_mode=node_image.boot_mode,
                    task_owner=task_owner,
                ),
                docker_auth=DockerBasicAuth(
                    server_address=settings.DIRECTOR_V2_DOCKER_REGISTRY.resolved_registry_url,
                    username=settings.DIRECTOR_V2_DOCKER_REGISTRY.REGISTRY_USER,
                    password=settings.DIRECTOR_V2_DOCKER_REGISTRY.REGISTRY_PW,
                ),
                log_file_url=log_file_url,
                s3_settings=s3_settings,
                key=job_id,
                resources=dask_resources,
                retries=0,
                pure=False,
            )
            # NOTE: the callback is running in a secondary thread, and takes a future as arg
            task_future.add_done_callback(lambda _: callback())

            await dask_utils.wrap_client_async_routine(
                self.backend.client.publish_dataset(task_future, name=job_id)
            )

            _logger.debug(
                "Dask task %s started [%s]",
                f"{task_future.key=}",
                f"{node_image.command=}",
            )
            return PublishedComputationTask(node_id=node_id, job_id=DaskJobID(job_id))
        except Exception:
            # Dask raises a base Exception here in case of connection error, this will raise a more precise one
            dask_utils.check_scheduler_status(self.backend.client)
            # if the connection is good, then the problem is different, so we re-raise
            raise

    async def send_computation_tasks(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        cluster_id: ClusterID,
        tasks: dict[NodeID, Image],
        callback: _UserCallbackInSepThread,
        remote_fct: ContainerRemoteFct | None = None,
        metadata: RunMetadataDict,
        hardware_info: HardwareInfo,
    ) -> list[PublishedComputationTask]:
        """actually sends the function remote_fct to be remotely executed. if None is kept then the default
        function that runs container will be started.

        Raises:
          - ComputationalBackendNoS3AccessError when storage is not accessible
          - ComputationalSchedulerChangedError when expected scheduler changed
          - ComputationalBackendNotConnectedError when scheduler is not connected/running
          - MissingComputationalResourcesError (only for internal cluster)
          - InsuficientComputationalResourcesError (only for internal cluster)
          - TaskSchedulingError when any other error happens
        """

        list_of_node_id_to_job_id: list[PublishedComputationTask] = []
        for node_id, node_image in tasks.items():
            job_id = dask_utils.generate_dask_job_id(
                service_key=node_image.name,
                service_version=node_image.tag,
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
            )
            assert node_image.node_requirements  # nosec
            dask_resources = dask_utils.from_node_reqs_to_dask_resources(
                node_image.node_requirements
            )
            if hardware_info.aws_ec2_instances:
                dask_resources[
                    create_ec2_resource_constraint_key(
                        hardware_info.aws_ec2_instances[0]
                    )
                ] = 1

            dask_utils.check_scheduler_is_still_the_same(
                self.backend.scheduler_id, self.backend.client
            )
            dask_utils.check_communication_with_scheduler_is_open(self.backend.client)
            dask_utils.check_scheduler_status(self.backend.client)
            await dask_utils.check_maximize_workers(self.backend.gateway_cluster)
            # NOTE: in case it's a gateway or it is an on-demand cluster
            # we do not check a priori if the task
            # is runnable because we CAN'T. A cluster might auto-scale, the worker(s)
            # might also auto-scale and the gateway does not know that a priori.
            # So, we'll just send the tasks over and see what happens after a while.
            if (self.cluster_type != ClusterTypeInModel.ON_DEMAND) and (
                self.backend.gateway is None
            ):
                dask_utils.check_if_cluster_is_able_to_run_pipeline(
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

            try:
                # This instance is created only once so it can be reused in calls below
                node_ports = await dask_utils.create_node_ports(
                    db_engine=self.app.state.engine,
                    user_id=user_id,
                    project_id=project_id,
                    node_id=node_id,
                )
                # NOTE: for download there is no need to go with S3 links
                input_data = await dask_utils.compute_input_data(
                    project_id=project_id,
                    node_id=node_id,
                    node_ports=node_ports,
                    file_link_type=FileLinkType.PRESIGNED,
                )
                output_data_keys = await dask_utils.compute_output_data_schema(
                    user_id=user_id,
                    project_id=project_id,
                    node_id=node_id,
                    node_ports=node_ports,
                    file_link_type=self.tasks_file_link_type,
                )
                log_file_url = await dask_utils.compute_service_log_file_upload_link(
                    user_id,
                    project_id,
                    node_id,
                    file_link_type=self.tasks_file_link_type,
                )
                task_labels = dask_utils.compute_task_labels(
                    user_id=user_id,
                    project_id=project_id,
                    node_id=node_id,
                    run_metadata=metadata,
                    node_requirements=node_image.node_requirements,
                )
                task_envs = await dask_utils.compute_task_envs(
                    self.app,
                    user_id=user_id,
                    project_id=project_id,
                    node_id=node_id,
                    node_image=node_image,
                    metadata=metadata,
                )
                task_owner = dask_utils.compute_task_owner(
                    user_id, project_id, node_id, metadata.get("project_metadata", {})
                )
                list_of_node_id_to_job_id.append(
                    await self._publish_in_dask(
                        remote_fct=remote_fct,
                        node_image=node_image,
                        input_data=input_data,
                        output_data_keys=output_data_keys,
                        log_file_url=log_file_url,
                        task_envs=task_envs,
                        task_labels=task_labels,
                        task_owner=task_owner,
                        s3_settings=s3_settings,
                        dask_resources=dask_resources,
                        node_id=node_id,
                        job_id=job_id,
                        callback=callback,
                    )
                )
            except (NodeportsException, ValidationError, ClientResponseError) as exc:
                raise TaskSchedulingError(
                    project_id=project_id, node_id=node_id, msg=f"{exc}"
                ) from exc

        return list_of_node_id_to_job_id

    async def get_tasks_status(self, job_ids: list[str]) -> list[DaskClientTaskState]:
        dask_utils.check_scheduler_is_still_the_same(
            self.backend.scheduler_id, self.backend.client
        )
        dask_utils.check_communication_with_scheduler_is_open(self.backend.client)
        dask_utils.check_scheduler_status(self.backend.client)

        # try to get the task from the scheduler
        def _get_pipeline_statuses(
            dask_scheduler: distributed.Scheduler,
        ) -> dict[dask.typing.Key, DaskSchedulerTaskState | None]:
            statuses: dict[
                dask.typing.Key, DaskSchedulerTaskState | None
            ] = dask_scheduler.get_task_status(keys=job_ids)
            return statuses

        task_statuses: dict[
            dask.typing.Key, DaskSchedulerTaskState | None
        ] = await self.backend.client.run_on_scheduler(_get_pipeline_statuses)
        assert isinstance(task_statuses, dict)  # nosec

        _logger.debug("found dask task statuses: %s", f"{task_statuses=}")

        running_states: list[DaskClientTaskState] = []
        for job_id in job_ids:
            dask_status = cast(
                DaskSchedulerTaskState | None, task_statuses.get(job_id, "lost")
            )
            if dask_status == "erred":
                # find out if this was a cancellation
                exception = await distributed.Future(job_id).exception(
                    timeout=_DASK_DEFAULT_TIMEOUT_S
                )
                assert isinstance(exception, Exception)  # nosec

                if isinstance(exception, TaskCancelledError):
                    running_states.append(DaskClientTaskState.ABORTED)
                else:
                    assert exception  # nosec
                    _logger.warning(
                        "Task  %s completed in error:\n%s\nTrace:\n%s",
                        job_id,
                        exception,
                        "".join(traceback.format_exception(exception)),
                    )
                    running_states.append(DaskClientTaskState.ERRED)
            elif dask_status is None:
                running_states.append(DaskClientTaskState.LOST)
            else:
                running_states.append(
                    _DASK_TASK_STATUS_DASK_CLIENT_TASK_STATE_MAP.get(
                        dask_status, DaskClientTaskState.LOST
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
            task_future: distributed.Future = (
                await dask_utils.wrap_client_async_routine(
                    self.backend.client.get_dataset(name=job_id)
                )
            )
            # NOTE: It seems there is a bug in the pubsub system in dask
            # Event are more robust to connections/disconnections
            cancel_event = await distributed.Event(
                name=TaskCancelEventName.format(job_id), client=self.backend.client
            )
            await dask_utils.wrap_client_async_routine(cancel_event.set())
            await dask_utils.wrap_client_async_routine(task_future.cancel())
            _logger.debug("Dask task %s cancelled", task_future.key)
        except KeyError:
            _logger.warning("Unknown task cannot be aborted: %s", f"{job_id=}")

    async def get_task_result(self, job_id: str) -> TaskOutputData:
        _logger.debug("getting result of %s", f"{job_id=}")
        try:
            task_future: distributed.Future = (
                await dask_utils.wrap_client_async_routine(
                    self.backend.client.get_dataset(name=job_id)
                )
            )
            return cast(
                TaskOutputData,
                await task_future.result(timeout=_DASK_DEFAULT_TIMEOUT_S),
            )
        except KeyError as exc:
            raise ComputationalBackendTaskNotFoundError(job_id=job_id) from exc
        except distributed.TimeoutError as exc:
            raise ComputationalBackendTaskResultsNotReadyError from exc

    async def release_task_result(self, job_id: str) -> None:
        _logger.debug("releasing results for %s", f"{job_id=}")
        try:
            # first check if the key exists
            await dask_utils.wrap_client_async_routine(
                self.backend.client.get_dataset(name=job_id)
            )
            await dask_utils.wrap_client_async_routine(
                self.backend.client.unpublish_dataset(name=job_id)
            )
        except KeyError:
            _logger.warning("Unknown task cannot be unpublished: %s", f"{job_id=}")

    async def get_cluster_details(self) -> ClusterDetails:
        dask_utils.check_scheduler_is_still_the_same(
            self.backend.scheduler_id, self.backend.client
        )
        dask_utils.check_communication_with_scheduler_is_open(self.backend.client)
        dask_utils.check_scheduler_status(self.backend.client)
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
            ] = await dask_utils.wrap_client_async_routine(
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
            dashboard_link=TypeAdapter(AnyUrl).validate_python(dashboard_link),
        )

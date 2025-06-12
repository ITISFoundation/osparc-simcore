"""The dask client is the osparc part that communicates with a
dask-scheduler/worker backend.

From dask documentation any Data or function must follow the criteria to be
usable in dask [http://distributed.dask.org/en/stable/limitations.html?highlight=cloudpickle#assumptions-on-functions-and-data]:
from cloudpickle import dumps, loads
loads(dumps(my_object))

"""

import asyncio
import logging
import traceback
from collections.abc import Callable, Iterable
from copy import deepcopy
from dataclasses import dataclass
from http.client import HTTPException
from typing import Any, Final, cast

import distributed
from aiohttp import ClientResponseError
from common_library.json_serialization import json_dumps
from dask_task_models_library.container_tasks.docker import DockerBasicAuth
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import TaskProgressEvent
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
from dask_task_models_library.container_tasks.utils import generate_dask_job_id
from dask_task_models_library.models import (
    TASK_LIFE_CYCLE_EVENT,
    TASK_RUNNING_PROGRESS_EVENT,
    DaskJobID,
    DaskResources,
    TaskLifeCycleState,
)
from dask_task_models_library.resource_constraints import (
    create_ec2_resource_constraint_key,
)
from fastapi import FastAPI
from models_library.api_schemas_directorv2.clusters import ClusterDetails, Scheduler
from models_library.clusters import ClusterAuthentication, ClusterTypeInModel
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.resource_tracker import HardwareInfo
from models_library.services import ServiceRunID
from models_library.users import UserID
from pydantic import TypeAdapter, ValidationError
from pydantic.networks import AnyUrl
from servicelib.logging_utils import log_catch, log_context
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
from ..modules.storage import StorageClient
from ..utils import dask as dask_utils
from ..utils.dask_client_utils import (
    DaskSubSystem,
    TaskHandlers,
    UnixTimestamp,
    connect_to_dask_scheduler,
)
from .db import get_db_engine

_logger = logging.getLogger(__name__)


_DASK_DEFAULT_TIMEOUT_S: Final[int] = 35


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
            f"dask-scheduler at {endpoint}",
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
                backend = await connect_to_dask_scheduler(endpoint, authentication)
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
                    f"dask-scheduler at {endpoint}",
                    json_dumps(attempt.retry_state.retry_object.statistics),
                )
                _logger.info(
                    "Scheduler info:\n%s",
                    json_dumps(backend.client.scheduler_info(), indent=2),
                )
                return instance
        # this is to satisfy pylance
        err_msg = "Could not create client"
        raise ValueError(err_msg)

    async def delete(self) -> None:
        with log_context(_logger, logging.INFO, msg="close dask client"):
            await self.backend.close()

    def register_handlers(self, task_handlers: TaskHandlers) -> None:
        _event_consumer_map = [
            (TaskProgressEvent.topic_name(), task_handlers.task_progress_handler),
        ]
        for topic_name, handler in _event_consumer_map:
            self.backend.client.subscribe_topic(topic_name, handler)

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
            from simcore_service_dask_sidecar.worker import (  # type: ignore[import-not-found] # this runs inside the dask-sidecar
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
            await distributed.Variable(job_id, client=self.backend.client).set(
                task_future
            )

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
        tasks: dict[NodeID, Image],
        callback: _UserCallbackInSepThread,
        remote_fct: ContainerRemoteFct | None = None,
        metadata: RunMetadataDict,
        hardware_info: HardwareInfo,
        resource_tracking_run_id: ServiceRunID,
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
            job_id = generate_dask_job_id(
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
            # NOTE: in case it is an on-demand cluster
            # we do not check a priori if the task
            # is runnable because we CAN'T. A cluster might auto-scale, the worker(s)
            # might also auto-scale we do not know that a priori.
            # So, we'll just send the tasks over and see what happens after a while.
            if self.cluster_type != ClusterTypeInModel.ON_DEMAND:
                dask_utils.check_if_cluster_is_able_to_run_pipeline(
                    project_id=project_id,
                    node_id=node_id,
                    scheduler_info=self.backend.client.scheduler_info(),
                    task_resources=dask_resources,
                    node_image=node_image,
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
                    db_engine=get_db_engine(self.app),
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
                    resource_tracking_run_id=resource_tracking_run_id,
                    wallet_id=metadata.get("wallet_id"),
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

    async def get_tasks_progress(
        self, job_ids: list[str]
    ) -> list[TaskProgressEvent | None]:
        dask_utils.check_scheduler_is_still_the_same(
            self.backend.scheduler_id, self.backend.client
        )
        dask_utils.check_communication_with_scheduler_is_open(self.backend.client)
        dask_utils.check_scheduler_status(self.backend.client)

        async def _get_task_progress(job_id: str) -> TaskProgressEvent | None:
            dask_events: tuple[tuple[UnixTimestamp, str], ...] = (
                await self.backend.client.get_events(
                    TASK_RUNNING_PROGRESS_EVENT.format(key=job_id)
                )
            )
            if not dask_events:
                return None
            # we are interested in the last event
            return TaskProgressEvent.model_validate_json(dask_events[-1][1])

        return await asyncio.gather(*(_get_task_progress(job_id) for job_id in job_ids))

    async def get_tasks_status(self, job_ids: Iterable[str]) -> list[RunningState]:
        dask_utils.check_scheduler_is_still_the_same(
            self.backend.scheduler_id, self.backend.client
        )
        dask_utils.check_communication_with_scheduler_is_open(self.backend.client)
        dask_utils.check_scheduler_status(self.backend.client)

        async def _get_task_state(job_id: str) -> RunningState:
            dask_events: tuple[tuple[UnixTimestamp, str], ...] = (
                await self.backend.client.get_events(
                    TASK_LIFE_CYCLE_EVENT.format(key=job_id)
                )
            )
            if not dask_events:
                return RunningState.UNKNOWN
            # we are interested in the last event
            parsed_event = TaskLifeCycleState.model_validate(dask_events[-1][1])

            if parsed_event.state == RunningState.FAILED:
                try:
                    # find out if this was a cancellation
                    var = distributed.Variable(job_id, client=self.backend.client)
                    future: distributed.Future = await var.get(
                        timeout=_DASK_DEFAULT_TIMEOUT_S
                    )
                    exception = await future.exception(timeout=_DASK_DEFAULT_TIMEOUT_S)
                    assert isinstance(exception, Exception)  # nosec

                    if isinstance(exception, TaskCancelledError):
                        return RunningState.ABORTED
                    assert exception  # nosec
                    _logger.warning(
                        "Task  %s completed in error:\n%s\nTrace:\n%s",
                        job_id,
                        exception,
                        "".join(traceback.format_exception(exception)),
                    )
                    return RunningState.FAILED
                except TimeoutError:
                    _logger.warning(
                        "Task  %s could not be retrieved from dask-scheduler, it is lost\n"
                        "TIP:If the task was unpublished this can happen, or if the dask-scheduler was restarted.",
                        job_id,
                    )
                    return RunningState.UNKNOWN

            return parsed_event.state

        return await asyncio.gather(*(_get_task_state(job_id) for job_id in job_ids))

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
            raise ComputationalBackendTaskResultsNotReadyError(job_id=job_id) from exc

    async def release_task_result(self, job_id: str) -> None:
        _logger.debug("releasing results for %s", f"{job_id=}")
        try:
            # NOTE: The distributed Variable holds the future of the tasks in the dask-scheduler
            # Alas, deleting the variable is done asynchronously and there is no way to ensure
            # the variable was effectively deleted.
            # This is annoying as one can re-create the variable without error.
            var = distributed.Variable(job_id, client=self.backend.client)
            await asyncio.get_event_loop().run_in_executor(None, var.delete)
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
            used_resources_per_worker: dict[str, dict[str, Any]] = (
                await dask_utils.wrap_client_async_routine(
                    self.backend.client.run_on_scheduler(_get_worker_used_resources)
                )
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

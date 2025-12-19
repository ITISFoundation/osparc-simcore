import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Final

import arrow
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from dask_task_models_library.container_tasks.errors import TaskCancelledError
from dask_task_models_library.container_tasks.events import (
    TaskProgressEvent,
)
from dask_task_models_library.container_tasks.io import TaskOutputData
from models_library.clusters import BaseCluster
from models_library.errors import ErrorDict
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rabbitmq_messages import SimcorePlatformStatus
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from pydantic import PositiveInt
from servicelib.common_headers import UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
from servicelib.logging_utils import log_catch, log_context
from servicelib.redis._semaphore_decorator import (
    with_limited_concurrency_cm,
)
from servicelib.utils import limited_as_completed, limited_gather
from simcore_sdk.node_ports_common.exceptions import S3InvalidPathError

from ..._meta import APP_NAME
from ...core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalBackendOnDemandNotReadyError,
    ComputationalBackendTaskResultsNotReadyError,
    PortsValidationError,
)
from ...models.comp_runs import CompRunsAtDB, Iteration, RunMetadataDict
from ...models.comp_tasks import CompTaskAtDB
from ...utils.dask import (
    clean_task_output_and_log_files_if_invalid,
    parse_output_data,
)
from ...utils.dask_client_utils import TaskHandlers, UnixTimestamp
from ...utils.rabbitmq import (
    publish_service_progress,
    publish_service_resource_tracking_stopped,
    publish_service_stopped_metrics,
)
from ..clusters_keeper import get_or_create_on_demand_cluster
from ..dask_client import DaskClient
from ..dask_clients_pool import DaskClientsPool
from ..db.repositories.comp_runs import (
    CompRunsRepository,
)
from ..db.repositories.comp_tasks import CompTasksRepository
from ._models import TaskStateTracker
from ._scheduler_base import BaseCompScheduler
from ._utils import (
    WAITING_FOR_START_STATES,
)

_logger = logging.getLogger(__name__)

_DASK_CLIENT_RUN_REF: Final[str] = "{user_id}:{project_id}:{run_id}"
_TASK_RETRIEVAL_ERROR_TYPE: Final[str] = "task-result-retrieval-timeout"
_TASK_RETRIEVAL_ERROR_CONTEXT_TIME_KEY: Final[str] = "check_time"
_PUBLICATION_CONCURRENCY_LIMIT: Final[int] = 10


@asynccontextmanager
async def _cluster_dask_client(
    user_id: UserID,
    scheduler: "DaskScheduler",
    *,
    use_on_demand_clusters: bool,
    project_id: ProjectID,
    run_id: PositiveInt,
    run_metadata: RunMetadataDict,
) -> AsyncIterator[DaskClient]:
    cluster: BaseCluster = scheduler.settings.default_cluster
    if use_on_demand_clusters:
        cluster = await get_or_create_on_demand_cluster(
            scheduler.rabbitmq_rpc_client,
            user_id=user_id,
            wallet_id=run_metadata.get("wallet_id"),
        )

    @with_limited_concurrency_cm(
        scheduler.redis_client,
        key=f"{APP_NAME}-cluster-user_id_{user_id}-wallet_id_{run_metadata.get('wallet_id')}",
        capacity=scheduler.settings.COMPUTATIONAL_BACKEND_PER_CLUSTER_MAX_DISTRIBUTED_CONCURRENT_CONNECTIONS,
        blocking=True,
        blocking_timeout=None,
    )
    @asynccontextmanager
    async def _acquire_client(
        user_id: UserID, scheduler: "DaskScheduler"
    ) -> AsyncIterator[DaskClient]:
        async with scheduler.dask_clients_pool.acquire(
            cluster,
            ref=_DASK_CLIENT_RUN_REF.format(
                user_id=user_id, project_id=project_id, run_id=run_id
            ),
        ) as client:
            yield client

    async with _acquire_client(user_id, scheduler) as client:
        yield client


@dataclass
class DaskScheduler(BaseCompScheduler):
    dask_clients_pool: DaskClientsPool

    def __post_init__(self) -> None:
        self.dask_clients_pool.register_handlers(
            TaskHandlers(
                self._task_progress_change_handler,
            )
        )

    async def _start_tasks(
        self,
        *,
        user_id: UserID,
        project_id: ProjectID,
        scheduled_tasks: dict[NodeID, CompTaskAtDB],
        comp_run: CompRunsAtDB,
        wake_up_callback: Callable[[], None],
    ) -> None:
        # now transfer the pipeline to the dask scheduler
        async with _cluster_dask_client(
            user_id,
            self,
            use_on_demand_clusters=comp_run.use_on_demand_clusters,
            project_id=comp_run.project_uuid,
            run_id=comp_run.run_id,
            run_metadata=comp_run.metadata,
        ) as client:
            # Change the tasks state to PENDING
            comp_tasks_repo = CompTasksRepository.instance(self.db_engine)
            await comp_tasks_repo.update_project_tasks_state(
                project_id,
                comp_run.run_id,
                list(scheduled_tasks.keys()),
                RunningState.PENDING,
            )
            # each task is started independently

            for node_id, task in scheduled_tasks.items():
                published_tasks = await client.send_computation_tasks(
                    user_id=user_id,
                    project_id=project_id,
                    tasks={node_id: task.image},
                    hardware_info=task.hardware_info,
                    callback=wake_up_callback,
                    metadata=comp_run.metadata,
                    resource_tracking_run_id=ServiceRunID.get_resource_tracking_run_id_for_computational(
                        user_id, project_id, node_id, comp_run.iteration
                    ),
                )

                # update the database so we do have the correct job_ids there
                await limited_gather(
                    *(
                        comp_tasks_repo.update_project_task_job_id(
                            project_id, task.node_id, comp_run.run_id, task.job_id
                        )
                        for task in published_tasks
                    ),
                    log=_logger,
                    limit=1,
                )

    async def _get_tasks_status(
        self,
        user_id: UserID,
        tasks: list[CompTaskAtDB],
        comp_run: CompRunsAtDB,
    ) -> list[RunningState]:
        try:
            async with _cluster_dask_client(
                user_id,
                self,
                use_on_demand_clusters=comp_run.use_on_demand_clusters,
                project_id=comp_run.project_uuid,
                run_id=comp_run.run_id,
                run_metadata=comp_run.metadata,
            ) as client:
                return await client.get_tasks_status([f"{t.job_id}" for t in tasks])

        except ComputationalBackendOnDemandNotReadyError:
            _logger.info("The on demand computational backend is not ready yet...")
            return [RunningState.WAITING_FOR_CLUSTER] * len(tasks)

    async def _process_executing_tasks(
        self,
        user_id: UserID,
        tasks: list[CompTaskAtDB],
        comp_run: CompRunsAtDB,
    ) -> None:
        task_progress_events = []
        try:
            async with _cluster_dask_client(
                user_id,
                self,
                use_on_demand_clusters=comp_run.use_on_demand_clusters,
                project_id=comp_run.project_uuid,
                run_id=comp_run.run_id,
                run_metadata=comp_run.metadata,
            ) as client:
                task_progress_events = [
                    t
                    for t in await client.get_tasks_progress(
                        [f"{t.job_id}" for t in tasks],
                    )
                    if t is not None
                ]
            for progress_event in task_progress_events:
                await CompTasksRepository(self.db_engine).update_project_task_progress(
                    progress_event.task_owner.project_id,
                    progress_event.task_owner.node_id,
                    comp_run.run_id,
                    progress_event.progress,
                )

        except ComputationalBackendOnDemandNotReadyError:
            _logger.info("The on demand computational backend is not ready yet...")

        comp_tasks_repo = CompTasksRepository(self.db_engine)
        for task in task_progress_events:
            await comp_tasks_repo.update_project_task_progress(
                task.task_owner.project_id,
                task.task_owner.node_id,
                comp_run.run_id,
                task.progress,
            )
        await limited_gather(
            *(
                publish_service_progress(
                    self.rabbitmq_client,
                    user_id=t.task_owner.user_id,
                    project_id=t.task_owner.project_id,
                    node_id=t.task_owner.node_id,
                    progress=t.progress,
                )
                for t in task_progress_events
            ),
            log=_logger,
            limit=_PUBLICATION_CONCURRENCY_LIMIT,
        )

    async def _release_resources(self, comp_run: CompRunsAtDB) -> None:
        """release resources used by the scheduler for a given user and project"""
        with (
            log_catch(_logger, reraise=False),
            log_context(
                _logger,
                logging.INFO,
                msg=f"releasing resources for {comp_run.user_id=}, {comp_run.project_uuid=}, {comp_run.run_id=}",
            ),
        ):
            await self.dask_clients_pool.release_client_ref(
                ref=_DASK_CLIENT_RUN_REF.format(
                    user_id=comp_run.user_id,
                    project_id=comp_run.project_uuid,
                    run_id=comp_run.run_id,
                )
            )

    async def _stop_tasks(
        self, user_id: UserID, tasks: list[CompTaskAtDB], comp_run: CompRunsAtDB
    ) -> None:
        # NOTE: if this exception raises, it means the backend was anyway not up
        with contextlib.suppress(ComputationalBackendOnDemandNotReadyError):
            async with _cluster_dask_client(
                user_id,
                self,
                use_on_demand_clusters=comp_run.use_on_demand_clusters,
                project_id=comp_run.project_uuid,
                run_id=comp_run.run_id,
                run_metadata=comp_run.metadata,
            ) as client:
                for t in tasks:
                    if not t.job_id:
                        _logger.warning("%s has no job_id, cannot be stopped", t)
                        continue
                    await client.abort_computation_task(t.job_id)
                    # tasks that have no-worker must be unpublished as these are blocking forever
                    if t.state is RunningState.WAITING_FOR_RESOURCES:
                        await client.release_task_result(t.job_id)

    async def _process_completed_tasks(
        self,
        user_id: UserID,
        tasks: list[TaskStateTracker],
        iteration: Iteration,
        comp_run: CompRunsAtDB,
    ) -> None:
        async with _cluster_dask_client(
            user_id,
            self,
            use_on_demand_clusters=comp_run.use_on_demand_clusters,
            project_id=comp_run.project_uuid,
            run_id=comp_run.run_id,
            run_metadata=comp_run.metadata,
        ) as client:
            tasks_results = await limited_gather(
                *(
                    client.get_task_result(t.current.job_id or "undefined")
                    for t in tasks
                ),
                reraise=False,
                log=_logger,
                limit=1,  # to avoid overloading the dask scheduler
            )
            async for future in limited_as_completed(
                (
                    self._process_task_result(
                        task,
                        result,
                        iteration,
                        comp_run,
                    )
                    for task, result in zip(tasks, tasks_results, strict=True)
                ),
                limit=10,  # this is not accessing the dask-scheduelr (only db)
            ):
                with log_catch(_logger, reraise=False):
                    task_can_be_cleaned, job_id = await future
                    if task_can_be_cleaned and job_id:
                        await client.release_task_result(job_id)

    async def _handle_successful_run(
        self,
        task: CompTaskAtDB,
        result: TaskOutputData,
        log_error_context: dict[str, Any],
    ) -> tuple[RunningState, SimcorePlatformStatus, list[ErrorDict], bool]:
        assert task.job_id  # nosec
        try:
            await parse_output_data(
                self.db_engine,
                task.job_id,
                result,
            )
            return RunningState.SUCCESS, SimcorePlatformStatus.OK, [], True
        except PortsValidationError as err:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    "Unexpected error while parsing output data, comp_tasks/comp_pipeline is not in sync with what was started",
                    error=err,
                    error_context=log_error_context,
                )
            )
            # NOTE: simcore platform state is still OK as the task ran fine, the issue is likely due to the service labels
            return RunningState.FAILED, SimcorePlatformStatus.OK, err.get_errors(), True
        except S3InvalidPathError as err:
            msg = "Unexpected error while retrieving output data, the data was not found in storage"
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    msg,
                    error=err,
                    error_context=log_error_context,
                )
            )
            # NOTE: The platform state is BAD as the output data in a successful task must be available
            return (
                RunningState.FAILED,
                SimcorePlatformStatus.BAD,
                [
                    ErrorDict(
                        loc=(f"{task.project_id}", f"{task.node_id}"),
                        msg=f"{msg}: {err}",
                        type="storage.s3.invalid-path",
                    )
                ],
                True,
            )

    async def _handle_computational_retrieval_error(
        self,
        task: CompTaskAtDB,
        result: ComputationalBackendTaskResultsNotReadyError,
        log_error_context: dict[str, Any],
    ) -> tuple[RunningState, SimcorePlatformStatus, list[ErrorDict], bool]:
        _logger.warning(
            **create_troubleshooting_log_kwargs(
                f"Retrieval of task {task.job_id} result timed-out",
                error=result,
                error_context=log_error_context,
                tip="This can happen if the computational backend is overloaded with requests. It will be automatically retried again.",
            )
        )
        task_errors: list[ErrorDict] = []
        check_time = arrow.utcnow()
        if task.errors:
            for error in task.errors:
                if error["type"] == _TASK_RETRIEVAL_ERROR_TYPE:
                    # already had a timeout error, let's keep it
                    task_errors.append(error)
                    assert "ctx" in error  # nosec
                    assert _TASK_RETRIEVAL_ERROR_CONTEXT_TIME_KEY in error["ctx"]  # nosec
                    check_time = arrow.get(
                        error["ctx"][_TASK_RETRIEVAL_ERROR_CONTEXT_TIME_KEY]
                    )
                    break
        if not task_errors:
            # first time we have this error
            task_errors.append(
                ErrorDict(
                    loc=(f"{task.project_id}", f"{task.node_id}"),
                    msg=f"{result}",
                    type=_TASK_RETRIEVAL_ERROR_TYPE,
                    ctx={
                        _TASK_RETRIEVAL_ERROR_CONTEXT_TIME_KEY: f"{check_time}",
                        **log_error_context,
                    },
                )
            )

        # if the task has been running for too long, we consider it failed
        elapsed_time = arrow.utcnow() - check_time
        if (
            elapsed_time
            > self.settings.COMPUTATIONAL_BACKEND_MAX_WAITING_FOR_RETRIEVING_RESULTS
        ):
            _logger.error(
                **create_troubleshooting_log_kwargs(
                    f"Task {task.job_id} failed because results could not be retrieved after {elapsed_time}",
                    error=result,
                    error_context=log_error_context,
                    tip="Please try again later or contact support if the problem persists.",
                )
            )
            return RunningState.FAILED, SimcorePlatformStatus.BAD, task_errors, True
        # state is kept as STARTED so it will be retried
        return RunningState.STARTED, SimcorePlatformStatus.BAD, task_errors, False

    @staticmethod
    async def _handle_computational_backend_not_connected_error(
        task: CompTaskAtDB,
        result: ComputationalBackendNotConnectedError,
        log_error_context: dict[str, Any],
    ) -> tuple[RunningState, SimcorePlatformStatus, list[ErrorDict], bool]:
        _logger.warning(
            **create_troubleshooting_log_kwargs(
                f"Computational backend disconnected when retrieving task {task.job_id} result",
                error=result,
                error_context=log_error_context,
                tip="This can happen if the computational backend is temporarily disconnected. It will be automatically retried again.",
            )
        )
        # NOTE: the task will be set to UNKNOWN on the next processing loop

        # state is kept as STARTED so it will be retried
        return RunningState.STARTED, SimcorePlatformStatus.BAD, [], False

    @staticmethod
    async def _handle_task_error(
        task: CompTaskAtDB,
        result: BaseException,
        log_error_context: dict[str, Any],
    ) -> tuple[RunningState, SimcorePlatformStatus, list[ErrorDict], bool]:
        # the task itself failed, check why
        if isinstance(result, TaskCancelledError):
            _logger.info(
                **create_troubleshooting_log_kwargs(
                    f"Task {task.job_id} was cancelled",
                    error=result,
                    error_context=log_error_context,
                )
            )
            return RunningState.ABORTED, SimcorePlatformStatus.OK, [], True

        _logger.info(
            **create_troubleshooting_log_kwargs(
                f"Task {task.job_id} completed with errors",
                error=result,
                error_context=log_error_context,
            )
        )
        return (
            RunningState.FAILED,
            SimcorePlatformStatus.OK,
            [
                ErrorDict(
                    loc=(f"{task.project_id}", f"{task.node_id}"),
                    msg=f"{result}",
                    type="runtime",
                )
            ],
            True,
        )

    async def _process_task_result(
        self,
        task: TaskStateTracker,
        result: BaseException | TaskOutputData,
        iteration: Iteration,
        comp_run: CompRunsAtDB,
    ) -> tuple[bool, str | None]:
        """Returns True and the job ID if the task was successfully processed and can be released from the Dask cluster."""
        with log_context(
            _logger, logging.DEBUG, msg=f"{comp_run.run_id=}, {task=}, {result=}"
        ):
            log_error_context = {
                "user_id": comp_run.user_id,
                "project_id": f"{comp_run.project_uuid}",
                "node_id": f"{task.current.node_id}",
                "job_id": task.current.job_id,
            }

            if isinstance(result, TaskOutputData):
                (
                    task_final_state,
                    simcore_platform_status,
                    task_errors,
                    task_completed,
                ) = await self._handle_successful_run(
                    task.current, result, log_error_context
                )

            elif isinstance(result, ComputationalBackendTaskResultsNotReadyError):
                (
                    task_final_state,
                    simcore_platform_status,
                    task_errors,
                    task_completed,
                ) = await self._handle_computational_retrieval_error(
                    task.current, result, log_error_context
                )
            elif isinstance(result, ComputationalBackendNotConnectedError):
                (
                    task_final_state,
                    simcore_platform_status,
                    task_errors,
                    task_completed,
                ) = await self._handle_computational_backend_not_connected_error(
                    task.current, result, log_error_context
                )
            else:
                (
                    task_final_state,
                    simcore_platform_status,
                    task_errors,
                    task_completed,
                ) = await self._handle_task_error(
                    task.current, result, log_error_context
                )

                # we need to remove any invalid files in the storage
                await clean_task_output_and_log_files_if_invalid(
                    self.db_engine,
                    comp_run.user_id,
                    comp_run.project_uuid,
                    task.current.node_id,
                )

            if task_completed:
                # resource tracking
                await publish_service_resource_tracking_stopped(
                    self.rabbitmq_client,
                    ServiceRunID.get_resource_tracking_run_id_for_computational(
                        comp_run.user_id,
                        comp_run.project_uuid,
                        task.current.node_id,
                        iteration,
                    ),
                    simcore_platform_status=simcore_platform_status,
                )
                # instrumentation
                await publish_service_stopped_metrics(
                    self.rabbitmq_client,
                    user_id=comp_run.user_id,
                    simcore_user_agent=comp_run.metadata.get(
                        "simcore_user_agent", UNDEFINED_DEFAULT_SIMCORE_USER_AGENT_VALUE
                    ),
                    task=task.current,
                    task_final_state=task_final_state,
                )

            await CompTasksRepository(self.db_engine).update_project_tasks_state(
                task.current.project_id,
                comp_run.run_id,
                [task.current.node_id],
                task_final_state if task_completed else task.previous.state,
                errors=task_errors,
                optional_progress=1 if task_completed else None,
                optional_stopped=arrow.utcnow().datetime if task_completed else None,
            )

            return task_completed, task.current.job_id

    async def _task_progress_change_handler(
        self, event: tuple[UnixTimestamp, Any]
    ) -> None:
        with log_catch(_logger, reraise=False):
            task_progress_event = TaskProgressEvent.model_validate_json(event[1])
            _logger.debug("received task progress update: %s", task_progress_event)
            user_id = task_progress_event.task_owner.user_id
            project_id = task_progress_event.task_owner.project_id
            node_id = task_progress_event.task_owner.node_id
            comp_tasks_repo = CompTasksRepository(self.db_engine)
            task = await comp_tasks_repo.get_task(project_id, node_id)
            run = await CompRunsRepository(self.db_engine).get(user_id, project_id)
            if task.state in WAITING_FOR_START_STATES:
                task.state = RunningState.STARTED
                task.progress = task_progress_event.progress
                await self._process_started_tasks(
                    [task],
                    user_id=user_id,
                    project_id=project_id,
                    iteration=run.iteration,
                    run_metadata=run.metadata,
                    run_id=run.run_id,
                )
            else:
                await comp_tasks_repo.update_project_task_progress(
                    project_id, node_id, run.run_id, task_progress_event.progress
                )
            await publish_service_progress(
                self.rabbitmq_client,
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                progress=task_progress_event.progress,
            )

# pylint: disable=too-many-instance-attributes
import logging
from dataclasses import dataclass

from celery_library.errors import TaskNotFoundError
from common_library.exclude import as_dict_exclude_none
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from models_library.functions import (
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionInputsList,
    FunctionJobCollectionID,
    FunctionJobID,
    FunctionJobStatus,
    FunctionOutputs,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobWithStatus,
    TaskID,
)
from models_library.functions_errors import (
    UnsupportedFunctionClassError,
    UnsupportedFunctionFunctionJobClassCombinationError,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.projects_state import RunningState
from models_library.rest_pagination import PageMetaInfoLimitOffset, PageOffsetInt
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.celery.models import ExecutionMetadata, TasksQueue, TaskUUID
from servicelib.celery.task_manager import TaskManager
from sqlalchemy.ext.asyncio import AsyncEngine

from ._meta import APP_NAME
from ._service_function_jobs import FunctionJobService
from ._service_functions import FunctionService
from ._service_jobs import JobService
from .api.dependencies.authentication import Identity
from .exceptions.backend_errors import (
    SolverJobOutputRequestButNotSucceededError,
    StudyJobOutputRequestButNotSucceededError,
)
from .models.api_resources import JobLinks
from .models.domain.celery_models import ApiServerOwnerMetadata
from .models.domain.functions import FunctionJobPatch
from .models.schemas.functions import FunctionJobCreationTaskStatus
from .models.schemas.jobs import JobInputs, JobPricingSpecification
from .services_http.webserver import AuthSession
from .services_rpc.storage import StorageService
from .services_rpc.wb_api_server import WbApiRpcClient

_logger = logging.getLogger(__name__)


def join_inputs(
    default_inputs: FunctionInputs | None,
    function_inputs: FunctionInputs | None,
) -> FunctionInputs:
    if default_inputs is None:
        return function_inputs

    if function_inputs is None:
        return default_inputs

    # last dict will override defaults
    return {**default_inputs, **function_inputs}


async def _celery_task_status(
    job_creation_task_id: TaskID | None,
    task_manager: TaskManager,
    user_id: UserID,
    product_name: ProductName,
) -> FunctionJobCreationTaskStatus:
    if job_creation_task_id is None:
        return FunctionJobCreationTaskStatus.NOT_YET_SCHEDULED
    owner_metadata = ApiServerOwnerMetadata(
        user_id=user_id,
        product_name=product_name,
    )
    task_uuid: TaskUUID = TypeAdapter(TaskUUID).validate_python(f"{job_creation_task_id}")
    try:
        task_status = await task_manager.get_task_status(owner_metadata=owner_metadata, task_uuid=task_uuid)
        return FunctionJobCreationTaskStatus[task_status.task_state]
    except TaskNotFoundError as err:
        user_msg = f"Job creation task not found for task_uuid={task_uuid!r}."
        _logger.exception(
            **create_troubleshooting_log_kwargs(
                user_msg,
                error=err,
                error_context={
                    "task_uuid": task_uuid,
                    "owner_metadata": owner_metadata,
                    "user_id": user_id,
                    "product_name": product_name,
                },
                tip="This probably means the celery task failed, because the task should have created the project_id.",
            )
        )
        return FunctionJobCreationTaskStatus.ERROR


@dataclass(frozen=True, kw_only=True)
class FunctionJobTaskClientService:
    user_id: UserID
    product_name: ProductName
    _web_rpc_client: WbApiRpcClient
    _storage_client: StorageService
    _job_service: JobService
    _function_service: FunctionService
    _function_job_service: FunctionJobService
    _webserver_api: AuthSession
    _celery_task_manager: TaskManager
    _async_pg_engine: AsyncEngine

    async def list_function_jobs_with_status(
        self,
        *,
        filter_by_function_id: FunctionID | None = None,
        filter_by_function_job_ids: list[FunctionJobID] | None = None,
        filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[
        list[RegisteredFunctionJobWithStatus],
        PageMetaInfoLimitOffset,
    ]:
        """Lists all function jobs for a user with pagination"""

        pagination_kwargs = as_dict_exclude_none(pagination_offset=pagination_offset, pagination_limit=pagination_limit)

        (
            function_jobs_list_ws,
            meta,
        ) = await self._web_rpc_client.list_function_jobs_with_status(
            user_id=self.user_id,
            product_name=self.product_name,
            filter_by_function_id=filter_by_function_id,
            filter_by_function_job_ids=filter_by_function_job_ids,
            filter_by_function_job_collection_id=filter_by_function_job_collection_id,
            **pagination_kwargs,
        )

        for function_job_wso in function_jobs_list_ws:
            if function_job_wso.outputs is None or (
                function_job_wso.status.status
                not in (
                    RunningState.SUCCESS,
                    RunningState.FAILED,
                )
            ):
                function_job_wso.status = await self.inspect_function_job(
                    function=await self._function_service.get_function(
                        function_id=function_job_wso.function_uid,
                    ),
                    function_job=function_job_wso,
                )

                if function_job_wso.status.status == RunningState.SUCCESS:
                    function_job_wso.outputs = await self.function_job_outputs(
                        function_job=function_job_wso,
                        function=await self._function_service.get_function(
                            function_id=function_job_wso.function_uid,
                        ),
                        stored_job_outputs=None,
                    )
        return function_jobs_list_ws, meta

    async def inspect_function_job(
        self,
        function: RegisteredFunction,
        function_job: RegisteredFunctionJob,
    ) -> FunctionJobStatus:
        """Raises FunctionJobProjectNotRegisteredError if no project is associated with job"""
        stored_job_status = await self._web_rpc_client.get_function_job_status(
            function_job_id=function_job.uid,
            user_id=self.user_id,
            product_name=self.product_name,
        )

        if stored_job_status.status in (RunningState.SUCCESS, RunningState.FAILED):
            return stored_job_status

        status: str
        if function.function_class == FunctionClass.PROJECT and function_job.function_class == FunctionClass.PROJECT:
            if function_job.project_job_id is None:
                status = await _celery_task_status(
                    job_creation_task_id=function_job.job_creation_task_id,
                    task_manager=self._celery_task_manager,
                    user_id=self.user_id,
                    product_name=self.product_name,
                )
            else:
                job_status = await self._job_service.inspect_study_job(
                    job_id=function_job.project_job_id,
                )
                status = job_status.state
        elif (function.function_class == FunctionClass.SOLVER) and (
            function_job.function_class == FunctionClass.SOLVER
        ):
            if function_job.solver_job_id is None:
                status = await _celery_task_status(
                    job_creation_task_id=function_job.job_creation_task_id,
                    task_manager=self._celery_task_manager,
                    user_id=self.user_id,
                    product_name=self.product_name,
                )
            else:
                job_status = await self._job_service.inspect_solver_job(
                    solver_key=function.solver_key,
                    version=function.solver_version,
                    job_id=function_job.solver_job_id,
                )
                status = job_status.state
        else:
            raise UnsupportedFunctionFunctionJobClassCombinationError(
                function_class=function.function_class,
                function_job_class=function_job.function_class,
            )

        new_job_status = FunctionJobStatus(status=status)

        return await self._web_rpc_client.update_function_job_status(
            function_job_id=function_job.uid,
            user_id=self.user_id,
            product_name=self.product_name,
            job_status=new_job_status,
            check_write_permissions=False,
        )

    async def function_job_outputs(  # noqa: PLR0911
        self,
        *,
        function: RegisteredFunction,
        function_job: RegisteredFunctionJob,
        stored_job_outputs: FunctionOutputs | None,
    ) -> FunctionOutputs:
        # pylint: disable=too-many-return-statements

        if stored_job_outputs is not None:
            return stored_job_outputs

        job_status = await self.inspect_function_job(function=function, function_job=function_job)

        if job_status.status != RunningState.SUCCESS:
            return None

        if function.function_class == FunctionClass.PROJECT and function_job.function_class == FunctionClass.PROJECT:
            if function_job.project_job_id is None:
                return None
            try:
                new_outputs = dict(
                    (
                        await self._job_service.get_study_job_outputs(
                            study_id=function.project_id,
                            job_id=function_job.project_job_id,
                        )
                    ).results
                )
            except StudyJobOutputRequestButNotSucceededError:
                return None
        elif function.function_class == FunctionClass.SOLVER and function_job.function_class == FunctionClass.SOLVER:
            if function_job.solver_job_id is None:
                return None
            try:
                new_outputs = dict(
                    (
                        await self._job_service.get_solver_job_outputs(
                            solver_key=function.solver_key,
                            version=function.solver_version,
                            job_id=function_job.solver_job_id,
                            async_pg_engine=self._async_pg_engine,
                        )
                    ).results
                )
            except SolverJobOutputRequestButNotSucceededError:
                return None
        else:
            raise UnsupportedFunctionClassError(function_class=function.function_class)

        return await self._web_rpc_client.update_function_job_outputs(
            function_job_id=function_job.uid,
            user_id=self.user_id,
            product_name=self.product_name,
            outputs=new_outputs,
            check_write_permissions=False,
        )

    async def create_function_job_creation_tasks(
        self,
        *,
        function: RegisteredFunction,
        function_inputs: FunctionInputsList,
        user_identity: Identity,
        pricing_spec: JobPricingSpecification | None,
        job_links: JobLinks,
        parent_project_uuid: ProjectID | None = None,
        parent_node_id: NodeID | None = None,
    ) -> list[RegisteredFunctionJob]:
        inputs = [join_inputs(function.default_inputs, input_) for input_ in function_inputs]

        cached_jobs = await self._web_rpc_client.find_cached_function_jobs(
            user_id=user_identity.user_id,
            product_name=user_identity.product_name,
            function_id=function.uid,
            inputs=TypeAdapter(FunctionInputsList).validate_python(inputs),
            status_filter=[FunctionJobStatus(status=RunningState.SUCCESS)],
        )

        uncached_inputs = [input_ for input_, job in zip(inputs, cached_jobs, strict=False) if job is None]

        pre_registered_function_job_data_list = await self._function_job_service.batch_pre_register_function_jobs(
            function=function,
            job_input_list=[JobInputs(values=_ or {}) for _ in uncached_inputs],
        )

        # run function in celery task
        owner_metadata = ApiServerOwnerMetadata(
            user_id=user_identity.user_id,
            product_name=user_identity.product_name,
            owner=APP_NAME,
        )
        task_uuids = [
            await self._celery_task_manager.submit_task(
                ExecutionMetadata(
                    name="run_function",
                    ephemeral=False,
                    queue=TasksQueue.API_WORKER_QUEUE,
                ),
                owner_metadata=owner_metadata,
                user_identity=user_identity,
                function=function,
                pre_registered_function_job_data=pre_registered_function_job_data,
                pricing_spec=pricing_spec,
                job_links=job_links,
                x_simcore_parent_project_uuid=parent_project_uuid,
                x_simcore_parent_node_id=parent_node_id,
            )
            for pre_registered_function_job_data in pre_registered_function_job_data_list
        ]

        patched_jobs = await self._function_job_service.batch_patch_registered_function_job(
            user_id=user_identity.user_id,
            product_name=user_identity.product_name,
            function_job_patches=[
                FunctionJobPatch(
                    function_class=function.function_class,
                    function_job_id=pre_registered_function_job_data.function_job_id,
                    job_creation_task_id=TaskID(task_uuid),
                    project_job_id=None,
                    solver_job_id=None,
                )
                for task_uuid, pre_registered_function_job_data in zip(
                    task_uuids, pre_registered_function_job_data_list, strict=False
                )
            ],
        )
        patched_jobs_iter = iter(patched_jobs.updated_items)

        def resolve_cached_jobs(job):
            return job if job is not None else next(patched_jobs_iter)

        return [resolve_cached_jobs(job) for job in cached_jobs]

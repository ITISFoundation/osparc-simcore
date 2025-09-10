from dataclasses import dataclass
from typing import Final, overload

import jsonschema
from common_library.exclude import as_dict_exclude_none
from models_library.functions import (
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionJobCollectionID,
    FunctionJobID,
    FunctionSchemaClass,
    ProjectFunctionJob,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobPatch,
    RegisteredProjectFunctionJobPatch,
    RegisteredSolverFunctionJobPatch,
    SolverFunctionJob,
    SolverJobID,
    TaskID,
)
from models_library.functions_errors import (
    FunctionInputsValidationError,
    UnsupportedFunctionClassError,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rest_pagination import PageMetaInfoLimitOffset, PageOffsetInt
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID
from pydantic import ValidationError
from servicelib.celery.models import TaskUUID
from servicelib.celery.task_manager import TaskManager
from simcore_service_api_server._service_functions import FunctionService
from simcore_service_api_server.services_rpc.storage import StorageService

from ._service_jobs import JobService
from .api.routes.tasks import _get_task_filter
from .models.api_resources import JobLinks
from .models.domain.functions import PreRegisteredFunctionJobData
from .models.schemas.jobs import JobInputs, JobPricingSpecification
from .services_http.webserver import AuthSession
from .services_rpc.wb_api_server import WbApiRpcClient

_JOB_CREATION_TASK_STATUS_PREFIX: Final[str] = "JOB_CREATION_TASK_STATUS_"
_JOB_CREATION_TASK_NOT_YET_SCHEDULED_STATUS: Final[str] = (
    f"{_JOB_CREATION_TASK_STATUS_PREFIX}NOT_YET_SCHEDULED"
)


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
) -> str:
    if job_creation_task_id is None:
        return _JOB_CREATION_TASK_NOT_YET_SCHEDULED_STATUS
    task_filter = _get_task_filter(user_id, product_name)
    task_status = await task_manager.get_task_status(
        task_uuid=TaskUUID(job_creation_task_id), task_filter=task_filter
    )
    return f"{_JOB_CREATION_TASK_STATUS_PREFIX}{task_status.task_state}"


@dataclass(frozen=True, kw_only=True)
class FunctionJobService:
    user_id: UserID
    product_name: ProductName
    _web_rpc_client: WbApiRpcClient
    _storage_client: StorageService
    _job_service: JobService
    _function_service: FunctionService
    _webserver_api: AuthSession

    async def list_function_jobs(
        self,
        *,
        filter_by_function_id: FunctionID | None = None,
        filter_by_function_job_ids: list[FunctionJobID] | None = None,
        filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
        """Lists all function jobs for a user with pagination"""

        pagination_kwargs = as_dict_exclude_none(
            pagination_offset=pagination_offset, pagination_limit=pagination_limit
        )

        return await self._web_rpc_client.list_function_jobs(
            user_id=self.user_id,
            product_name=self.product_name,
            filter_by_function_id=filter_by_function_id,
            filter_by_function_job_ids=filter_by_function_job_ids,
            filter_by_function_job_collection_id=filter_by_function_job_collection_id,
            **pagination_kwargs,
        )

    async def validate_function_inputs(
        self, *, function_id: FunctionID, inputs: FunctionInputs
    ) -> tuple[bool, str]:
        function = await self._web_rpc_client.get_function(
            function_id=function_id,
            user_id=self.user_id,
            product_name=self.product_name,
        )

        if (
            function.input_schema is None
            or function.input_schema.schema_content is None
        ):
            return True, "No input schema defined for this function"

        if function.input_schema.schema_class == FunctionSchemaClass.json_schema:
            try:
                jsonschema.validate(
                    instance=inputs, schema=function.input_schema.schema_content
                )
            except ValidationError as err:
                return False, str(err)
            return True, "Inputs are valid"

        return (
            False,
            f"Unsupported function schema class {function.input_schema.schema_class}",
        )

    async def create_function_job_inputs(  # pylint: disable=no-self-use
        self,
        *,
        function: RegisteredFunction,
        function_inputs: FunctionInputs,
    ) -> JobInputs:
        joined_inputs = join_inputs(
            function.default_inputs,
            function_inputs,
        )
        return JobInputs(
            values=joined_inputs or {},
        )

    async def pre_register_function_job(
        self,
        *,
        function: RegisteredFunction,
        job_inputs: JobInputs,
    ) -> PreRegisteredFunctionJobData:

        if function.input_schema is not None:
            is_valid, validation_str = await self.validate_function_inputs(
                function_id=function.uid,
                inputs=job_inputs.values,
            )
            if not is_valid:
                raise FunctionInputsValidationError(error=validation_str)

        if function.function_class == FunctionClass.PROJECT:
            job = await self._web_rpc_client.register_function_job(
                function_job=ProjectFunctionJob(
                    function_uid=function.uid,
                    title=f"Function job of function {function.uid}",
                    description=function.description,
                    inputs=job_inputs.values,
                    outputs=None,
                    project_job_id=None,
                    job_creation_task_id=None,
                ),
                user_id=self.user_id,
                product_name=self.product_name,
            )

        elif function.function_class == FunctionClass.SOLVER:
            job = await self._web_rpc_client.register_function_job(
                function_job=SolverFunctionJob(
                    function_uid=function.uid,
                    title=f"Function job of function {function.uid}",
                    description=function.description,
                    inputs=job_inputs.values,
                    outputs=None,
                    solver_job_id=None,
                    job_creation_task_id=None,
                ),
                user_id=self.user_id,
                product_name=self.product_name,
            )
        else:
            raise UnsupportedFunctionClassError(
                function_class=function.function_class,
            )

        return PreRegisteredFunctionJobData(
            function_job_id=job.uid,
            job_inputs=job_inputs,
        )

    @overload
    async def patch_registered_function_job(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_id: FunctionJobID,
        function_class: FunctionClass,
        job_creation_task_id: TaskID | None,
    ) -> RegisteredFunctionJob: ...

    @overload
    async def patch_registered_function_job(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_id: FunctionJobID,
        function_class: FunctionClass,
        job_creation_task_id: TaskID | None,
        project_job_id: ProjectID | None,
    ) -> RegisteredFunctionJob: ...

    @overload
    async def patch_registered_function_job(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_id: FunctionJobID,
        function_class: FunctionClass,
        job_creation_task_id: TaskID | None,
        solver_job_id: SolverJobID | None,
    ) -> RegisteredFunctionJob: ...

    async def patch_registered_function_job(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_id: FunctionJobID,
        function_class: FunctionClass,
        job_creation_task_id: TaskID | None,
        project_job_id: ProjectID | None = None,
        solver_job_id: SolverJobID | None = None,
    ) -> RegisteredFunctionJob:
        # Only allow one of project_job_id or solver_job_id depending on function_class
        patch: RegisteredFunctionJobPatch
        if function_class == FunctionClass.PROJECT:
            patch = RegisteredProjectFunctionJobPatch(
                title=None,
                description=None,
                inputs=None,
                outputs=None,
                job_creation_task_id=job_creation_task_id,
                project_job_id=project_job_id,
            )
        elif function_class == FunctionClass.SOLVER:
            patch = RegisteredSolverFunctionJobPatch(
                title=None,
                description=None,
                inputs=None,
                outputs=None,
                job_creation_task_id=job_creation_task_id,
                solver_job_id=solver_job_id,
            )
        else:
            raise UnsupportedFunctionClassError(
                function_class=function_class,
            )
        return await self._web_rpc_client.patch_registered_function_job(
            user_id=user_id,
            product_name=product_name,
            function_job_id=function_job_id,
            registered_function_job_patch=patch,
        )

    async def run_function(
        self,
        *,
        function: RegisteredFunction,
        pre_registered_function_job_data: PreRegisteredFunctionJobData,
        pricing_spec: JobPricingSpecification | None,
        job_links: JobLinks,
        x_simcore_parent_project_uuid: NodeID | None,
        x_simcore_parent_node_id: NodeID | None,
    ) -> RegisteredFunctionJob:
        """N.B. this function does not check access rights. Use get_cached_function_job for that"""

        if function.function_class == FunctionClass.PROJECT:
            study_job = await self._job_service.create_studies_job(
                study_id=function.project_id,
                job_inputs=pre_registered_function_job_data.job_inputs,
                hidden=True,
                job_links=job_links,
                x_simcore_parent_project_uuid=x_simcore_parent_project_uuid,
                x_simcore_parent_node_id=x_simcore_parent_node_id,
            )
            await self._job_service.start_study_job(
                study_id=function.project_id,
                job_id=study_job.id,
                pricing_spec=pricing_spec,
            )
            return await self.patch_registered_function_job(
                user_id=self.user_id,
                product_name=self.product_name,
                function_job_id=pre_registered_function_job_data.function_job_id,
                function_class=FunctionClass.PROJECT,
                job_creation_task_id=None,
                project_job_id=study_job.id,
            )

        if function.function_class == FunctionClass.SOLVER:
            solver_job = await self._job_service.create_solver_job(
                solver_key=function.solver_key,
                version=function.solver_version,
                inputs=pre_registered_function_job_data.job_inputs,
                job_links=job_links,
                hidden=True,
                x_simcore_parent_project_uuid=x_simcore_parent_project_uuid,
                x_simcore_parent_node_id=x_simcore_parent_node_id,
            )
            await self._job_service.start_solver_job(
                solver_key=function.solver_key,
                version=function.solver_version,
                job_id=solver_job.id,
                pricing_spec=pricing_spec,
            )
            return await self.patch_registered_function_job(
                user_id=self.user_id,
                product_name=self.product_name,
                function_job_id=pre_registered_function_job_data.function_job_id,
                function_class=FunctionClass.SOLVER,
                job_creation_task_id=None,
                solver_job_id=solver_job.id,
            )

        raise UnsupportedFunctionClassError(
            function_class=function.function_class,
        )

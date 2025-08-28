from dataclasses import dataclass
from typing import overload

import jsonschema
from common_library.exclude import as_dict_exclude_none
from models_library.functions import (
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobID,
    FunctionJobStatus,
    FunctionSchemaClass,
    ProjectFunctionJob,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
    RegisteredFunctionJobPatch,
    RegisteredProjectFunctionJobPatch,
    RegisteredSolverFunctionJobPatch,
    SolverFunctionJob,
    SolverJobID,
    TaskID,
)
from models_library.functions_errors import (
    FunctionExecuteAccessDeniedError,
    FunctionInputsValidationError,
    FunctionsExecuteApiAccessDeniedError,
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
from pydantic import ValidationError

from ._service_jobs import JobService
from .exceptions.function_errors import (
    FunctionJobCacheNotFoundError,
    FunctionJobProjectMissingError,
)
from .models.api_resources import JobLinks
from .models.domain.functions import PreRegisteredFunctionJobData
from .models.schemas.jobs import (
    JobInputs,
    JobPricingSpecification,
)
from .services_rpc.wb_api_server import WbApiRpcClient


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


@dataclass(frozen=True, kw_only=True)
class FunctionJobService:
    user_id: UserID
    product_name: ProductName
    _web_rpc_client: WbApiRpcClient
    _job_service: JobService

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

    async def inspect_function_job(
        self, function: RegisteredFunction, function_job: RegisteredFunctionJob
    ) -> FunctionJobStatus:
        """Raises FunctionJobProjectNotRegisteredError if no project is associated with job"""
        stored_job_status = await self._web_rpc_client.get_function_job_status(
            function_job_id=function_job.uid,
            user_id=self.user_id,
            product_name=self.product_name,
        )

        if stored_job_status.status in (RunningState.SUCCESS, RunningState.FAILED):
            return stored_job_status

        if (
            function.function_class == FunctionClass.PROJECT
            and function_job.function_class == FunctionClass.PROJECT
        ):
            if function_job.project_job_id is None:
                raise FunctionJobProjectMissingError()
            job_status = await self._job_service.inspect_study_job(
                job_id=function_job.project_job_id,
            )
        elif (function.function_class == FunctionClass.SOLVER) and (
            function_job.function_class == FunctionClass.SOLVER
        ):
            if function_job.solver_job_id is None:
                raise FunctionJobProjectMissingError()
            job_status = await self._job_service.inspect_solver_job(
                solver_key=function.solver_key,
                version=function.solver_version,
                job_id=function_job.solver_job_id,
            )
        else:
            raise UnsupportedFunctionFunctionJobClassCombinationError(
                function_class=function.function_class,
                function_job_class=function_job.function_class,
            )

        new_job_status = FunctionJobStatus(status=job_status.state)

        return await self._web_rpc_client.update_function_job_status(
            function_job_id=function_job.uid,
            user_id=self.user_id,
            product_name=self.product_name,
            job_status=new_job_status,
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

    async def get_cached_function_job(
        self,
        *,
        function: RegisteredFunction,
        job_inputs: JobInputs,
    ) -> RegisteredFunctionJob:
        """
        N.B. this function checks access rights

        raises FunctionsExecuteApiAccessDeniedError if user cannot execute functions
        raises FunctionJobCacheNotFoundError if no cached job is found

        """

        user_api_access_rights = (
            await self._web_rpc_client.get_functions_user_api_access_rights(
                user_id=self.user_id, product_name=self.product_name
            )
        )
        if not user_api_access_rights.execute_functions:
            raise FunctionsExecuteApiAccessDeniedError(
                user_id=self.user_id,
                function_id=function.uid,
            )

        user_permissions = await self._web_rpc_client.get_function_user_permissions(
            function_id=function.uid,
            user_id=self.user_id,
            product_name=self.product_name,
        )
        if not user_permissions.execute:
            raise FunctionExecuteAccessDeniedError(
                user_id=self.user_id,
                function_id=function.uid,
            )

        if cached_function_jobs := await self._web_rpc_client.find_cached_function_jobs(
            function_id=function.uid,
            inputs=job_inputs.values,
            user_id=self.user_id,
            product_name=self.product_name,
        ):
            for cached_function_job in cached_function_jobs:
                job_status = await self.inspect_function_job(
                    function=function,
                    function_job=cached_function_job,
                )
                if job_status.status == RunningState.SUCCESS:
                    return cached_function_job

        raise FunctionJobCacheNotFoundError()

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
        job_creation_task_id: TaskID | None,
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
                job_creation_task_id=job_creation_task_id,
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
                job_creation_task_id=job_creation_task_id,
                solver_job_id=solver_job.id,
            )

        raise UnsupportedFunctionClassError(
            function_class=function.function_class,
        )

    async def map_function(
        self,
        *,
        job_creation_task_id: TaskID | None,
        function: RegisteredFunction,
        pre_registered_function_job_data_list: list[PreRegisteredFunctionJobData],
        job_links: JobLinks,
        pricing_spec: JobPricingSpecification | None,
        x_simcore_parent_project_uuid: ProjectID | None,
        x_simcore_parent_node_id: NodeID | None,
    ) -> RegisteredFunctionJobCollection:

        function_jobs = [
            await self.run_function(
                job_creation_task_id=job_creation_task_id,
                function=function,
                pre_registered_function_job_data=data,
                pricing_spec=pricing_spec,
                job_links=job_links,
                x_simcore_parent_project_uuid=x_simcore_parent_project_uuid,
                x_simcore_parent_node_id=x_simcore_parent_node_id,
            )
            for data in pre_registered_function_job_data_list
        ]

        function_job_collection_description = f"Function job collection of map of function {function.uid} with {len(pre_registered_function_job_data_list)} inputs"
        return await self._web_rpc_client.register_function_job_collection(
            function_job_collection=FunctionJobCollection(
                title="Function job collection of function map",
                description=function_job_collection_description,
                job_ids=[function_job.uid for function_job in function_jobs],
            ),
            user_id=self.user_id,
            product_name=self.product_name,
        )

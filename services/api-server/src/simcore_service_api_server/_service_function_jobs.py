from dataclasses import dataclass
from typing import Annotated

import jsonschema
from common_library.exclude import as_dict_exclude_none
from models_library.functions import (
    FunctionClass,
    FunctionID,
    FunctionInputs,
    FunctionJobCollectionID,
    FunctionJobID,
    FunctionJobList,
    FunctionSchemaClass,
    ProjectFunctionJob,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredProjectFunctionJobPatch,
    RegisteredProjectFunctionJobPatchInput,
    RegisteredProjectFunctionJobPatchInputList,
    RegisteredSolverFunctionJobPatch,
    RegisteredSolverFunctionJobPatchInput,
    RegisteredSolverFunctionJobPatchInputList,
    SolverFunctionJob,
)
from models_library.functions_errors import (
    FunctionInputsValidationError,
    UnsupportedFunctionClassError,
)
from models_library.products import ProductName
from models_library.projects_nodes_io import NodeID
from models_library.rest_pagination import PageMetaInfoLimitOffset, PageOffsetInt
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID
from pydantic import Field, TypeAdapter, ValidationError, validate_call
from simcore_service_api_server._service_functions import FunctionService
from simcore_service_api_server.services_rpc.storage import StorageService

from ._service_jobs import JobService
from .models.api_resources import JobLinks
from .models.domain.functions import (
    FunctionJobPatch,
    PreRegisteredFunctionJobData,
)
from .models.schemas.jobs import JobInputs, JobPricingSpecification
from .services_http.webserver import AuthSession
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

    async def validate_function_inputs(  # pylint: disable=no-self-use
        self, *, function: RegisteredFunction, job_inputs: list[JobInputs]
    ) -> tuple[bool, str]:

        if (
            function.input_schema is None
            or function.input_schema.schema_content is None
        ):
            return True, "No input schema defined for this function"

        if function.input_schema.schema_class == FunctionSchemaClass.json_schema:
            try:
                for input_ in job_inputs:
                    jsonschema.validate(
                        instance=input_.values,
                        schema=function.input_schema.schema_content,
                    )
            except ValidationError as err:
                return False, str(err)
            return True, "Inputs are valid"

        return (
            False,
            f"Unsupported function schema class {function.input_schema.schema_class}",
        )

    def create_function_job_inputs(  # pylint: disable=no-self-use
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
        job_inputs: list[JobInputs],
    ) -> list[PreRegisteredFunctionJobData]:

        if function.input_schema is not None:
            is_valid, validation_str = await self.validate_function_inputs(
                function=function,
                job_inputs=job_inputs,
            )
            if not is_valid:
                raise FunctionInputsValidationError(error=validation_str)

        function_jobs: list[ProjectFunctionJob | SolverFunctionJob]
        if function.function_class == FunctionClass.PROJECT:
            function_jobs = [
                ProjectFunctionJob(
                    function_uid=function.uid,
                    title=f"Function job of function {function.uid}",
                    description=function.description,
                    inputs=input_.values,
                    outputs=None,
                    project_job_id=None,
                    job_creation_task_id=None,
                )
                for input_ in job_inputs
            ]
            jobs = await self._web_rpc_client.register_function_job(
                function_jobs=TypeAdapter(FunctionJobList).validate_python(
                    function_jobs
                ),
                user_id=self.user_id,
                product_name=self.product_name,
            )

        elif function.function_class == FunctionClass.SOLVER:
            function_jobs = [
                SolverFunctionJob(
                    function_uid=function.uid,
                    title=f"Function job of function {function.uid}",
                    description=function.description,
                    inputs=input_.values,
                    outputs=None,
                    solver_job_id=None,
                    job_creation_task_id=None,
                )
                for input_ in job_inputs
            ]
            jobs = await self._web_rpc_client.register_function_job(
                function_jobs=TypeAdapter(FunctionJobList).validate_python(
                    function_jobs
                ),
                user_id=self.user_id,
                product_name=self.product_name,
            )
        else:
            raise UnsupportedFunctionClassError(
                function_class=function.function_class,
            )

        return [
            PreRegisteredFunctionJobData(
                function_job_id=job.uid,
                job_inputs=input_,
            )
            for job, input_ in zip(jobs, job_inputs)
        ]

    @validate_call
    async def patch_registered_function_job(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        patches: Annotated[
            list[FunctionJobPatch],
            Field(max_length=50, min_length=1),
        ],
    ) -> list[RegisteredFunctionJob]:
        patch_inputs: list[
            RegisteredProjectFunctionJobPatchInput
            | RegisteredSolverFunctionJobPatchInput
        ] = []
        for patch in patches:
            if patch.function_class == FunctionClass.PROJECT:
                patch_inputs.append(
                    RegisteredProjectFunctionJobPatchInput(
                        uid=patch.function_job_id,
                        patch=RegisteredProjectFunctionJobPatch(
                            title=None,
                            description=None,
                            inputs=None,
                            outputs=None,
                            job_creation_task_id=patch.job_creation_task_id,
                            project_job_id=patch.project_job_id,
                        ),
                    )
                )
            elif patch.function_class == FunctionClass.SOLVER:
                patch_inputs.append(
                    RegisteredSolverFunctionJobPatchInput(
                        uid=patch.function_job_id,
                        patch=RegisteredSolverFunctionJobPatch(
                            title=None,
                            description=None,
                            inputs=None,
                            outputs=None,
                            job_creation_task_id=patch.job_creation_task_id,
                            solver_job_id=patch.solver_job_id,
                        ),
                    )
                )
            else:
                raise UnsupportedFunctionClassError(
                    function_class=patch.function_class,
                )

        return await self._web_rpc_client.patch_registered_function_job(
            user_id=user_id,
            product_name=product_name,
            registered_function_job_patch_inputs=TypeAdapter(
                RegisteredProjectFunctionJobPatchInputList
                | RegisteredSolverFunctionJobPatchInputList
            ).validate_python(patch_inputs),
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
            registered_jobs = await self.patch_registered_function_job(
                user_id=self.user_id,
                product_name=self.product_name,
                patches=[
                    FunctionJobPatch(
                        function_class=FunctionClass.PROJECT,
                        function_job_id=pre_registered_function_job_data.function_job_id,
                        job_creation_task_id=None,
                        project_job_id=study_job.id,
                    )
                ],
            )
            assert len(registered_jobs) == 1
            return registered_jobs[0]

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
            registered_jobs = await self.patch_registered_function_job(
                user_id=self.user_id,
                product_name=self.product_name,
                patches=[
                    FunctionJobPatch(
                        function_class=FunctionClass.SOLVER,
                        function_job_id=pre_registered_function_job_data.function_job_id,
                        job_creation_task_id=None,
                        solver_job_id=solver_job.id,
                    )
                ],
            )
            assert len(registered_jobs) == 1
            return registered_jobs[0]

        raise UnsupportedFunctionClassError(
            function_class=function.function_class,
        )

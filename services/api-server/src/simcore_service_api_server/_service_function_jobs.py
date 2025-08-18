from dataclasses import dataclass

from common_library.exclude import as_dict_exclude_none
from models_library.functions import (
    FunctionClass,
    FunctionID,
    FunctionJobCollectionID,
    FunctionJobID,
    FunctionJobStatus,
    RegisteredFunction,
    RegisteredFunctionJob,
)
from models_library.functions_errors import (
    UnsupportedFunctionFunctionJobClassCombinationError,
)
from models_library.products import ProductName
from models_library.projects_state import RunningState
from models_library.rest_pagination import PageMetaInfoLimitOffset, PageOffsetInt
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID

from ._service_jobs import JobService
from .services_rpc.wb_api_server import WbApiRpcClient


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

    async def inspect_function_job(
        self, function: RegisteredFunction, function_job: RegisteredFunctionJob
    ) -> FunctionJobStatus:

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
            job_status = await self._job_service.inspect_study_job(
                job_id=function_job.project_job_id,
            )
        elif (function.function_class == FunctionClass.SOLVER) and (
            function_job.function_class == FunctionClass.SOLVER
        ):
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

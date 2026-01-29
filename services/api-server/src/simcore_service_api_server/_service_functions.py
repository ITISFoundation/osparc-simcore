# pylint: disable=no-self-use

from collections.abc import Callable
from dataclasses import dataclass

from common_library.exclude import as_dict_exclude_none
from models_library.functions import FunctionClass, FunctionID, RegisteredFunction
from models_library.functions_errors import (
    FunctionExecuteAccessDeniedError,
    FunctionsExecuteApiAccessDeniedError,
    UnsupportedFunctionClassError,
)
from models_library.products import ProductName
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID

from .models.api_resources import JobLinks
from .services_http.solver_job_models_converters import (
    get_solver_job_rest_interface_links,
)
from .services_http.study_job_models_converters import (
    get_study_job_rest_interface_links,
)
from .services_rpc.wb_api_server import WbApiRpcClient

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


@dataclass(frozen=True, kw_only=True)
class FunctionService:
    user_id: UserID
    product_name: ProductName
    _web_rpc_client: WbApiRpcClient

    async def list_functions(
        self,
        *,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
        """Lists all functions for a user with pagination"""

        pagination_kwargs = as_dict_exclude_none(pagination_offset=pagination_offset, pagination_limit=pagination_limit)

        return await self._web_rpc_client.list_functions(
            user_id=self.user_id,
            product_name=self.product_name,
            **pagination_kwargs,
        )

    async def get_function_job_links(self, function: RegisteredFunction, url_for: Callable) -> JobLinks:
        if function.function_class == FunctionClass.SOLVER:
            return get_solver_job_rest_interface_links(
                url_for=url_for,
                solver_key=function.solver_key,
                version=function.solver_version,
            )
        if function.function_class == FunctionClass.PROJECT:
            return get_study_job_rest_interface_links(
                url_for=url_for,
                study_id=function.project_id,
            )
        raise UnsupportedFunctionClassError(
            function_class=function.function_class,
        )

    async def get_function(self, function_id: FunctionID) -> RegisteredFunction:
        """Fetch a function by its ID"""
        return await self._web_rpc_client.get_function(
            user_id=self.user_id,
            product_name=self.product_name,
            function_id=function_id,
        )

    async def check_execute_function_permission(
        self,
        *,
        function: RegisteredFunction,
    ) -> None:
        """
        Check execute permissions for a user on a function

        raises FunctionsExecuteApiAccessDeniedError if user cannot execute functions via the functions API
        raises FunctionExecuteAccessDeniedError if user cannot execute this functions
        """

        user_api_access_rights = await self._web_rpc_client.get_functions_user_api_access_rights(
            user_id=self.user_id, product_name=self.product_name
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

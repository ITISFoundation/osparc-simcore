"""Functions RPC API subclient."""

from typing import Literal, cast

from models_library.api_schemas_webserver.functions import (
    Function,
    FunctionID,
    FunctionInputs,
    FunctionInputSchema,
    FunctionJob,
    FunctionJobCollection,
    FunctionJobCollectionID,
    FunctionJobCollectionsListFilters,
    FunctionJobID,
    FunctionOutputSchema,
    RegisteredFunction,
    RegisteredFunctionJob,
    RegisteredFunctionJobCollection,
)
from models_library.functions import (
    FunctionClass,
    FunctionGroupAccessRights,
    FunctionJobStatus,
    FunctionOutputs,
    FunctionUserAccessRights,
    FunctionUserApiAccessRights,
    RegisteredFunctionJobPatch,
    RegisteredFunctionJobWithStatus,
)
from models_library.products import ProductName
from models_library.rest_ordering import OrderBy
from models_library.rest_pagination import PageMetaInfoLimitOffset
from models_library.users import UserID

from ._base import BaseRpcApi


class FunctionsRpcApi(BaseRpcApi):
    """RPC client for function-related operations."""

    # pylint: disable=too-many-public-methods

    async def register_function(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function: Function,
    ) -> RegisteredFunction:
        """Register a function."""
        return cast(
            RegisteredFunction,
            await self._request(
                "register_function",
                product_name=product_name,
                user_id=user_id,
                function=function,
            ),
        )

    async def get_function(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_id: FunctionID,
    ) -> RegisteredFunction:
        """Get a function by ID."""
        return cast(
            RegisteredFunction,
            await self._request(
                "get_function",
                product_name=product_name,
                user_id=user_id,
                function_id=function_id,
            ),
        )

    async def get_function_input_schema(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_id: FunctionID,
    ) -> FunctionInputSchema:
        """Get function input schema."""
        return cast(
            FunctionInputSchema,
            await self._request(
                "get_function_input_schema",
                product_name=product_name,
                user_id=user_id,
                function_id=function_id,
            ),
        )

    async def get_function_output_schema(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_id: FunctionID,
    ) -> FunctionOutputSchema:
        """Get function output schema."""
        return cast(
            FunctionOutputSchema,
            await self._request(
                "get_function_output_schema",
                product_name=product_name,
                user_id=user_id,
                function_id=function_id,
            ),
        )

    async def delete_function(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_id: FunctionID,
    ) -> None:
        """Delete a function."""
        await self._request(
            "delete_function",
            product_name=product_name,
            user_id=user_id,
            function_id=function_id,
        )

    async def list_functions(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        pagination_offset: int,
        pagination_limit: int,
        order_by: OrderBy | None = None,
        filter_by_function_class: FunctionClass | None = None,
        search_by_function_title: str | None = None,
        search_by_multi_columns: str | None = None,
    ) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
        """List available functions."""
        return cast(
            tuple[list[RegisteredFunction], PageMetaInfoLimitOffset],
            await self._request(
                "list_functions",
                product_name=product_name,
                user_id=user_id,
                pagination_offset=pagination_offset,
                pagination_limit=pagination_limit,
                order_by=order_by,
                filter_by_function_class=filter_by_function_class,
                search_by_function_title=search_by_function_title,
                search_by_multi_columns=search_by_multi_columns,
            ),
        )

    async def list_function_jobs(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        pagination_limit: int,
        pagination_offset: int,
        filter_by_function_id: FunctionID | None = None,
        filter_by_function_job_ids: list[FunctionJobID] | None = None,
        filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
    ) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
        """List function jobs."""
        return cast(
            tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset],
            await self._request(
                "list_function_jobs",
                product_name=product_name,
                user_id=user_id,
                pagination_offset=pagination_offset,
                pagination_limit=pagination_limit,
                filter_by_function_id=filter_by_function_id,
                filter_by_function_job_ids=filter_by_function_job_ids,
                filter_by_function_job_collection_id=filter_by_function_job_collection_id,
            ),
        )

    async def list_function_jobs_with_status(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        pagination_offset: int,
        pagination_limit: int,
        filter_by_function_id: FunctionID | None = None,
        filter_by_function_job_ids: list[FunctionJobID] | None = None,
        filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
    ) -> tuple[list[RegisteredFunctionJobWithStatus], PageMetaInfoLimitOffset]:
        """List function jobs with status."""
        return cast(
            tuple[list[RegisteredFunctionJobWithStatus], PageMetaInfoLimitOffset],
            await self._request(
                "list_function_jobs_with_status",
                product_name=product_name,
                user_id=user_id,
                pagination_offset=pagination_offset,
                pagination_limit=pagination_limit,
                filter_by_function_id=filter_by_function_id,
                filter_by_function_job_ids=filter_by_function_job_ids,
                filter_by_function_job_collection_id=filter_by_function_job_collection_id,
            ),
        )

    async def list_function_job_collections(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        pagination_limit: int,
        pagination_offset: int,
        filters: FunctionJobCollectionsListFilters | None = None,
    ) -> tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset]:
        """List function job collections."""
        return cast(
            tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset],
            await self._request(
                "list_function_job_collections",
                product_name=product_name,
                user_id=user_id,
                pagination_offset=pagination_offset,
                pagination_limit=pagination_limit,
                filters=filters,
            ),
        )

    async def update_function_title(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_id: FunctionID,
        title: str,
    ) -> RegisteredFunction:
        """Update function title."""
        return cast(
            RegisteredFunction,
            await self._request(
                "update_function_title",
                product_name=product_name,
                user_id=user_id,
                function_id=function_id,
                title=title,
            ),
        )

    async def update_function_description(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_id: FunctionID,
        description: str,
    ) -> RegisteredFunction:
        """Update function description."""
        return cast(
            RegisteredFunction,
            await self._request(
                "update_function_description",
                product_name=product_name,
                user_id=user_id,
                function_id=function_id,
                description=description,
            ),
        )

    async def run_function(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_id: FunctionID,
        inputs: FunctionInputs,
    ) -> RegisteredFunctionJob:
        """Run a function."""
        return cast(
            RegisteredFunctionJob,
            await self._request(
                "run_function",
                product_name=product_name,
                user_id=user_id,
                function_id=function_id,
                inputs=inputs,
            ),
        )

    async def register_function_job(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job: FunctionJob,
    ) -> RegisteredFunctionJob:
        """Register a function job."""
        return cast(
            RegisteredFunctionJob,
            await self._request(
                "register_function_job",
                product_name=product_name,
                user_id=user_id,
                function_job=function_job,
            ),
        )

    async def patch_registered_function_job(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_uuid: FunctionJobID,
        registered_function_job_patch: RegisteredFunctionJobPatch,
    ) -> RegisteredFunctionJob:
        """Patch a registered function job."""
        return cast(
            RegisteredFunctionJob,
            await self._request(
                "patch_registered_function_job",
                product_name=product_name,
                user_id=user_id,
                function_job_uuid=function_job_uuid,
                registered_function_job_patch=registered_function_job_patch,
            ),
        )

    async def get_function_job(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_id: FunctionJobID,
    ) -> RegisteredFunctionJob:
        """Get a function job."""
        return cast(
            RegisteredFunctionJob,
            await self._request(
                "get_function_job",
                product_name=product_name,
                user_id=user_id,
                function_job_id=function_job_id,
            ),
        )

    async def get_function_job_status(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_id: FunctionJobID,
    ) -> FunctionJobStatus:
        """Get function job status."""
        return cast(
            FunctionJobStatus,
            await self._request(
                "get_function_job_status",
                product_name=product_name,
                user_id=user_id,
                function_job_id=function_job_id,
            ),
        )

    async def get_function_job_outputs(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_id: FunctionJobID,
    ) -> FunctionOutputs:
        """Get function job outputs."""
        return cast(
            FunctionOutputs,
            await self._request(
                "get_function_job_outputs",
                product_name=product_name,
                user_id=user_id,
                function_job_id=function_job_id,
            ),
        )

    async def update_function_job_status(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_id: FunctionJobID,
        job_status: FunctionJobStatus,
        check_write_permissions: bool = True,
    ) -> FunctionJobStatus:
        """Update function job status."""
        return cast(
            FunctionJobStatus,
            await self._request(
                "update_function_job_status",
                product_name=product_name,
                user_id=user_id,
                function_job_id=function_job_id,
                job_status=job_status,
                check_write_permissions=check_write_permissions,
            ),
        )

    async def update_function_job_outputs(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_id: FunctionJobID,
        outputs: FunctionOutputs,
        check_write_permissions: bool = True,
    ) -> FunctionOutputs:
        """Update function job outputs."""
        return cast(
            FunctionOutputs,
            await self._request(
                "update_function_job_outputs",
                product_name=product_name,
                user_id=user_id,
                function_job_id=function_job_id,
                outputs=outputs,
                check_write_permissions=check_write_permissions,
            ),
        )

    async def delete_function_job(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_id: FunctionJobID,
    ) -> None:
        """Delete a function job."""
        await self._request(
            "delete_function_job",
            product_name=product_name,
            user_id=user_id,
            function_job_id=function_job_id,
        )

    async def find_cached_function_jobs(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_id: FunctionID,
        inputs: FunctionInputs,
    ) -> list[RegisteredFunctionJob] | None:
        """Find cached function jobs."""
        return cast(
            list[RegisteredFunctionJob] | None,
            await self._request(
                "find_cached_function_jobs",
                product_name=product_name,
                user_id=user_id,
                function_id=function_id,
                inputs=inputs,
            ),
        )

    async def register_function_job_collection(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_collection: FunctionJobCollection,
    ) -> RegisteredFunctionJobCollection:
        """Register a function job collection."""
        return cast(
            RegisteredFunctionJobCollection,
            await self._request(
                "register_function_job_collection",
                product_name=product_name,
                user_id=user_id,
                function_job_collection=function_job_collection,
            ),
        )

    async def get_function_job_collection(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_collection_id: FunctionJobCollectionID,
    ) -> RegisteredFunctionJobCollection:
        """Get a function job collection."""
        return cast(
            RegisteredFunctionJobCollection,
            await self._request(
                "get_function_job_collection",
                product_name=product_name,
                user_id=user_id,
                function_job_collection_id=function_job_collection_id,
            ),
        )

    async def delete_function_job_collection(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_job_collection_id: FunctionJobCollectionID,
    ) -> None:
        """Delete a function job collection."""
        await self._request(
            "delete_function_job_collection",
            product_name=product_name,
            user_id=user_id,
            function_job_collection_id=function_job_collection_id,
        )

    async def get_function_user_permissions(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        function_id: FunctionID,
    ) -> FunctionUserAccessRights:
        """Get function user permissions."""
        return cast(
            FunctionUserAccessRights,
            await self._request(
                "get_function_user_permissions",
                product_name=product_name,
                user_id=user_id,
                function_id=function_id,
            ),
        )

    async def get_functions_user_api_access_rights(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
    ) -> FunctionUserApiAccessRights:
        """Get functions user API access rights."""
        return cast(
            FunctionUserApiAccessRights,
            await self._request(
                "get_functions_user_api_access_rights",
                product_name=product_name,
                user_id=user_id,
            ),
        )

    async def set_group_permissions(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        object_type: Literal["function", "function_job", "function_job_collection"],
        object_ids: list[FunctionID | FunctionJobID | FunctionJobCollectionID],
        permission_group_id: int,
        read: bool | None = None,
        write: bool | None = None,
        execute: bool | None = None,
    ) -> list[
        tuple[
            FunctionID | FunctionJobID | FunctionJobCollectionID,
            FunctionGroupAccessRights,
        ]
    ]:
        """Set group permissions."""
        return cast(
            list[
                tuple[
                    FunctionID | FunctionJobID | FunctionJobCollectionID,
                    FunctionGroupAccessRights,
                ]
            ],
            await self._request(
                "set_group_permissions",
                product_name=product_name,
                user_id=user_id,
                object_type=object_type,
                object_ids=object_ids,
                permission_group_id=permission_group_id,
                read=read,
                write=write,
                execute=execute,
            ),
        )

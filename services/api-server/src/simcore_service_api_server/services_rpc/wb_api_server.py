# pylint: disable=too-many-public-methods

from dataclasses import dataclass
from functools import partial
from typing import cast

from common_library.exclude import as_dict_exclude_none
from fastapi import FastAPI
from fastapi_pagination import create_page
from models_library.api_schemas_api_server.functions import (
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
from models_library.api_schemas_webserver.licensed_items import LicensedItemRpcGetPage
from models_library.functions import (
    FunctionJobStatus,
    FunctionOutputs,
    FunctionUserAccessRights,
    FunctionUserApiAccessRights,
    RegisteredFunctionJobPatch,
    RegisteredFunctionJobWithStatus,
)
from models_library.licenses import LicensedItemID
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc.webserver.projects import (
    ListProjectsMarkedAsJobRpcFilters,
    MetadataFilterItem,
    ProjectJobRpcGet,
)
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CanNotCheckoutNotEnoughAvailableSeatsError,
)
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    CanNotCheckoutServiceIsNotRunningError as _CanNotCheckoutServiceIsNotRunningError,
)
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    LicensedItemCheckoutNotFoundError as _LicensedItemCheckoutNotFoundError,
)
from servicelib.rabbitmq.rpc_interfaces.resource_usage_tracker.errors import (
    NotEnoughAvailableSeatsError,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import (
    ProjectForbiddenRpcError,
    ProjectNotFoundRpcError,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient
from simcore_service_api_server.models.basic_types import NameValueTuple

from ..core.settings import WebServerSettings
from ..exceptions.backend_errors import (
    CanNotCheckoutServiceIsNotRunningError,
    ConfigurationError,
    InsufficientNumberOfSeatsError,
    JobForbiddenAccessError,
    JobNotFoundError,
    LicensedItemCheckoutNotFoundError,
)
from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.api_resources import RelativeResourceName
from ..models.pagination import Page, PaginationParams
from ..models.schemas.model_adapter import (
    LicensedItemCheckoutGet,
    LicensedItemGet,
    LicensedResource,
)

_exception_mapper = partial(service_exception_mapper, service_name="WebApiServer")


def _create_licensed_items_get_page(
    *, licensed_items_page: LicensedItemRpcGetPage, page_params: PaginationParams
) -> Page[LicensedItemGet]:
    page = create_page(
        [
            LicensedItemGet(
                licensed_item_id=elm.licensed_item_id,
                key=elm.key,
                version=elm.version,
                display_name=elm.display_name,
                licensed_resource_type=elm.licensed_resource_type,
                licensed_resources=[
                    LicensedResource.model_validate(res.model_dump())
                    for res in elm.licensed_resources
                ],
                pricing_plan_id=elm.pricing_plan_id,
                is_hidden_on_market=elm.is_hidden_on_market,
                created_at=elm.created_at,
                modified_at=elm.modified_at,
            )
            for elm in licensed_items_page.items
        ],
        total=licensed_items_page.total,
        params=page_params,
    )
    return cast(Page[LicensedItemGet], page)


@dataclass
class WbApiRpcClient(SingletonInAppStateMixin):
    app_state_name = "wb_api_rpc_client"
    _client: RabbitMQRPCClient
    _rpc_client: WebServerRpcClient

    @_exception_mapper(rpc_exception_map={})
    async def get_licensed_items(
        self, *, product_name: ProductName, page_params: PaginationParams
    ) -> Page[LicensedItemGet]:
        licensed_items_page = await self._rpc_client.licenses.get_licensed_items(
            product_name=product_name,
            offset=page_params.offset,
            limit=page_params.limit,
        )
        return _create_licensed_items_get_page(
            licensed_items_page=licensed_items_page, page_params=page_params
        )

    @_exception_mapper(rpc_exception_map={})
    async def get_available_licensed_items_for_wallet(
        self,
        *,
        product_name: ProductName,
        wallet_id: WalletID,
        user_id: UserID,
        page_params: PaginationParams,
    ) -> Page[LicensedItemGet]:
        licensed_items_page = (
            await self._rpc_client.licenses.get_available_licensed_items_for_wallet(
                product_name=product_name,
                wallet_id=wallet_id,
                user_id=user_id,
                offset=page_params.offset,
                limit=page_params.limit,
            )
        )
        return _create_licensed_items_get_page(
            licensed_items_page=licensed_items_page, page_params=page_params
        )

    @_exception_mapper(
        rpc_exception_map={
            NotEnoughAvailableSeatsError: InsufficientNumberOfSeatsError,
            CanNotCheckoutNotEnoughAvailableSeatsError: InsufficientNumberOfSeatsError,
            _CanNotCheckoutServiceIsNotRunningError: CanNotCheckoutServiceIsNotRunningError,
            # NOTE: missing WalletAccessForbiddenError
        }
    )
    async def checkout_licensed_item_for_wallet(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        wallet_id: WalletID,
        licensed_item_id: LicensedItemID,
        num_of_seats: int,
        service_run_id: ServiceRunID,
    ) -> LicensedItemCheckoutGet:
        licensed_item_checkout_get = (
            await self._rpc_client.licenses.checkout_licensed_item_for_wallet(
                product_name=product_name,
                user_id=user_id,
                wallet_id=wallet_id,
                licensed_item_id=licensed_item_id,
                num_of_seats=num_of_seats,
                service_run_id=service_run_id,
            )
        )
        return LicensedItemCheckoutGet(
            licensed_item_checkout_id=licensed_item_checkout_get.licensed_item_checkout_id,
            licensed_item_id=licensed_item_checkout_get.licensed_item_id,
            key=licensed_item_checkout_get.key,
            version=licensed_item_checkout_get.version,
            wallet_id=licensed_item_checkout_get.wallet_id,
            user_id=licensed_item_checkout_get.user_id,
            product_name=licensed_item_checkout_get.product_name,
            started_at=licensed_item_checkout_get.started_at,
            stopped_at=licensed_item_checkout_get.stopped_at,
            num_of_seats=licensed_item_checkout_get.num_of_seats,
        )

    @_exception_mapper(
        rpc_exception_map={
            _LicensedItemCheckoutNotFoundError: LicensedItemCheckoutNotFoundError
        }
    )
    async def release_licensed_item_for_wallet(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        licensed_item_checkout_id: LicensedItemCheckoutID,
    ) -> LicensedItemCheckoutGet:
        licensed_item_checkout_get = (
            await self._rpc_client.licenses.release_licensed_item_for_wallet(
                product_name=product_name,
                user_id=user_id,
                licensed_item_checkout_id=licensed_item_checkout_id,
            )
        )
        return LicensedItemCheckoutGet(
            licensed_item_checkout_id=licensed_item_checkout_get.licensed_item_checkout_id,
            licensed_item_id=licensed_item_checkout_get.licensed_item_id,
            key=licensed_item_checkout_get.key,
            version=licensed_item_checkout_get.version,
            wallet_id=licensed_item_checkout_get.wallet_id,
            user_id=licensed_item_checkout_get.user_id,
            product_name=licensed_item_checkout_get.product_name,
            started_at=licensed_item_checkout_get.started_at,
            stopped_at=licensed_item_checkout_get.stopped_at,
            num_of_seats=licensed_item_checkout_get.num_of_seats,
        )

    async def mark_project_as_job(
        self,
        product_name: ProductName,
        user_id: UserID,
        project_uuid: ProjectID,
        job_parent_resource_name: RelativeResourceName,
        storage_assets_deleted: bool,  # noqa: FBT001
    ):
        await self._rpc_client.projects.mark_project_as_job(
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            job_parent_resource_name=job_parent_resource_name,
            storage_assets_deleted=storage_assets_deleted,
        )

    @_exception_mapper(
        rpc_exception_map={
            ProjectForbiddenRpcError: JobForbiddenAccessError,
            ProjectNotFoundRpcError: JobNotFoundError,
        }
    )
    async def get_project_marked_as_job(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        project_id: ProjectID,
        job_parent_resource_name: RelativeResourceName,
    ) -> ProjectJobRpcGet:
        return await self._rpc_client.projects.get_project_marked_as_job(
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_id,
            job_parent_resource_name=job_parent_resource_name,
        )

    async def list_projects_marked_as_jobs(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        pagination_offset: int = 0,
        pagination_limit: int = 50,
        filter_by_job_parent_resource_name_prefix: str | None,
        filter_any_custom_metadata: list[NameValueTuple] | None,
    ):
        pagination_kwargs = as_dict_exclude_none(
            offset=pagination_offset, limit=pagination_limit
        )

        filters = ListProjectsMarkedAsJobRpcFilters(
            job_parent_resource_name_prefix=filter_by_job_parent_resource_name_prefix,
            any_custom_metadata=(
                [
                    MetadataFilterItem(name=name, pattern=pattern)
                    for name, pattern in filter_any_custom_metadata
                ]
                if filter_any_custom_metadata
                else None
            ),
        )

        return await self._rpc_client.projects.list_projects_marked_as_jobs(
            product_name=product_name,
            user_id=user_id,
            filters=filters,
            **pagination_kwargs,
        )

    async def register_function(
        self, *, user_id: UserID, product_name: ProductName, function: Function
    ) -> RegisteredFunction:
        return await self._rpc_client.functions.register_function(
            function=function,
            user_id=user_id,
            product_name=product_name,
        )

    async def get_function(
        self, *, user_id: UserID, product_name: ProductName, function_id: FunctionID
    ) -> RegisteredFunction:
        return await self._rpc_client.functions.get_function(
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
        )

    async def delete_function(
        self, *, user_id: UserID, product_name: ProductName, function_id: FunctionID
    ) -> None:
        return await self._rpc_client.functions.delete_function(
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
        )

    async def list_functions(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        pagination_offset: PageOffsetInt = 0,
        pagination_limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    ) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:

        return await self._rpc_client.functions.list_functions(
            user_id=user_id,
            product_name=product_name,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
        )

    async def list_function_jobs(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        pagination_offset: PageOffsetInt = 0,
        pagination_limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        filter_by_function_id: FunctionID | None = None,
        filter_by_function_job_ids: list[FunctionJobID] | None = None,
        filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
    ) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
        return await self._rpc_client.functions.list_function_jobs(
            user_id=user_id,
            product_name=product_name,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
            filter_by_function_id=filter_by_function_id,
            filter_by_function_job_ids=filter_by_function_job_ids,
            filter_by_function_job_collection_id=filter_by_function_job_collection_id,
        )

    async def list_function_jobs_with_status(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        pagination_offset: PageOffsetInt = 0,
        pagination_limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        filter_by_function_id: FunctionID | None = None,
        filter_by_function_job_ids: list[FunctionJobID] | None = None,
        filter_by_function_job_collection_id: FunctionJobCollectionID | None = None,
    ) -> tuple[
        list[RegisteredFunctionJobWithStatus],
        PageMetaInfoLimitOffset,
    ]:
        return await self._rpc_client.functions.list_function_jobs_with_status(
            user_id=user_id,
            product_name=product_name,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
            filter_by_function_id=filter_by_function_id,
            filter_by_function_job_ids=filter_by_function_job_ids,
            filter_by_function_job_collection_id=filter_by_function_job_collection_id,
        )

    async def list_function_job_collections(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        pagination_offset: PageOffsetInt = 0,
        pagination_limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        filters: FunctionJobCollectionsListFilters | None = None,
    ) -> tuple[list[RegisteredFunctionJobCollection], PageMetaInfoLimitOffset]:
        return await self._rpc_client.functions.list_function_job_collections(
            user_id=user_id,
            product_name=product_name,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
            filters=filters,
        )

    async def run_function(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_id: FunctionID,
        inputs: FunctionInputs,
    ) -> RegisteredFunctionJob:
        return await self._rpc_client.functions.run_function(
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
            inputs=inputs,
        )

    async def get_function_job(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_id: FunctionJobID,
    ) -> RegisteredFunctionJob:
        return await self._rpc_client.functions.get_function_job(
            user_id=user_id,
            product_name=product_name,
            function_job_id=function_job_id,
        )

    async def update_function_title(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_id: FunctionID,
        title: str,
    ) -> RegisteredFunction:
        return await self._rpc_client.functions.update_function_title(
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
            title=title,
        )

    async def update_function_description(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_id: FunctionID,
        description: str,
    ) -> RegisteredFunction:
        return await self._rpc_client.functions.update_function_description(
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
            description=description,
        )

    async def delete_function_job(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_id: FunctionJobID,
    ) -> None:
        return await self._rpc_client.functions.delete_function_job(
            user_id=user_id,
            product_name=product_name,
            function_job_id=function_job_id,
        )

    async def register_function_job(
        self, *, user_id: UserID, function_job: FunctionJob, product_name: ProductName
    ) -> RegisteredFunctionJob:
        return await self._rpc_client.functions.register_function_job(
            user_id=user_id,
            product_name=product_name,
            function_job=function_job,
        )

    async def patch_registered_function_job(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_id: FunctionJobID,
        registered_function_job_patch: RegisteredFunctionJobPatch,
    ) -> RegisteredFunctionJob:
        return await self._rpc_client.functions.patch_registered_function_job(
            user_id=user_id,
            product_name=product_name,
            function_job_uuid=function_job_id,
            registered_function_job_patch=registered_function_job_patch,
        )

    async def get_function_input_schema(
        self, *, user_id: UserID, product_name: ProductName, function_id: FunctionID
    ) -> FunctionInputSchema:
        return await self._rpc_client.functions.get_function_input_schema(
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
        )

    async def get_function_output_schema(
        self, *, user_id: UserID, product_name: ProductName, function_id: FunctionID
    ) -> FunctionOutputSchema:
        return await self._rpc_client.functions.get_function_output_schema(
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
        )

    async def get_function_job_status(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_id: FunctionJobID,
    ) -> FunctionJobStatus:
        return await self._rpc_client.functions.get_function_job_status(
            user_id=user_id,
            product_name=product_name,
            function_job_id=function_job_id,
        )

    async def get_function_job_outputs(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_id: FunctionJobID,
    ) -> FunctionOutputs:
        return await self._rpc_client.functions.get_function_job_outputs(
            user_id=user_id,
            product_name=product_name,
            function_job_id=function_job_id,
        )

    async def update_function_job_status(
        self,
        *,
        function_job_id: FunctionJobID,
        user_id: UserID,
        product_name: ProductName,
        job_status: FunctionJobStatus,
        check_write_permissions: bool = True,
    ) -> FunctionJobStatus:
        return await self._rpc_client.functions.update_function_job_status(
            function_job_id=function_job_id,
            user_id=user_id,
            product_name=product_name,
            job_status=job_status,
            check_write_permissions=check_write_permissions,
        )

    async def update_function_job_outputs(
        self,
        *,
        function_job_id: FunctionJobID,
        user_id: UserID,
        product_name: ProductName,
        outputs: FunctionOutputs,
        check_write_permissions: bool = True,
    ) -> FunctionOutputs:
        return await self._rpc_client.functions.update_function_job_outputs(
            function_job_id=function_job_id,
            user_id=user_id,
            product_name=product_name,
            outputs=outputs,
            check_write_permissions=check_write_permissions,
        )

    async def find_cached_function_jobs(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_id: FunctionID,
        inputs: FunctionInputs,
    ) -> list[RegisteredFunctionJob] | None:
        return await self._rpc_client.functions.find_cached_function_jobs(
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
            inputs=inputs,
        )

    async def get_function_job_collection(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_collection_id: FunctionJobCollectionID,
    ) -> RegisteredFunctionJobCollection:
        return await self._rpc_client.functions.get_function_job_collection(
            user_id=user_id,
            product_name=product_name,
            function_job_collection_id=function_job_collection_id,
        )

    async def register_function_job_collection(
        self,
        *,
        user_id: UserID,
        function_job_collection: FunctionJobCollection,
        product_name: ProductName,
    ) -> RegisteredFunctionJobCollection:
        return await self._rpc_client.functions.register_function_job_collection(
            user_id=user_id,
            function_job_collection=function_job_collection,
            product_name=product_name,
        )

    async def delete_function_job_collection(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_job_collection_id: FunctionJobCollectionID,
    ) -> None:
        return await self._rpc_client.functions.delete_function_job_collection(
            user_id=user_id,
            product_name=product_name,
            function_job_collection_id=function_job_collection_id,
        )

    async def get_function_user_permissions(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_id: FunctionID,
    ) -> FunctionUserAccessRights:
        return await self._rpc_client.functions.get_function_user_permissions(
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
        )

    async def get_functions_user_api_access_rights(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
    ) -> FunctionUserApiAccessRights:
        return await self._rpc_client.functions.get_functions_user_api_access_rights(
            user_id=user_id,
            product_name=product_name,
        )


def setup(app: FastAPI, rabbitmq_rmp_client: RabbitMQRPCClient):
    webserver_settings: WebServerSettings = app.state.settings.API_SERVER_WEBSERVER
    if not webserver_settings:
        raise ConfigurationError(tip="Webserver settings are not configured")

    wb_api_rpc_client = WbApiRpcClient(
        _client=rabbitmq_rmp_client,
        _rpc_client=WebServerRpcClient(
            rabbitmq_rmp_client, webserver_settings.WEBSERVER_RPC_NAMESPACE
        ),
    )
    wb_api_rpc_client.set_to_app_state(app=app)

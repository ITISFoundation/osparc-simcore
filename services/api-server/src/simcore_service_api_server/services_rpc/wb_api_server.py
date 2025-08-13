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
from servicelib.rabbitmq.rpc_interfaces.webserver import projects as projects_rpc
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import (
    ProjectForbiddenRpcError,
    ProjectNotFoundRpcError,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.functions import (
    functions_rpc_interface,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.licenses.licensed_items import (
    checkout_licensed_item_for_wallet as _checkout_licensed_item_for_wallet,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.licenses.licensed_items import (
    get_available_licensed_items_for_wallet as _get_available_licensed_items_for_wallet,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.licenses.licensed_items import (
    get_licensed_items as _get_licensed_items,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.licenses.licensed_items import (
    release_licensed_item_for_wallet as _release_licensed_item_for_wallet,
)
from simcore_service_api_server.models.basic_types import NameValueTuple

from ..exceptions.backend_errors import (
    CanNotCheckoutServiceIsNotRunningError,
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

    @_exception_mapper(rpc_exception_map={})
    async def get_licensed_items(
        self, *, product_name: ProductName, page_params: PaginationParams
    ) -> Page[LicensedItemGet]:
        licensed_items_page = await _get_licensed_items(
            rabbitmq_rpc_client=self._client,
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
        licensed_items_page = await _get_available_licensed_items_for_wallet(
            rabbitmq_rpc_client=self._client,
            product_name=product_name,
            wallet_id=wallet_id,
            user_id=user_id,
            offset=page_params.offset,
            limit=page_params.limit,
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
        licensed_item_checkout_get = await _checkout_licensed_item_for_wallet(
            self._client,
            product_name=product_name,
            user_id=user_id,
            wallet_id=wallet_id,
            licensed_item_id=licensed_item_id,
            num_of_seats=num_of_seats,
            service_run_id=service_run_id,
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
        licensed_item_checkout_get = await _release_licensed_item_for_wallet(
            self._client,
            product_name=product_name,
            user_id=user_id,
            licensed_item_checkout_id=licensed_item_checkout_id,
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
        storage_data_deleted: bool,
    ):
        await projects_rpc.mark_project_as_job(
            rpc_client=self._client,
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            job_parent_resource_name=job_parent_resource_name,
            storage_data_deleted=storage_data_deleted,
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
        project_uuid: ProjectID,
        job_parent_resource_name: RelativeResourceName,
    ):
        return await projects_rpc.get_project_marked_as_job(
            rpc_client=self._client,
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
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

        return await projects_rpc.list_projects_marked_as_jobs(
            rpc_client=self._client,
            product_name=product_name,
            user_id=user_id,
            filters=filters,
            **pagination_kwargs,
        )

    async def register_function(
        self, *, user_id: UserID, product_name: ProductName, function: Function
    ) -> RegisteredFunction:
        return await functions_rpc_interface.register_function(
            self._client,
            function=function,
            user_id=user_id,
            product_name=product_name,
        )

    async def get_function(
        self, *, user_id: UserID, product_name: ProductName, function_id: FunctionID
    ) -> RegisteredFunction:
        return await functions_rpc_interface.get_function(
            self._client,
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
        )

    async def delete_function(
        self, *, user_id: UserID, product_name: ProductName, function_id: FunctionID
    ) -> None:
        return await functions_rpc_interface.delete_function(
            self._client,
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

        return await functions_rpc_interface.list_functions(
            self._client,
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
    ) -> tuple[list[RegisteredFunctionJob], PageMetaInfoLimitOffset]:
        return await functions_rpc_interface.list_function_jobs(
            self._client,
            user_id=user_id,
            product_name=product_name,
            pagination_offset=pagination_offset,
            pagination_limit=pagination_limit,
            filter_by_function_id=filter_by_function_id,
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
        return await functions_rpc_interface.list_function_job_collections(
            self._client,
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
        return await functions_rpc_interface.run_function(
            self._client,
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
        return await functions_rpc_interface.get_function_job(
            self._client,
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
        return await functions_rpc_interface.update_function_title(
            self._client,
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
        return await functions_rpc_interface.update_function_description(
            self._client,
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
        return await functions_rpc_interface.delete_function_job(
            self._client,
            user_id=user_id,
            product_name=product_name,
            function_job_id=function_job_id,
        )

    async def register_function_job(
        self, *, user_id: UserID, function_job: FunctionJob, product_name: ProductName
    ) -> RegisteredFunctionJob:
        return await functions_rpc_interface.register_function_job(
            self._client,
            user_id=user_id,
            product_name=product_name,
            function_job=function_job,
        )

    async def get_function_input_schema(
        self, *, user_id: UserID, product_name: ProductName, function_id: FunctionID
    ) -> FunctionInputSchema:
        return await functions_rpc_interface.get_function_input_schema(
            self._client,
            user_id=user_id,
            product_name=product_name,
            function_id=function_id,
        )

    async def get_function_output_schema(
        self, *, user_id: UserID, product_name: ProductName, function_id: FunctionID
    ) -> FunctionOutputSchema:
        return await functions_rpc_interface.get_function_output_schema(
            self._client,
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
        return await functions_rpc_interface.get_function_job_status(
            self._client,
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
        return await functions_rpc_interface.get_function_job_outputs(
            self._client,
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
    ) -> FunctionJobStatus:
        return await functions_rpc_interface.update_function_job_status(
            self._client,
            function_job_id=function_job_id,
            user_id=user_id,
            product_name=product_name,
            job_status=job_status,
        )

    async def update_function_job_outputs(
        self,
        *,
        function_job_id: FunctionJobID,
        user_id: UserID,
        product_name: ProductName,
        outputs: FunctionOutputs,
    ) -> FunctionOutputs:
        return await functions_rpc_interface.update_function_job_outputs(
            self._client,
            function_job_id=function_job_id,
            user_id=user_id,
            product_name=product_name,
            outputs=outputs,
        )

    async def find_cached_function_jobs(
        self,
        *,
        user_id: UserID,
        product_name: ProductName,
        function_id: FunctionID,
        inputs: FunctionInputs,
    ) -> list[RegisteredFunctionJob] | None:
        return await functions_rpc_interface.find_cached_function_jobs(
            self._client,
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
        return await functions_rpc_interface.get_function_job_collection(
            self._client,
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
        return await functions_rpc_interface.register_function_job_collection(
            self._client,
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
        return await functions_rpc_interface.delete_function_job_collection(
            self._client,
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
        return await functions_rpc_interface.get_function_user_permissions(
            self._client,
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
        return await functions_rpc_interface.get_functions_user_api_access_rights(
            self._client,
            user_id=user_id,
            product_name=product_name,
        )


def setup(app: FastAPI, rabbitmq_rmp_client: RabbitMQRPCClient):
    wb_api_rpc_client = WbApiRpcClient(_client=rabbitmq_rmp_client)
    wb_api_rpc_client.set_to_app_state(app=app)

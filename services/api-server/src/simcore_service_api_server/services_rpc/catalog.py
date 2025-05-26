from dataclasses import dataclass
from functools import partial

from models_library.api_schemas_catalog.services import (
    LatestServiceGet,
    ServiceGetV2,
    ServiceListFilters,
    ServiceSummary,
)
from models_library.api_schemas_catalog.services_ports import ServicePortGet
from models_library.products import ProductName
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.services_history import ServiceRelease
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import ValidationError
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.catalog import services as catalog_rpc
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)

from ..exceptions.backend_errors import (
    InvalidInputError,
    ProgramOrSolverOrStudyNotFoundError,
    ServiceForbiddenAccessError,
)
from ..exceptions.service_errors_utils import service_exception_mapper

_exception_mapper = partial(service_exception_mapper, service_name="CatalogService")


@dataclass(frozen=True, kw_only=True)
class CatalogService:
    _rpc_client: RabbitMQRPCClient
    user_id: UserID
    product_name: ProductName

    async def list_latest_releases(
        self,
        *,
        pagination_offset: PageOffsetInt = 0,
        pagination_limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        filters: ServiceListFilters | None = None,
    ) -> tuple[list[LatestServiceGet], PageMetaInfoLimitOffset]:

        page = await catalog_rpc.list_services_paginated(
            self._rpc_client,
            product_name=self.product_name,
            user_id=self.user_id,
            offset=pagination_offset,
            limit=pagination_limit,
            filters=filters,
        )
        meta = PageMetaInfoLimitOffset(
            limit=page.meta.limit,
            offset=page.meta.offset,
            total=page.meta.total,
            count=page.meta.count,
        )
        return page.data, meta

    async def list_release_history_latest_first(
        self,
        *,
        filter_by_service_key: ServiceKey,
        pagination_offset: PageOffsetInt = 0,
        pagination_limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    ) -> tuple[list[ServiceRelease], PageMetaInfoLimitOffset]:

        page = await catalog_rpc.list_my_service_history_latest_first(
            self._rpc_client,
            product_name=self.product_name,
            user_id=self.user_id,
            service_key=filter_by_service_key,
            offset=pagination_offset,
            limit=pagination_limit,
        )
        meta = PageMetaInfoLimitOffset(
            limit=page.meta.limit,
            offset=page.meta.offset,
            total=page.meta.total,
            count=page.meta.count,
        )
        return page.data, meta

    async def list_all_services_summaries(
        self,
        *,
        pagination_offset: PageOffsetInt = 0,
        pagination_limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        filters: ServiceListFilters | None = None,
    ) -> tuple[list[ServiceSummary], PageMetaInfoLimitOffset]:
        """Lists all services with pagination, including all versions of each service.

        Returns a lightweight summary view of services for better performance.

        Args:
            pagination_offset: Number of items to skip
            pagination_limit: Maximum number of items to return
            filters: Optional filters to apply

        Returns:
            Tuple containing list of service summaries and pagination metadata
        """
        page = await catalog_rpc.list_all_services_summaries_paginated(
            self._rpc_client,
            product_name=self.product_name,
            user_id=self.user_id,
            offset=pagination_offset,
            limit=pagination_limit,
            filters=filters,
        )
        meta = PageMetaInfoLimitOffset(
            limit=page.meta.limit,
            offset=page.meta.offset,
            total=page.meta.total,
            count=page.meta.count,
        )
        return page.data, meta

    @_exception_mapper(
        rpc_exception_map={
            CatalogItemNotFoundError: ProgramOrSolverOrStudyNotFoundError,
            CatalogForbiddenError: ServiceForbiddenAccessError,
            ValidationError: InvalidInputError,
        }
    )
    async def get(
        self,
        *,
        name: ServiceKey,
        version: ServiceVersion,
    ) -> ServiceGetV2:

        return await catalog_rpc.get_service(
            self._rpc_client,
            product_name=self.product_name,
            user_id=self.user_id,
            service_key=name,
            service_version=version,
        )

    @_exception_mapper(
        rpc_exception_map={
            CatalogItemNotFoundError: ProgramOrSolverOrStudyNotFoundError,
            CatalogForbiddenError: ServiceForbiddenAccessError,
            ValidationError: InvalidInputError,
        }
    )
    async def get_service_ports(
        self,
        *,
        name: ServiceKey,
        version: ServiceVersion,
    ) -> list[ServicePortGet]:
        """Gets service ports (inputs and outputs) for a specific service version

        Raises:
            ProgramOrSolverOrStudyNotFoundError: service not found in catalog
            ServiceForbiddenAccessError: no access rights to read this service
            InvalidInputError: invalid input parameters
        """
        return await catalog_rpc.get_service_ports(
            self._rpc_client,
            product_name=self.product_name,
            user_id=self.user_id,
            service_key=name,
            service_version=version,
        )

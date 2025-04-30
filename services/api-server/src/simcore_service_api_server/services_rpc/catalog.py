from functools import partial

from models_library.api_schemas_catalog.services import (
    LatestServiceGet,
    ServiceGetV2,
    ServiceListFilters,
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
from simcore_service_api_server.exceptions.backend_errors import (
    InvalidInputError,
    ProgramOrSolverOrStudyNotFoundError,
    ServiceForbiddenAccessError,
)

from ..exceptions.service_errors_utils import service_exception_mapper

_exception_mapper = partial(service_exception_mapper, service_name="CatalogService")


class CatalogService:
    _rpc_client: RabbitMQRPCClient

    # context
    _user_id: UserID
    _product_name: ProductName

    def __init__(
        self,
        *,
        rpc_client: RabbitMQRPCClient,
        user_id: UserID,
        product_name: ProductName,
    ):
        self._rpc_client = rpc_client

        self._user_id = user_id
        self._product_name = product_name

    async def list_latest_releases(
        self,
        *,
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        filters: ServiceListFilters | None = None,
    ) -> tuple[list[LatestServiceGet], PageMetaInfoLimitOffset]:

        page = await catalog_rpc.list_services_paginated(
            self._rpc_client,
            product_name=self._product_name,
            user_id=self._user_id,
            offset=offset,
            limit=limit,
            filters=filters,
        )
        meta = PageMetaInfoLimitOffset(
            limit=page.meta.limit,
            offset=page.meta.offset,
            total=page.meta.total,
            count=page.meta.count,
        )
        return page.data, meta

    async def list_release_history(
        self,
        *,
        service_key: ServiceKey,
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    ) -> tuple[list[ServiceRelease], PageMetaInfoLimitOffset]:

        page = await catalog_rpc.list_my_service_history_paginated(
            self._rpc_client,
            product_name=self._product_name,
            user_id=self._user_id,
            service_key=service_key,
            offset=offset,
            limit=limit,
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
            product_name=self._product_name,
            user_id=self._user_id,
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
            product_name=self._product_name,
            user_id=self._user_id,
            service_key=name,
            service_version=version,
        )

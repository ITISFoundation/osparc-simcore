from functools import partial
from typing import Annotated

from fastapi import Depends
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

from ..api.dependencies.rabbitmq import get_rabbitmq_rpc_client
from ..exceptions.service_errors_utils import service_exception_mapper

_exception_mapper = partial(service_exception_mapper, service_name="CatalogService")


class CatalogService:
    _client: RabbitMQRPCClient

    def __init__(
        self, client: Annotated[RabbitMQRPCClient, Depends(get_rabbitmq_rpc_client)]
    ):
        self._client = client

    async def list_latest_releases(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        filters: ServiceListFilters | None = None,
    ) -> tuple[list[LatestServiceGet], PageMetaInfoLimitOffset]:

        page = await catalog_rpc.list_services_paginated(
            self._client,
            product_name=product_name,
            user_id=user_id,
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

    async def list_release_history_latest_first(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    ) -> tuple[list[ServiceRelease], PageMetaInfoLimitOffset]:

        page = await catalog_rpc.list_my_service_history_latest_first(
            self._client,
            product_name=product_name,
            user_id=user_id,
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
        product_name: ProductName,
        user_id: UserID,
        name: ServiceKey,
        version: ServiceVersion,
    ) -> ServiceGetV2:

        return await catalog_rpc.get_service(
            self._client,
            product_name=product_name,
            user_id=user_id,
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
        product_name: ProductName,
        user_id: UserID,
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
            self._client,
            product_name=product_name,
            user_id=user_id,
            service_key=name,
            service_version=version,
        )

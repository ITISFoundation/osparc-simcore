from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_catalog.services import LatestServiceGet, ServiceGetV2
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
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.catalog import services as catalog_rpc

from ..api.dependencies.rabbitmq import get_rabbitmq_rpc_client


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
    ) -> tuple[list[LatestServiceGet], PageMetaInfoLimitOffset]:

        page = await catalog_rpc.list_services_paginated(
            self._client,
            product_name=product_name,
            user_id=user_id,
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

    async def list_release_history(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        offset: PageOffsetInt = 0,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    ) -> tuple[list[ServiceRelease], PageMetaInfoLimitOffset]:

        page = await catalog_rpc.list_my_service_history_paginated(
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

    async def get(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> ServiceGetV2:

        return await catalog_rpc.get_service(
            self._client,
            product_name=product_name,
            user_id=user_id,
            service_key=service_key,
            service_version=service_version,
        )

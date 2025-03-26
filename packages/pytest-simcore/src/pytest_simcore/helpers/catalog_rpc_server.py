# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.api_schemas_catalog.services import LatestServiceGet, ServiceGetV2
from models_library.api_schemas_webserver.catalog import (
    CatalogServiceUpdate,
)
from models_library.products import ProductName
from models_library.rpc_pagination import PageLimitInt, PageRpc
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import NonNegativeInt, TypeAdapter
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient


class CatalogRpcSideEffects:
    async def list_services_paginated(
        self,
        rpc_client: RabbitMQRPCClient,
        *,
        product_name: ProductName,
        user_id: UserID,
        limit: PageLimitInt,
        offset: NonNegativeInt,
    ):
        assert rpc_client
        assert product_name
        assert user_id

        items = TypeAdapter(list[LatestServiceGet]).validate_python(
            LatestServiceGet.model_json_schema()["examples"],
        )
        total_count = len(items)

        return PageRpc[LatestServiceGet].create(
            items[offset : offset + limit],
            total=total_count,
            limit=limit,
            offset=offset,
        )

    async def get_service(
        self,
        rpc_client: RabbitMQRPCClient,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ):
        assert rpc_client
        assert product_name
        assert user_id

        got = ServiceGetV2.model_validate(
            ServiceGetV2.model_json_schema()["examples"][0]
        )
        got.version = service_version
        got.key = service_key

        return got

    async def update_service(
        self,
        rpc_client: RabbitMQRPCClient,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
        update: CatalogServiceUpdate,
    ):
        assert rpc_client
        assert product_name
        assert user_id

        got = ServiceGetV2.model_validate(
            ServiceGetV2.model_json_schema()["examples"][0]
        )
        got.version = service_version
        got.key = service_key
        return got.model_copy(update=update.model_dump(exclude_unset=True))

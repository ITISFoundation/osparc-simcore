# pylint: disable=no-self-use
# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import fnmatch
from dataclasses import dataclass

from models_library.api_schemas_catalog.services import (
    LatestServiceGet,
    ServiceGetV2,
    ServiceListFilters,
    ServiceSummary,
    ServiceUpdateV2,
)
from models_library.api_schemas_catalog.services_ports import ServicePortGet
from models_library.products import ProductName
from models_library.rest_pagination import PageOffsetInt
from models_library.rpc_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
    PageRpc,
)
from models_library.services_enums import ServiceType
from models_library.services_history import ServiceRelease
from models_library.services_regex import (
    COMPUTATIONAL_SERVICE_KEY_RE,
    DYNAMIC_SERVICE_KEY_RE,
)
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import TypeAdapter, validate_call
from pytest_mock import MockType
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient

assert ServiceListFilters.model_json_schema()["properties"].keys() == {
    "service_type",
    "service_key_pattern",
    "version_display_pattern",
}, (
    "ServiceListFilters is expected to only have the key 'service_type'. "
    "Please update the mock if the schema changes."
)


class CatalogRpcSideEffects:
    # pylint: disable=no-self-use
    @validate_call(config={"arbitrary_types_allowed": True})
    async def list_services_paginated(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        product_name: ProductName,
        user_id: UserID,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        offset: PageOffsetInt = 0,
        filters: ServiceListFilters | None = None,
    ):
        assert rpc_client
        assert product_name
        assert user_id

        services_list = TypeAdapter(list[LatestServiceGet]).validate_python(
            LatestServiceGet.model_json_schema()["examples"],
        )
        if filters:

            filtered_services = []
            for src in services_list:
                # Match service type if specified
                if filters.service_type and src.service_type != filters.service_type:
                    continue

                # Match service key pattern if specified
                if filters.service_key_pattern and not fnmatch.fnmatch(
                    src.key, filters.service_key_pattern
                ):
                    continue

                # Match version display pattern if specified
                if filters.version_display_pattern and (
                    src.version_display is None
                    or not fnmatch.fnmatch(
                        src.version_display, filters.version_display_pattern
                    )
                ):
                    continue

                filtered_services.append(src)

            services_list = filtered_services

        total_count = len(services_list)

        return PageRpc[LatestServiceGet].create(
            services_list[offset : offset + limit],
            total=total_count,
            limit=limit,
            offset=offset,
        )

    @validate_call(config={"arbitrary_types_allowed": True})
    async def get_service(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
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

        if DYNAMIC_SERVICE_KEY_RE.match(got.key):
            got.service_type = ServiceType.DYNAMIC
        elif COMPUTATIONAL_SERVICE_KEY_RE.match(got.key):
            got.service_type = ServiceType.COMPUTATIONAL
        else:
            msg = "Service type not recognized. Please extend the mock yourself"
            raise RuntimeError(msg)

        return got

    @validate_call(config={"arbitrary_types_allowed": True})
    async def update_service(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
        update: ServiceUpdateV2,
    ) -> ServiceGetV2:
        assert rpc_client
        assert product_name
        assert user_id

        got = ServiceGetV2.model_validate(
            ServiceGetV2.model_json_schema()["examples"][0]
        )
        got.version = service_version
        got.key = service_key
        return got.model_copy(update=update.model_dump(exclude_unset=True))

    @validate_call(config={"arbitrary_types_allowed": True})
    async def list_my_service_history_latest_first(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        offset: PageOffsetInt = 0,
        filters: ServiceListFilters | None = None,
    ) -> PageRpc[ServiceRelease]:

        assert rpc_client
        assert product_name
        assert user_id
        assert service_key
        assert filters is None, "filters not mocked yet"

        items = TypeAdapter(list[ServiceRelease]).validate_python(
            ServiceRelease.model_json_schema()["examples"],
        )
        total_count = len(items)

        return PageRpc[ServiceRelease].create(
            items[offset : offset + limit],
            total=total_count,
            limit=limit,
            offset=offset,
        )

    @validate_call(config={"arbitrary_types_allowed": True})
    async def get_service_ports(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        product_name: ProductName,
        user_id: UserID,
        service_key: ServiceKey,
        service_version: ServiceVersion,
    ) -> list[ServicePortGet]:
        assert rpc_client
        assert product_name
        assert user_id
        assert service_key
        assert service_version

        return TypeAdapter(list[ServicePortGet]).validate_python(
            ServicePortGet.model_json_schema()["examples"],
        )

    @validate_call(config={"arbitrary_types_allowed": True})
    async def list_all_services_summaries_paginated(
        self,
        rpc_client: RabbitMQRPCClient | MockType,
        *,
        product_name: ProductName,
        user_id: UserID,
        limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
        offset: PageOffsetInt = 0,
        filters: ServiceListFilters | None = None,
    ):
        assert rpc_client
        assert product_name
        assert user_id

        service_summaries = TypeAdapter(list[ServiceSummary]).validate_python(
            ServiceSummary.model_json_schema()["examples"],
        )
        if filters:
            filtered_summaries = []
            for summary in service_summaries:
                # Match service type if specified
                if (
                    filters.service_type
                    and {
                        ServiceType.COMPUTATIONAL: "/comp/",
                        ServiceType.DYNAMIC: "/dynamic/",
                    }[filters.service_type]
                    not in summary.key
                ):
                    continue

                # Match service key pattern if specified
                if filters.service_key_pattern and not fnmatch.fnmatch(
                    summary.key, filters.service_key_pattern
                ):
                    continue

                # Match version display pattern if specified
                if filters.version_display_pattern and (
                    summary.version_display is None
                    or not fnmatch.fnmatch(
                        summary.version_display, filters.version_display_pattern
                    )
                ):
                    continue

                filtered_summaries.append(summary)

            service_summaries = filtered_summaries

        total_count = len(service_summaries)

        return PageRpc[ServiceSummary].create(
            service_summaries[offset : offset + limit],
            total=total_count,
            limit=limit,
            offset=offset,
        )


@dataclass
class ZeroListingCatalogRpcSideEffects:
    """Catalog RPC mocks that return empty lists"""

    async def list_services_paginated(self, *args, **kwargs): ...
    async def get_service(self, *args, **kwargs): ...
    async def update_service(self, *args, **kwargs): ...
    async def get_service_ports(self, *args, **kwargs): ...
    async def list_my_service_history_latest_first(self, *args, **kwargs):
        return PageRpc[ServiceRelease].create(
            [],
            total=0,
            limit=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
            offset=0,
        )

    async def list_all_services_summaries_paginated(self, *args, **kwargs):
        return PageRpc[ServiceSummary].create(
            [],
            total=0,
            limit=DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
            offset=0,
        )

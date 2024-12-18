from dataclasses import dataclass
from functools import partial
from typing import cast

from fastapi import FastAPI
from fastapi_pagination import Page, create_page
from models_library.api_schemas_webserver.licensed_items import LicensedItemGetPage
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.webserver.licenses.licensed_items import (
    get_licensed_items as _get_licensed_items,
)

from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.pagination import PaginationParams
from ..models.schemas.model_adapter import LicensedItemGet

_exception_mapper = partial(service_exception_mapper, service_name="WebApiServer")


@dataclass
class WbApiRpcClient:
    _client: RabbitMQRPCClient

    def _create_licensed_items_get_page(
        self, *, licensed_items_page: LicensedItemGetPage, page_params: PaginationParams
    ) -> Page[LicensedItemGet]:
        page = create_page(
            [
                LicensedItemGet(
                    licensed_item_id=elm.licensed_item_id,
                    name=elm.name,
                    license_key=elm.license_key,
                    licensed_resource_type=elm.licensed_resource_type,
                    pricing_plan_id=elm.pricing_plan_id,
                    created_at=elm.created_at,
                    modified_at=elm.modified_at,
                )
                for elm in licensed_items_page.items
            ],
            total=licensed_items_page.total,
            params=page_params,
        )
        return cast(Page[LicensedItemGet], page)

    @_exception_mapper(rpc_exception_map={})
    async def get_licensed_items(
        self, product_name: str, page_params: PaginationParams
    ) -> Page[LicensedItemGet]:
        licensed_items_page = await _get_licensed_items(
            rabbitmq_rpc_client=self._client,
            product_name=product_name,
            offset=page_params.offset,
            limit=page_params.limit,
        )
        return self._create_licensed_items_get_page(
            licensed_items_page=licensed_items_page, page_params=page_params
        )


def setup(app: FastAPI, rabbitmq_rmp_client: RabbitMQRPCClient):
    app.state.wb_api_rpc_client = WbApiRpcClient(_client=rabbitmq_rmp_client)

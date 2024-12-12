from dataclasses import dataclass
from functools import partial

from fastapi import FastAPI
from fastapi_pagination import Page, create_page
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
        return create_page(
            [
                LicensedItemGet.model_validate(elm.model_dump())
                for elm in licensed_items_page.items
            ],
            total=licensed_items_page.total,
            params=page_params,
        )


def setup(app: FastAPI, rabbitmq_rmp_client: RabbitMQRPCClient):
    app.state.wb_api_rpc_client = WbApiRpcClient(_client=rabbitmq_rmp_client)

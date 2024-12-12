from dataclasses import dataclass

from fastapi_pagination import Page, create_page
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.webserver.licenses.licensed_items import (
    get_licensed_items as _get_licensed_items,
)
from simcore_service_api_server.models.pagination import PaginationParams

from ..models.schemas.model_adapter import LicensedItemGet


@dataclass
class WbApiRpcClient:
    _rabbitmq_rpc_client: RabbitMQRPCClient

    async def get_licensed_items(
        self, product_name: str, page_params: PaginationParams
    ) -> Page[LicensedItemGet]:
        licensed_items_page = await _get_licensed_items(
            rabbitmq_rpc_client=self._rabbitmq_rpc_client,
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

from dataclasses import dataclass
from functools import partial
from typing import cast

from fastapi import FastAPI
from fastapi_pagination import Page, create_page
from models_library.api_schemas_webserver.licensed_items import LicensedItemGetPage
from models_library.licensed_items import LicensedItemID
from models_library.resource_tracker import ServiceRunId
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
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

from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.pagination import PaginationParams
from ..models.schemas.model_adapter import LicensedItemCheckoutGet, LicensedItemGet

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
        self, *, product_name: str, page_params: PaginationParams
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

    @_exception_mapper(rpc_exception_map={})
    async def get_available_licensed_items_for_wallet(
        self,
        *,
        product_name: str,
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
        return self._create_licensed_items_get_page(
            licensed_items_page=licensed_items_page, page_params=page_params
        )

    async def checkout_licensed_item_for_wallet(
        self,
        *,
        product_name: str,
        user_id: UserID,
        wallet_id: WalletID,
        licensed_item_id: LicensedItemID,
        num_of_seats: int,
        service_run_id: ServiceRunId,
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
            wallet_id=licensed_item_checkout_get.wallet_id,
            user_id=licensed_item_checkout_get.user_id,
            product_name=licensed_item_checkout_get.product_name,
            started_at=licensed_item_checkout_get.started_at,
            stopped_at=licensed_item_checkout_get.stopped_at,
            num_of_seats=licensed_item_checkout_get.num_of_seats,
        )

    async def release_licensed_item_for_wallet(
        self,
        *,
        product_name: str,
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
            wallet_id=licensed_item_checkout_get.wallet_id,
            user_id=licensed_item_checkout_get.user_id,
            product_name=licensed_item_checkout_get.product_name,
            started_at=licensed_item_checkout_get.started_at,
            stopped_at=licensed_item_checkout_get.stopped_at,
            num_of_seats=licensed_item_checkout_get.num_of_seats,
        )


def setup(app: FastAPI, rabbitmq_rmp_client: RabbitMQRPCClient):
    app.state.wb_api_rpc_client = WbApiRpcClient(_client=rabbitmq_rmp_client)

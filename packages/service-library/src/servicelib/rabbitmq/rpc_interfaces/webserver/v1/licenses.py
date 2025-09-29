"""Licenses RPC API subclient."""

from typing import Any

from models_library.api_schemas_webserver.licensed_items import LicensedItemRpcGetPage
from models_library.api_schemas_webserver.licensed_items_checkouts import (
    LicensedItemCheckoutRpcGet,
)
from models_library.licenses import LicensedItemID
from models_library.products import ProductName
from models_library.resource_tracker_licensed_items_checkouts import (
    LicensedItemCheckoutID,
)
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.wallets import WalletID

from ._base import BaseRpcApi


class LicensesRpcApi(BaseRpcApi):
    """RPC client for license-related operations."""

    async def get_licensed_items(
        self,
        *,
        product_name: ProductName,
        offset: int = 0,
        limit: int = 20,
    ) -> LicensedItemRpcGetPage:
        return await self._request_without_authentication(
            "get_licensed_items",
            product_name=product_name,
            offset=offset,
            limit=limit,
        )

    async def get_available_licensed_items_for_wallet(
        self,
        *,
        product_name: ProductName,
        wallet_id: WalletID,
        user_id: UserID,
        offset: int = 0,
        limit: int = 20,
    ) -> LicensedItemRpcGetPage:
        """Get licensed items for a wallet."""
        return await self._request(
            "get_available_licensed_items_for_wallet",
            product_name=product_name,
            user_id=user_id,
            wallet_id=wallet_id,
            offset=offset,
            limit=limit,
        )

    async def get_licensed_items_checkouts_for_wallet(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        wallet_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get licensed items checkouts for a wallet."""
        return await self._request(
            "get_licensed_items_checkouts_for_wallet",
            product_name=product_name,
            user_id=user_id,
            wallet_id=wallet_id,
        )

    async def checkout_licensed_item_for_wallet(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        wallet_id: WalletID,
        licensed_item_id: LicensedItemID,
        num_of_seats: int,
        service_run_id: ServiceRunID,
    ) -> LicensedItemCheckoutRpcGet:
        """Checkout a licensed item for a wallet."""
        return await self._request(
            "checkout_licensed_item_for_wallet",
            product_name=product_name,
            user_id=user_id,
            wallet_id=wallet_id,
            licensed_item_id=licensed_item_id,
            num_of_seats=num_of_seats,
            service_run_id=service_run_id,
        )

    async def release_licensed_item_for_wallet(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        licensed_item_checkout_id: LicensedItemCheckoutID,
    ) -> LicensedItemCheckoutRpcGet:
        """Release a licensed item checkout for a wallet."""
        return await self._request(
            "release_licensed_item_for_wallet",
            product_name=product_name,
            user_id=user_id,
            licensed_item_checkout_id=licensed_item_checkout_id,
        )

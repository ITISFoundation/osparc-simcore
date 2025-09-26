"""Licenses RPC API subclient."""

from typing import Any

from models_library.products import ProductName
from models_library.users import UserID

from ._base import BaseRpcApi


class LicensesRpcApi(BaseRpcApi):
    """RPC client for license-related operations."""

    async def get_licensed_items_for_wallet(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        wallet_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get licensed items for a wallet."""
        return await self._request(
            "get_licensed_items_for_wallet",
            product_name=product_name,
            user_id=user_id,
            wallet_id=wallet_id,
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
        licensed_item_id: str,
        wallet_id: int,
        num_of_seats: int,
        service_run_id: str,
    ) -> dict[str, Any]:
        """Checkout a licensed item for a wallet."""
        return await self._request(
            "checkout_licensed_item_for_wallet",
            product_name=product_name,
            user_id=user_id,
            licensed_item_id=licensed_item_id,
            wallet_id=wallet_id,
            num_of_seats=num_of_seats,
            service_run_id=service_run_id,
        )

    async def release_licensed_item_for_wallet(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        licensed_item_checkout_id: str,
        wallet_id: int,
    ) -> None:
        """Release a licensed item checkout for a wallet."""
        return await self._request(
            "release_licensed_item_for_wallet",
            product_name=product_name,
            user_id=user_id,
            licensed_item_checkout_id=licensed_item_checkout_id,
            wallet_id=wallet_id,
        )

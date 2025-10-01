"""API Keys RPC API subclient."""

from typing import cast

from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.rpc.webserver.auth.api_keys import ApiKeyCreate, ApiKeyGet
from models_library.users import UserID

from ._base import BaseRpcApi


class ApiKeysRpcApi(BaseRpcApi):
    """RPC client for API key-related operations."""

    async def create_api_key(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        api_key: ApiKeyCreate,
    ) -> ApiKeyGet:
        """Create an API key."""
        return cast(
            ApiKeyGet,
            await self._request(
                "create_api_key",
                product_name=product_name,
                user_id=user_id,
                display_name=api_key.display_name,
                expiration=api_key.expiration,
            ),
        )

    async def get_api_key(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        api_key_id: IDStr,
    ) -> ApiKeyGet:
        """Get an API key by ID."""
        return cast(
            ApiKeyGet,
            await self._request(
                "get_api_key",
                product_name=product_name,
                user_id=user_id,
                api_key_id=api_key_id,
            ),
        )

    async def delete_api_key_by_key(
        self,
        *,
        product_name: ProductName,
        user_id: UserID,
        api_key: str,
    ) -> None:
        """Delete an API key by key value."""
        await self._request(
            "delete_api_key_by_key",
            product_name=product_name,
            user_id=user_id,
            api_key=api_key,
        )

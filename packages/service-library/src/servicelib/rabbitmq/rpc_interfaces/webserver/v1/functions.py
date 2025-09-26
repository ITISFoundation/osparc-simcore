"""Functions RPC API subclient."""

from typing import Any

from ._base import BaseRpcApi


class FunctionsRpcApi(BaseRpcApi):
    """RPC client for function-related operations."""

    async def get_function(self, user_id: int, function_id: str) -> dict[str, Any]:
        """Get a function by ID."""
        return await self._request(
            "get_function", user_id=user_id, function_id=function_id
        )

    async def list_functions(
        self, user_id: int, *, limit: int | None = None, offset: int = 0
    ) -> list[dict[str, Any]]:
        """List available functions."""
        return await self._request(
            "list_functions", user_id=user_id, limit=limit, offset=offset
        )

    async def create_function(
        self, user_id: int, function_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new function."""
        return await self._request(
            "create_function", user_id=user_id, function_data=function_data
        )

    async def update_function(
        self, user_id: int, function_id: str, function_patch: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing function."""
        return await self._request(
            "update_function",
            user_id=user_id,
            function_id=function_id,
            function_patch=function_patch,
        )

    async def delete_function(self, user_id: int, function_id: str) -> None:
        """Delete a function."""
        return await self._request(
            "delete_function", user_id=user_id, function_id=function_id
        )

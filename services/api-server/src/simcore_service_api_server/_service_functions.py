from dataclasses import dataclass

from common_library.exclude import as_dict_exclude_none
from models_library.functions import RegisteredFunction
from models_library.products import ProductName
from models_library.rest_pagination import (
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.rpc_pagination import PageLimitInt
from models_library.users import UserID
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient

DEFAULT_PAGINATION_LIMIT = MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE - 1


@dataclass(frozen=True, kw_only=True)
class FunctionService:
    user_id: UserID
    product_name: ProductName
    _web_rpc_client: WbApiRpcClient

    async def list_functions(
        self,
        *,
        pagination_offset: PageOffsetInt | None = None,
        pagination_limit: PageLimitInt | None = None,
    ) -> tuple[list[RegisteredFunction], PageMetaInfoLimitOffset]:
        """Lists all functions for a user with pagination"""

        pagination_kwargs = as_dict_exclude_none(
            pagination_offset=pagination_offset, pagination_limit=pagination_limit
        )

        return await self._web_rpc_client.list_functions(
            user_id=self.user_id,
            product_name=self.product_name,
            **pagination_kwargs,
        )

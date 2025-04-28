import logging

from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.aiopg_errors import DatabaseError
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesRepo,
)
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class GroupsExtraPropertiesRepository(BaseRepository):
    async def use_on_demand_clusters(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
        product_name: ProductName,
    ) -> bool:
        try:
            group_properties = (
                await GroupExtraPropertiesRepo.get_aggregated_properties_for_user_v2(
                    self.db_engine,
                    connection,
                    user_id=user_id,
                    product_name=product_name,
                )
            )
            return bool(group_properties.use_on_demand_clusters)

        except DatabaseError:
            _logger.exception("Unexpected error while access DB:")
            return False

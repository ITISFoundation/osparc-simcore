import logging

from models_library.users import UserID
from simcore_postgres_database.errors import DatabaseError
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesRepo,
)

from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class GroupsExtraPropertiesRepository(BaseRepository):
    async def use_on_demand_clusters(self, user_id: UserID, product_name: str) -> bool:
        try:
            async with self.db_engine.acquire() as conn:
                group_properties = (
                    await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
                        conn, user_id=user_id, product_name=product_name
                    )
                )
            return group_properties.use_on_demand_clusters

        except DatabaseError:
            _logger.exception("Unexpected error while access DB:")
            return False

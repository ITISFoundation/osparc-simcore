from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraProperties,
    GroupExtraPropertiesRepo,
)

from ._base import BaseRepository


class GroupsExtraPropertiesRepository(BaseRepository):
    async def _get_aggregated_properties_for_user(
        self,
        *,
        user_id: int,
        product_name: str,
    ) -> GroupExtraProperties:
        async with self.db_engine.acquire() as conn:
            return await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
                conn, user_id=user_id, product_name=product_name
            )

    async def has_internet_access(self, *, user_id: int, product_name: str) -> bool:
        group_extra_properties = await self._get_aggregated_properties_for_user(
            user_id=user_id, product_name=product_name
        )
        return group_extra_properties.internet_access

    async def telemetry_enabled(self, *, user_id: int, product_name: str) -> bool:
        group_extra_properties = await self._get_aggregated_properties_for_user(
            user_id=user_id, product_name=product_name
        )
        return group_extra_properties.enable_telemetry

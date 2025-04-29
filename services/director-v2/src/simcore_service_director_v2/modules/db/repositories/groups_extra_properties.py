from pydantic import BaseModel
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraProperties,
    GroupExtraPropertiesRepo,
)

from ._base import BaseRepository


class UserExtraProperties(BaseModel):
    is_internet_enabled: bool
    is_telemetry_enabled: bool
    is_efs_enabled: bool


class GroupsExtraPropertiesRepository(BaseRepository):
    async def _get_aggregated_properties_for_user(
        self,
        *,
        user_id: int,
        product_name: str,
    ) -> GroupExtraProperties:
        async with self.db_engine.connect() as conn:
            return await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
                conn, user_id=user_id, product_name=product_name
            )

    async def has_internet_access(self, *, user_id: int, product_name: str) -> bool:
        group_extra_properties = await self._get_aggregated_properties_for_user(
            user_id=user_id, product_name=product_name
        )
        internet_access: bool = group_extra_properties.internet_access
        return internet_access

    async def is_telemetry_enabled(self, *, user_id: int, product_name: str) -> bool:
        group_extra_properties = await self._get_aggregated_properties_for_user(
            user_id=user_id, product_name=product_name
        )
        telemetry_enabled: bool = group_extra_properties.enable_telemetry
        return telemetry_enabled

    async def get_user_extra_properties(
        self, *, user_id: int, product_name: str
    ) -> UserExtraProperties:
        group_extra_properties = await self._get_aggregated_properties_for_user(
            user_id=user_id, product_name=product_name
        )
        return UserExtraProperties(
            is_internet_enabled=group_extra_properties.internet_access,
            is_telemetry_enabled=group_extra_properties.enable_telemetry,
            is_efs_enabled=group_extra_properties.enable_efs,
        )

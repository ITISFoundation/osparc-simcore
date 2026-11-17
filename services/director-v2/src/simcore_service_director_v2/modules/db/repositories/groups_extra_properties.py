from pydantic import BaseModel
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraProperties,
    GroupExtraPropertiesRepo,
)
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import BaseRepository


class UserExtraProperties(BaseModel):
    is_internet_enabled: bool
    is_telemetry_enabled: bool
    mount_data: bool


class GroupsExtraPropertiesRepository(BaseRepository):
    async def _get_aggregated_properties_for_user(
        self,
        *,
        user_id: int,
        product_name: str,
        connection: AsyncConnection | None = None,
    ) -> GroupExtraProperties:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            return await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
                conn, user_id=user_id, product_name=product_name
            )

    async def has_internet_access(
        self, *, user_id: int, product_name: str, connection: AsyncConnection | None = None
    ) -> bool:
        group_extra_properties = await self._get_aggregated_properties_for_user(
            user_id=user_id, product_name=product_name, connection=connection
        )
        internet_access: bool = group_extra_properties.internet_access
        return internet_access

    async def is_telemetry_enabled(
        self, *, user_id: int, product_name: str, connection: AsyncConnection | None = None
    ) -> bool:
        group_extra_properties = await self._get_aggregated_properties_for_user(
            user_id=user_id, product_name=product_name, connection=connection
        )
        telemetry_enabled: bool = group_extra_properties.enable_telemetry
        return telemetry_enabled

    async def get_user_extra_properties(
        self, *, user_id: int, product_name: str, connection: AsyncConnection | None = None
    ) -> UserExtraProperties:
        group_extra_properties = await self._get_aggregated_properties_for_user(
            user_id=user_id, product_name=product_name, connection=connection
        )
        return UserExtraProperties(
            is_internet_enabled=group_extra_properties.internet_access,
            is_telemetry_enabled=group_extra_properties.enable_telemetry,
            mount_data=group_extra_properties.mount_data,
        )

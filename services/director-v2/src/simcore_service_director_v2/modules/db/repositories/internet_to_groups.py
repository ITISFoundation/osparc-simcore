import sqlalchemy as sa
from models_library.users import UserID

from ..tables import internet_to_groups, user_to_groups
from ._base import BaseRepository


class InternetToGroupsRepository(BaseRepository):
    async def has_access(self, user_id: UserID) -> bool:
        async with self.db_engine.acquire() as conn:
            # checks if one of the groups which the user is part of has internet access
            select_stmt = sa.select([internet_to_groups.c.has_access]).select_from(
                user_to_groups.join(
                    internet_to_groups,
                    (internet_to_groups.c.group_id == user_to_groups.c.gid)
                    & (user_to_groups.c.uid == user_id)
                    & (internet_to_groups.c.has_access == True),
                )
            )

            user_with_access = await conn.scalar(select_stmt)
            return user_with_access is not None

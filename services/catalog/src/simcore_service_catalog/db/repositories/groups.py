from typing import List, Optional

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from pydantic.networks import EmailStr
from pydantic.types import PositiveInt

from ...models.domain.group import GroupAtDB
from ..tables import GroupType, groups, user_to_groups, users
from ._base import BaseRepository


class GroupsRepository(BaseRepository):
    async def list_user_groups(self, user_id: int) -> List[GroupAtDB]:
        groups_in_db = []
        async for row in self.connection.execute(
            sa.select([groups])
            .select_from(
                user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
            )
            .where(user_to_groups.c.uid == user_id)
        ):
            if row:
                groups_in_db.append(GroupAtDB(**row))
        return groups_in_db

    async def get_everyone_group(self) -> GroupAtDB:
        row: RowProxy = await (
            await self.connection.execute(
                sa.select([groups]).where(groups.c.type == GroupType.EVERYONE)
            )
        ).first()
        return GroupAtDB(**row)

    async def get_user_gid_from_email(
        self, user_email: EmailStr
    ) -> Optional[PositiveInt]:
        return await self.connection.scalar(
            sa.select([users.c.primary_gid]).where(users.c.email == user_email)
        )

    async def get_gid_from_affiliation(self, affiliation: str) -> Optional[PositiveInt]:
        return await self.connection.scalar(
            sa.select([groups.c.gid]).where(groups.c.name == affiliation)
        )

    async def get_user_email_from_gid(self, gid: PositiveInt) -> Optional[EmailStr]:
        return await self.connection.scalar(
            sa.select([users.c.email]).where(users.c.primary_gid == gid)
        )

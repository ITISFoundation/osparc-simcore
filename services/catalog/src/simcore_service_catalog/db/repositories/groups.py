from typing import Dict, List, Optional, Set

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from pydantic.networks import EmailStr
from pydantic.types import PositiveInt

from ...models.domain.group import GroupAtDB
from ..errors import RepositoryError
from ..tables import GroupType, groups, user_to_groups, users
from ._base import BaseRepository


class GroupsRepository(BaseRepository):
    async def list_user_groups(self, user_id: int) -> List[GroupAtDB]:
        groups_in_db = []
        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                sa.select([groups])
                .select_from(
                    user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
                )
                .where(user_to_groups.c.uid == user_id)
            ):
                groups_in_db.append(GroupAtDB(**row))
        return groups_in_db

    async def get_everyone_group(self) -> GroupAtDB:
        async with self.db_engine.acquire() as conn:
            row: RowProxy = await (
                await conn.execute(
                    sa.select([groups]).where(groups.c.type == GroupType.EVERYONE)
                )
            ).first()
        if not row:
            raise RepositoryError(f"{GroupType.EVERYONE} groups was never initialized")
        return GroupAtDB(**row)

    async def get_user_gid_from_email(
        self, user_email: EmailStr
    ) -> Optional[PositiveInt]:
        async with self.db_engine.acquire() as conn:
            return await conn.scalar(
                sa.select([users.c.primary_gid]).where(users.c.email == user_email)
            )

    async def get_gid_from_affiliation(self, affiliation: str) -> Optional[PositiveInt]:
        async with self.db_engine.acquire() as conn:
            return await conn.scalar(
                sa.select([groups.c.gid]).where(groups.c.name == affiliation)
            )

    async def get_user_email_from_gid(self, gid: PositiveInt) -> Optional[EmailStr]:
        async with self.db_engine.acquire() as conn:
            return await conn.scalar(
                sa.select([users.c.email]).where(users.c.primary_gid == gid)
            )

    async def list_user_emails_from_gids(
        self, gids: Set[PositiveInt]
    ) -> Dict[PositiveInt, Optional[EmailStr]]:
        service_owners = {}
        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                sa.select([users.c.primary_gid, users.c.email]).where(
                    users.c.primary_gid.in_(gids)
                )
            ):
                service_owners[row[users.c.primary_gid]] = (
                    EmailStr(row[users.c.email]) if row[users.c.email] else None
                )
        return service_owners

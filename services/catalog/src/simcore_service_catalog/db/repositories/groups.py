from typing import cast

import sqlalchemy as sa
from models_library.emails import LowerCaseEmailStr
from models_library.groups import GroupAtDB
from pydantic import parse_obj_as
from pydantic.types import PositiveInt

from ...exceptions.db_errors import RepositoryError
from ..tables import GroupType, groups, user_to_groups, users
from ._base import BaseRepository


class GroupsRepository(BaseRepository):
    async def list_user_groups(self, user_id: int) -> list[GroupAtDB]:
        groups_in_db = []
        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(
                sa.select(groups)
                .select_from(
                    user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
                )
                .where(user_to_groups.c.uid == user_id)
            ):
                groups_in_db.append(GroupAtDB.from_orm(row))
        return groups_in_db

    async def get_everyone_group(self) -> GroupAtDB:
        async with self.db_engine.connect() as conn:
            result = await conn.execute(
                sa.select(groups).where(groups.c.type == GroupType.EVERYONE)
            )
            row = result.first()
        if not row:
            msg = f"{GroupType.EVERYONE} groups was never initialized"
            raise RepositoryError(msg)
        return GroupAtDB.from_orm(row)

    async def get_user_gid_from_email(
        self, user_email: LowerCaseEmailStr
    ) -> PositiveInt | None:
        async with self.db_engine.connect() as conn:
            return cast(
                PositiveInt | None,
                await conn.scalar(
                    sa.select(users.c.primary_gid).where(users.c.email == user_email)
                ),
            )

    async def get_gid_from_affiliation(self, affiliation: str) -> PositiveInt | None:
        async with self.db_engine.connect() as conn:
            return cast(
                PositiveInt | None,
                await conn.scalar(
                    sa.select(groups.c.gid).where(groups.c.name == affiliation)
                ),
            )

    async def get_user_email_from_gid(
        self, gid: PositiveInt
    ) -> LowerCaseEmailStr | None:
        async with self.db_engine.connect() as conn:
            email = await conn.scalar(
                sa.select(users.c.email).where(users.c.primary_gid == gid)
            )
            return cast(LowerCaseEmailStr, f"{email}") if email else None

    async def list_user_emails_from_gids(
        self, gids: set[PositiveInt]
    ) -> dict[PositiveInt, LowerCaseEmailStr | None]:
        service_owners = {}
        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(
                sa.select([users.c.primary_gid, users.c.email]).where(
                    users.c.primary_gid.in_(gids)
                )
            ):
                service_owners[row[users.c.primary_gid]] = (
                    parse_obj_as(LowerCaseEmailStr, row[users.c.email])
                    if row[users.c.email]
                    else None
                )
        return service_owners

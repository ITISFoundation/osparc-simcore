import sqlalchemy as sa
from models_library.emails import LowerCaseEmailStr
from models_library.groups import GroupAtDB, GroupID, GroupIDAdapter
from pydantic import TypeAdapter
from pydantic.types import PositiveInt
from simcore_postgres_database.models.groups import GroupType, groups, user_to_groups
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ..errors import UninitializedGroupError
from ._base import BaseRepository


class GroupsRepository(BaseRepository):
    async def list_user_groups(
        self,
        user_id: int,
        connection: AsyncConnection | None = None,
    ) -> list[GroupAtDB]:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(
                sa.select(groups)
                .select_from(
                    user_to_groups.join(groups, user_to_groups.c.gid == groups.c.gid),
                )
                .where(user_to_groups.c.uid == user_id)
            )
            return TypeAdapter(list[GroupAtDB]).validate_python(result.mappings().all())

    async def get_everyone_group(
        self,
        connection: AsyncConnection | None = None,
    ) -> GroupAtDB:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(sa.select(groups).where(groups.c.type == GroupType.EVERYONE))
            row = result.first()
        if not row:
            raise UninitializedGroupError(group=GroupType.EVERYONE, repo_cls=GroupsRepository)
        return GroupAtDB.model_validate(row)

    async def get_user_gid_from_email(self, user_email: LowerCaseEmailStr) -> GroupID | None:
        async with self.db_engine.connect() as conn:
            gid = await conn.scalar(sa.select(users.c.primary_gid).where(users.c.email == user_email))
            return GroupIDAdapter.validate_python(gid) if gid is not None else None

    async def get_user_email_from_gid(
        self,
        gid: PositiveInt,
        connection: AsyncConnection | None = None,
    ) -> LowerCaseEmailStr | None:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.scalar(sa.select(users.c.email).where(users.c.primary_gid == gid))
            return TypeAdapter(LowerCaseEmailStr).validate_python(result) if result else None

    async def list_user_emails_from_gids(
        self,
        gids: set[PositiveInt],
        connection: AsyncConnection | None = None,
    ) -> dict[PositiveInt, LowerCaseEmailStr | None]:
        service_owners: dict[PositiveInt, LowerCaseEmailStr | None] = {}
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            result = await conn.execute(
                sa.select(users.c.primary_gid, users.c.email).where(users.c.primary_gid.in_(gids))
            )
            for row in result:
                service_owners[row.primary_gid] = (
                    TypeAdapter(LowerCaseEmailStr).validate_python(row.email) if row.email else None
                )
        return service_owners

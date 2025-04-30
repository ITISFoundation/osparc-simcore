import sqlalchemy as sa
from common_library.users_enums import UserStatus
from models_library.emails import LowerCaseEmailStr
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import BaseRepository


class UsersRepository(BaseRepository):
    async def get_active_user_email(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
    ) -> LowerCaseEmailStr | None:
        async with pass_or_acquire_connection(self.db_engine, connection) as conn:
            email = await conn.scalar(
                sa.select(users.c.email).where(
                    (users.c.id == user_id) & (users.c.status == UserStatus.ACTIVE)
                )
            )
        return (
            TypeAdapter(LowerCaseEmailStr).validate_python(email)
            if email is not None
            else None
        )

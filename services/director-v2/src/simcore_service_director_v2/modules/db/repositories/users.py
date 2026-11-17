from typing import cast

from models_library.users import UserID
from pydantic import EmailStr, TypeAdapter
from simcore_postgres_database.models.users import UserRole
from simcore_postgres_database.utils_users import UsersRepo
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import BaseRepository


class UsersRepository(BaseRepository):
    def _repo(self):
        return UsersRepo(self.db_engine)

    async def get_user_email(self, user_id: UserID, *, connection: AsyncConnection | None = None) -> EmailStr:
        email = await self._repo().get_email(connection, user_id=user_id)
        return TypeAdapter(EmailStr).validate_python(email)

    async def get_user_role(self, user_id: UserID, *, connection: AsyncConnection | None = None) -> UserRole:
        return cast(UserRole, await self._repo().get_role(connection, user_id=user_id))

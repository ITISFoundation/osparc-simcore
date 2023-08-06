from models_library.users import UserID
from simcore_postgres_database.utils_users import UsersRepo

from ._base import BaseRepository


class UsersRepository(BaseRepository):
    async def get_user_email(self, user_id: UserID) -> str:
        async with self.db_engine.acquire() as conn:
            return await UsersRepo.get_email(conn, user_id)

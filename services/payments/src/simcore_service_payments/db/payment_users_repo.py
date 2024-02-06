import sqlalchemy as sa
from models_library.users import GroupID, UserID
from simcore_postgres_database.models.users import users

from .base import BaseRepository


class PaymentsUsersRepo(BaseRepository):
    # NOTE:
    # Currently linked to `users` but expected to be linked to `payments_users`
    # when databases are separated. The latter will be a subset copy of the former.
    #
    async def get_primary_group_id(self, user_id: UserID) -> GroupID:
        async with self.db_engine.begin() as conn:
            result = await conn.execute(
                sa.select(users.c.primary_gid).where(users.c.id == user_id)
            )
            row = result.first()
            if row is None:
                msg = f"{user_id=} not found"
                raise ValueError(msg)
            return GroupID(row.primary_gid)

    async def get_email_info(self, user_id: UserID):
        raise NotImplementedError

import sqlalchemy as sa
from models_library.emails import LowerCaseEmailStr
from pydantic import parse_obj_as

from ..tables import users
from ._base import BaseRepository


class UsersRepository(BaseRepository):
    async def get_email_from_user_id(self, user_id: int) -> LowerCaseEmailStr | None:
        stmt = sa.select(
            [
                users.c.email,
            ]
        ).where(users.c.id == user_id)
        async with self.db_engine.acquire() as conn:
            email: str | None = await conn.scalar(stmt)
        return parse_obj_as(LowerCaseEmailStr, email) if email is not None else None

import sqlalchemy as sa
from models_library.emails import LowerCaseEmailStr
from pydantic import parse_obj_as

from ..tables import UserStatus, users
from ._base import BaseRepository


class UsersRepository(BaseRepository):
    async def get_active_user_email(self, user_id: int) -> LowerCaseEmailStr | None:
        async with self.db_engine.acquire() as conn:
            email: str | None = await conn.scalar(
                sa.select(users.c.email).where(
                    (users.c.id == user_id) & (users.c.status == UserStatus.ACTIVE)
                )
            )
        return parse_obj_as(LowerCaseEmailStr, email) if email is not None else None

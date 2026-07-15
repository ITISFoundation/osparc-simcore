from common_library.gettext_support import SupportedLocale
from models_library.users import UserID
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine


async def get_user_language(db_engine: AsyncEngine, *, user_id: UserID) -> SupportedLocale | None:
    """Returns the user's persisted language, or None if never set.

    NOTE: RUT does not own the user domain (the webserver does); this is a
    denormalized, read-only lookup on the shared `users` table, mirroring the
    same pattern used by the payments service (`PaymentsUsersRepo`).
    """
    async with pass_or_acquire_connection(db_engine) as conn:
        return await conn.scalar(select(users.c.language).where(users.c.id == user_id))

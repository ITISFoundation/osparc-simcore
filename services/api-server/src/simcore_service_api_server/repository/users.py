import sqlalchemy as sa
from aiocache import Cache, cached  # type: ignore[import-untyped]
from common_library.users_enums import UserStatus
from models_library.emails import LowerCaseEmailStr
from models_library.users import UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.users import users
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from sqlalchemy.ext.asyncio import AsyncConnection

from ._base import AUTH_SESSION_TTL_SECONDS, BaseRepository


class UsersRepository(BaseRepository):
    @cached(
        ttl=AUTH_SESSION_TTL_SECONDS,
        key_builder=lambda *_args, **kwargs: f"user_email:{kwargs['user_id']}",
        cache=Cache.MEMORY,
        namespace=__name__,
        noself=True,
    )
    async def get_active_user_email(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: UserID,
    ) -> LowerCaseEmailStr | None:
        """Retrieves the email address of an active user.

        Arguments:
            user_id -- The ID of the user whose email is to be retrieved.

        Returns:
            The email address of the user if found, otherwise None.

        WARNING: Cached for 120s TTL - email changes will not be seen for 2 minutes.
        NOTE: to disable caching set AIOCACHE_DISABLE=1
        """
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

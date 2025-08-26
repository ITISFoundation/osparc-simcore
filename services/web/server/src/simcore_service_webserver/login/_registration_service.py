from aiohttp import web
from simcore_postgres_database.utils_users import UsersRepo

from ..db.plugin import get_asyncpg_engine


def get_user_name_from_email(email: str) -> str:
    return email.split("@")[0]


async def register_user_phone(
    app: web.Application, *, user_id: int, user_phone: str
) -> None:
    asyncpg_engine = get_asyncpg_engine(app)
    repo = UsersRepo(asyncpg_engine)
    await repo.update_user_phone(user_id=user_id, phone=user_phone)

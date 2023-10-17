import logging
from typing import NamedTuple

from aiohttp import web
from models_library.users import UserID
from simcore_postgres_database.models.users import UserStatus

from ..db.plugin import get_database_engine
from ._db import get_user_or_raise
from ._db import list_user_permissions as db_list_of_permissions
from ._db import update_user_status
from .schemas import Permission

_logger = logging.getLogger(__name__)


async def list_user_permissions(
    app: web.Application, user_id: UserID, product_name: str
) -> list[Permission]:
    permissions: list[Permission] = await db_list_of_permissions(
        app, user_id=user_id, product_name=product_name
    )
    return permissions


class UserEmailAndPassHashTuple(NamedTuple):
    email: str
    password_hash: str


async def get_email_and_password_hash(
    app: web.Application, *, user_id: UserID
) -> UserEmailAndPassHashTuple:
    row = await get_user_or_raise(
        get_database_engine(app),
        user_id=user_id,
        return_column_names=["email", "password_hash"],
    )

    return UserEmailAndPassHashTuple(email=row.email, password_hash=row.password_hash)


async def set_user_as_deleted(app: web.Application, user_id: UserID) -> None:
    await update_user_status(
        get_database_engine(app), user_id=user_id, new_status=UserStatus.DELETED
    )

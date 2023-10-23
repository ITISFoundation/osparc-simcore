import logging
from typing import NamedTuple

from aiohttp import web
from models_library.emails import LowerCaseEmailStr
from models_library.users import UserID
from pydantic import parse_obj_as
from simcore_postgres_database.models.users import (
    FullNameTuple,
    UserNameConverter,
    UserStatus,
)

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


class UserCredentialsTuple(NamedTuple):
    email: LowerCaseEmailStr
    password_hash: str
    full_name: FullNameTuple


async def get_user_credentials(
    app: web.Application, *, user_id: UserID
) -> UserCredentialsTuple:
    row = await get_user_or_raise(
        get_database_engine(app),
        user_id=user_id,
        return_column_names=["name", "email", "password_hash"],
    )

    return UserCredentialsTuple(
        email=parse_obj_as(LowerCaseEmailStr, row.email),
        password_hash=row.password_hash,
        full_name=UserNameConverter.get_full_name(row.name),
    )


async def set_user_as_deleted(app: web.Application, user_id: UserID) -> None:
    await update_user_status(
        get_database_engine(app), user_id=user_id, new_status=UserStatus.DELETED
    )

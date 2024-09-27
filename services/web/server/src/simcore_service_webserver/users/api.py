# mypy: disable-error-code=truthy-function
"""
    This should be the interface other modules should use to get
    information from user module

"""

import logging
from collections import deque
from typing import Any, NamedTuple, TypedDict

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from aiopg.sa.result import RowProxy
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from pydantic import EmailStr, ValidationError, parse_obj_as
from simcore_postgres_database.models.users import UserRole

from ..db.models import GroupType, groups, user_to_groups, users
from ..db.plugin import get_database_engine
from ..groups.models import convert_groups_db_to_schema
from ..login.storage import AsyncpgStorage, get_plugin_storage
from ..security.api import clean_auth_policy_cache
from . import _db
from ._api import get_user_credentials, get_user_invoice_address, set_user_as_deleted
from ._preferences_api import get_frontend_user_preferences_aggregation
from .exceptions import UserNotFoundError
from .schemas import ProfileGet, ProfileUpdate

_logger = logging.getLogger(__name__)


def _parse_as_user(user_id: Any) -> UserID:
    try:
        return parse_obj_as(UserID, user_id)
    except ValidationError as err:
        raise UserNotFoundError(uid=user_id) from err


async def get_user_profile(
    app: web.Application, user_id: UserID, product_name: ProductName
) -> ProfileGet:
    """
    :raises UserNotFoundError:
    """

    engine = get_database_engine(app)
    user_profile: dict[str, Any] = {}
    user_primary_group = all_group = {}
    user_standard_groups = []
    user_id = _parse_as_user(user_id)

    async with engine.acquire() as conn:
        row: RowProxy
        async for row in conn.execute(
            sa.select(users, groups, user_to_groups.c.access_rights)
            .select_from(
                sa.join(
                    users,
                    sa.join(
                        user_to_groups, groups, user_to_groups.c.gid == groups.c.gid
                    ),
                    users.c.id == user_to_groups.c.uid,
                )
            )
            .where(users.c.id == user_id)
            .order_by(sa.asc(groups.c.name))
            .set_label_style(sa.LABEL_STYLE_TABLENAME_PLUS_COL)
        ):
            if not user_profile:
                user_profile = {
                    "id": row.users_id,
                    "first_name": row.users_first_name,
                    "last_name": row.users_last_name,
                    "login": row.users_email,
                    "role": row.users_role,
                    "expiration_date": (
                        row.users_expires_at.date() if row.users_expires_at else None
                    ),
                }
                assert user_profile["id"] == user_id  # nosec

            if row.groups_type == GroupType.EVERYONE:
                all_group = convert_groups_db_to_schema(
                    row,
                    prefix="groups_",
                    accessRights=row["user_to_groups_access_rights"],
                )
            elif row.groups_type == GroupType.PRIMARY:
                user_primary_group = convert_groups_db_to_schema(
                    row,
                    prefix="groups_",
                    accessRights=row["user_to_groups_access_rights"],
                )
            else:
                user_standard_groups.append(
                    convert_groups_db_to_schema(
                        row,
                        prefix="groups_",
                        accessRights=row["user_to_groups_access_rights"],
                    )
                )

    if not user_profile:
        raise UserNotFoundError(uid=user_id)

    preferences = await get_frontend_user_preferences_aggregation(
        app, user_id=user_id, product_name=product_name
    )

    # NOTE: expirationDate null is not handled properly in front-end.
    # https://github.com/ITISFoundation/osparc-simcore/issues/5244
    optional = {}
    if user_profile.get("expiration_date"):
        optional["expiration_date"] = user_profile["expiration_date"]

    return ProfileGet(
        id=user_profile["id"],
        first_name=user_profile["first_name"],
        last_name=user_profile["last_name"],
        login=user_profile["login"],
        role=user_profile["role"],
        groups={  # type: ignore[arg-type]
            "me": user_primary_group,
            "organizations": user_standard_groups,
            "all": all_group,
        },
        preferences=preferences,
        **optional,
    )


async def update_user_profile(
    app: web.Application,
    user_id: UserID,
    update: ProfileUpdate,
    *,
    as_patch: bool = True,
) -> None:
    """
    Keyword Arguments:
        as_patch -- set False if PUT and True if PATCH (default: {True})

    Raises:
        UserNotFoundError
    """
    user_id = _parse_as_user(user_id)

    async with get_database_engine(app).acquire() as conn:
        to_update = update.dict(
            include={
                "first_name",
                "last_name",
            },
            exclude_unset=as_patch,
        )
        resp = await conn.execute(
            users.update().where(users.c.id == user_id).values(**to_update)
        )
        assert resp.rowcount == 1  # nosec


async def get_user_role(app: web.Application, user_id: UserID) -> UserRole:
    """
    :raises UserNotFoundError:
    """
    user_id = _parse_as_user(user_id)

    engine = get_database_engine(app)
    async with engine.acquire() as conn:
        user_role: RowProxy | None = await conn.scalar(
            sa.select(users.c.role).where(users.c.id == user_id)
        )
        if user_role is None:
            raise UserNotFoundError(uid=user_id)
        return UserRole(user_role)


class UserIdNamesTuple(NamedTuple):
    name: str
    email: str


async def get_user_name_and_email(
    app: web.Application, *, user_id: UserID
) -> UserIdNamesTuple:
    """
    Raises:
        UserNotFoundError

    Returns:
        (user, email)
    """
    row = await _db.get_user_or_raise(
        get_database_engine(app),
        user_id=_parse_as_user(user_id),
        return_column_names=["name", "email"],
    )
    return UserIdNamesTuple(name=row.name, email=row.email)


class UserDisplayAndIdNamesTuple(NamedTuple):
    name: str
    email: EmailStr
    first_name: IDStr
    last_name: IDStr

    @property
    def full_name(self) -> IDStr:
        return IDStr.concatenate(self.first_name, self.last_name)


async def get_user_display_and_id_names(
    app: web.Application, *, user_id: UserID
) -> UserDisplayAndIdNamesTuple:
    """
    Raises:
        UserNotFoundError
    """
    row = await _db.get_user_or_raise(
        get_database_engine(app),
        user_id=_parse_as_user(user_id),
        return_column_names=["name", "email", "first_name", "last_name"],
    )
    return UserDisplayAndIdNamesTuple(
        name=row.name,
        email=row.email,
        first_name=row.first_name or row.name.capitalize(),
        last_name=IDStr(row.last_name or ""),
    )


async def get_guest_user_ids_and_names(app: web.Application) -> list[tuple[int, str]]:
    engine = get_database_engine(app)
    result: deque = deque()
    async with engine.acquire() as conn:
        async for row in conn.execute(
            sa.select(users.c.id, users.c.name).where(users.c.role == UserRole.GUEST)
        ):
            result.append(row.as_tuple())
        return list(result)


async def delete_user_without_projects(app: web.Application, user_id: UserID) -> None:
    """Deletes a user from the database if the user exists"""
    # WARNING: user cannot be deleted without deleting first all ist project
    # otherwise this function will raise asyncpg.exceptions.ForeignKeyViolationError
    # Consider "marking" users as deleted and havning a background job that
    # cleans it up
    db: AsyncpgStorage = get_plugin_storage(app)
    user = await db.get_user({"id": user_id})
    if not user:
        _logger.warning(
            "User with id '%s' could not be deleted because it does not exist", user_id
        )
        return

    await db.delete_user(dict(user))

    # This user might be cached in the auth. If so, any request
    # with this user-id will get thru producing unexpected side-effects
    await clean_auth_policy_cache(app)


class FullNameDict(TypedDict):
    first_name: str | None
    last_name: str | None


async def get_user_fullname(app: web.Application, user_id: UserID) -> FullNameDict:
    """
    :raises UserNotFoundError:
    """
    user_id = _parse_as_user(user_id)

    async with get_database_engine(app).acquire() as conn:
        result = await conn.execute(
            sa.select(users.c.first_name, users.c.last_name).where(
                users.c.id == user_id
            )
        )
        user = await result.first()
        if not user:
            raise UserNotFoundError(uid=user_id)

        return FullNameDict(
            first_name=user.first_name,
            last_name=user.last_name,
        )


async def get_user(app: web.Application, user_id: UserID) -> dict[str, Any]:
    """
    :raises UserNotFoundError:
    """
    row = await _db.get_user_or_raise(engine=get_database_engine(app), user_id=user_id)
    return dict(row)


async def get_user_id_from_gid(app: web.Application, primary_gid: int) -> UserID:
    engine = get_database_engine(app)
    async with engine.acquire() as conn:
        user_id: UserID = await conn.scalar(
            sa.select(users.c.id).where(users.c.primary_gid == primary_gid)
        )
        return user_id


async def get_users_in_group(app: web.Application, gid: GroupID) -> set[UserID]:
    engine = get_database_engine(app)
    async with engine.acquire() as conn:
        return await _db.get_users_ids_in_group(conn, gid)


async def update_expired_users(engine: Engine) -> list[UserID]:
    async with engine.acquire() as conn:
        return await _db.do_update_expired_users(conn)


assert set_user_as_deleted  # nosec
assert get_user_credentials  # nosec
assert get_user_invoice_address  # nosec

__all__: tuple[str, ...] = (
    "get_user_credentials",
    "set_user_as_deleted",
    "get_user_invoice_address",
)

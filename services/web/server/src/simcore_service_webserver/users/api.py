# mypy: disable-error-code=truthy-function
"""
    This should be the interface other modules should use to get
    information from user module

"""

import logging
from typing import Any, NamedTuple, TypedDict

import simcore_postgres_database.errors as db_errors
import sqlalchemy as sa
from aiohttp import web
from models_library.api_schemas_webserver.users import (
    MyProfileGet,
    MyProfilePatch,
    MyProfilePrivacyGet,
)
from models_library.basic_types import IDStr
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import EmailStr, TypeAdapter, ValidationError
from simcore_postgres_database.models.groups import GroupType, groups, user_to_groups
from simcore_postgres_database.models.users import UserRole, users
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesNotFoundError,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_users import generate_alternative_username
from sqlalchemy.engine.row import Row

from ..db.plugin import get_asyncpg_engine
from ..login.storage import AsyncpgStorage, get_plugin_storage
from ..security.api import clean_auth_policy_cache
from . import _users_repository
from ._preferences_api import get_frontend_user_preferences_aggregation
from ._users_service import (
    get_user_credentials,
    get_user_invoice_address,
    set_user_as_deleted,
)
from .common._models import ToUserUpdateDB
from .exceptions import (
    MissingGroupExtraPropertiesForProductError,
    UserNameDuplicateError,
    UserNotFoundError,
)

_logger = logging.getLogger(__name__)


_GROUPS_SCHEMA_TO_DB = {
    "gid": "gid",
    "label": "name",
    "description": "description",
    "thumbnail": "thumbnail",
    "accessRights": "access_rights",
}


def _convert_groups_db_to_schema(
    db_row: Row, *, prefix: str | None = "", **kwargs
) -> dict:
    # NOTE: Deprecated. has to be replaced with
    converted_dict = {
        k: db_row[f"{prefix}{v}"]
        for k, v in _GROUPS_SCHEMA_TO_DB.items()
        if f"{prefix}{v}" in db_row
    }
    converted_dict.update(**kwargs)
    converted_dict["inclusionRules"] = {}
    return converted_dict


def _parse_as_user(user_id: Any) -> UserID:
    try:
        return TypeAdapter(UserID).validate_python(user_id)
    except ValidationError as err:
        raise UserNotFoundError(uid=user_id, user_id=user_id) from err


async def get_user_profile(
    app: web.Application, *, user_id: UserID, product_name: ProductName
) -> MyProfileGet:
    """
    :raises UserNotFoundError:
    :raises MissingGroupExtraPropertiesForProductError: when product is not properly configured
    """
    user_profile: dict[str, Any] = {}
    user_primary_group = everyone_group = {}
    user_standard_groups = []
    user_id = _parse_as_user(user_id)

    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        result = await conn.stream(
            sa.select(users, groups, user_to_groups.c.access_rights)
            .select_from(
                users.join(user_to_groups, users.c.id == user_to_groups.c.uid).join(
                    groups, user_to_groups.c.gid == groups.c.gid
                )
            )
            .where(users.c.id == user_id)
            .order_by(sa.asc(groups.c.name))
            .set_label_style(sa.LABEL_STYLE_TABLENAME_PLUS_COL)
        )

        async for row in result:
            if not user_profile:
                user_profile = {
                    "id": row.users_id,
                    "user_name": row.users_name,
                    "first_name": row.users_first_name,
                    "last_name": row.users_last_name,
                    "login": row.users_email,
                    "role": row.users_role,
                    "privacy_hide_fullname": row.users_privacy_hide_fullname,
                    "privacy_hide_email": row.users_privacy_hide_email,
                    "expiration_date": (
                        row.users_expires_at.date() if row.users_expires_at else None
                    ),
                }
                assert user_profile["id"] == user_id  # nosec

            if row.groups_type == GroupType.EVERYONE:
                everyone_group = _convert_groups_db_to_schema(
                    row,
                    prefix="groups_",
                    accessRights=row["user_to_groups_access_rights"],
                )
            elif row.groups_type == GroupType.PRIMARY:
                user_primary_group = _convert_groups_db_to_schema(
                    row,
                    prefix="groups_",
                    accessRights=row["user_to_groups_access_rights"],
                )
            else:
                user_standard_groups.append(
                    _convert_groups_db_to_schema(
                        row,
                        prefix="groups_",
                        accessRights=row["user_to_groups_access_rights"],
                    )
                )

    if not user_profile:
        raise UserNotFoundError(uid=user_id)

    try:
        preferences = await get_frontend_user_preferences_aggregation(
            app, user_id=user_id, product_name=product_name
        )
    except GroupExtraPropertiesNotFoundError as err:
        raise MissingGroupExtraPropertiesForProductError(
            user_id=user_id, product_name=product_name
        ) from err

    # NOTE: expirationDate null is not handled properly in front-end.
    # https://github.com/ITISFoundation/osparc-simcore/issues/5244
    optional = {}
    if user_profile.get("expiration_date"):
        optional["expiration_date"] = user_profile["expiration_date"]

    return MyProfileGet(
        id=user_profile["id"],
        user_name=user_profile["user_name"],
        first_name=user_profile["first_name"],
        last_name=user_profile["last_name"],
        login=user_profile["login"],
        role=user_profile["role"],
        groups={  # type: ignore[arg-type]
            "me": user_primary_group,
            "organizations": user_standard_groups,
            "all": everyone_group,
        },
        privacy=MyProfilePrivacyGet(
            hide_fullname=user_profile["privacy_hide_fullname"],
            hide_email=user_profile["privacy_hide_email"],
        ),
        preferences=preferences,
        **optional,
    )


async def update_user_profile(
    app: web.Application,
    *,
    user_id: UserID,
    update: MyProfilePatch,
) -> None:
    """
    Raises:
        UserNotFoundError
        UserNameAlreadyExistsError
    """
    user_id = _parse_as_user(user_id)

    if updated_values := ToUserUpdateDB.from_api(update).to_db():

        async with transaction_context(engine=get_asyncpg_engine(app)) as conn:
            query = users.update().where(users.c.id == user_id).values(**updated_values)

            try:
                await conn.execute(query)

            except db_errors.UniqueViolation as err:
                user_name = updated_values.get("name")

                raise UserNameDuplicateError(
                    user_name=user_name,
                    alternative_user_name=generate_alternative_username(user_name),
                    user_id=user_id,
                    updated_values=updated_values,
                ) from err


async def get_user_role(app: web.Application, *, user_id: UserID) -> UserRole:
    """
    :raises UserNotFoundError:
    """
    user_id = _parse_as_user(user_id)

    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        user_role = await conn.scalar(
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
    row = await _users_repository.get_user_or_raise(
        get_asyncpg_engine(app),
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
    row = await _users_repository.get_user_or_raise(
        get_asyncpg_engine(app),
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
    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        result = await conn.stream(
            sa.select(users.c.id, users.c.name).where(users.c.role == UserRole.GUEST)
        )
        return [(row.id, row.name) async for row in result]


async def delete_user_without_projects(app: web.Application, user_id: UserID) -> None:
    """Deletes a user from the database if the user exists"""
    # WARNING: user cannot be deleted without deleting first all ist project
    # otherwise this function will raise asyncpg.exceptions.ForeignKeyViolationError
    # Consider "marking" users as deleted and havning a background job that
    # cleans it up
    # TODO: upgrade!!!
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

    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        result = await conn.stream(
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
    row: Row = await _users_repository.get_user_or_raise(
        engine=get_asyncpg_engine(app), user_id=user_id
    )
    user: dict[str, Any] = row._asdict()
    return user


async def get_user_id_from_gid(app: web.Application, primary_gid: int) -> UserID:
    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        user_id: UserID = await conn.scalar(
            sa.select(users.c.id).where(users.c.primary_gid == primary_gid)
        )
        return user_id


async def get_users_in_group(app: web.Application, gid: GroupID) -> set[UserID]:
    return await _users_repository.get_users_ids_in_group(
        get_asyncpg_engine(app), group_id=gid
    )


async def update_expired_users(app: web.Application) -> list[UserID]:
    return await _users_repository.do_update_expired_users(get_asyncpg_engine(app))


assert set_user_as_deleted  # nosec
assert get_user_credentials  # nosec
assert get_user_invoice_address  # nosec

__all__: tuple[str, ...] = (
    "get_user_credentials",
    "set_user_as_deleted",
    "get_user_invoice_address",
)

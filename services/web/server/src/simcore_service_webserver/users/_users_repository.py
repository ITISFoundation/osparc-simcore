import contextlib
import logging
from typing import Any

import sqlalchemy as sa
from aiohttp import web
from common_library.users_enums import UserRole
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.users import (
    MyProfile,
    UserBillingDetails,
    UserID,
    UserNameID,
    UserPermission,
)
from pydantic import TypeAdapter, ValidationError
from simcore_postgres_database.models.groups import groups, user_to_groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import UserStatus, users
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesNotFoundError,
    GroupExtraPropertiesRepo,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_users import (
    UsersRepo,
    generate_alternative_username,
    is_public,
    visible_user_profile_cols,
)
from sqlalchemy import delete
from sqlalchemy.engine.row import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ..db.plugin import get_asyncpg_engine
from ._models import FullNameDict, ToUserUpdateDB
from .exceptions import (
    BillingDetailsNotFoundError,
    UserNameDuplicateError,
    UserNotFoundError,
)

_logger = logging.getLogger(__name__)


def _parse_as_user(user_id: Any) -> UserID:
    try:
        return TypeAdapter(UserID).validate_python(user_id)
    except ValidationError as err:
        raise UserNotFoundError(user_id=user_id) from err


def _public_user_cols(caller_id: int):
    return (
        # Fits PublicUser model
        users.c.id.label("user_id"),
        *visible_user_profile_cols(caller_id, username_label="user_name"),
        users.c.primary_gid.label("group_id"),
    )


#
#  PUBLIC User
#


async def get_public_user(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    caller_id: UserID,
    user_id: UserID,
):
    query = sa.select(*_public_user_cols(caller_id=caller_id)).where(
        users.c.id == user_id
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.execute(query)
        user = result.first()
        if not user:
            raise UserNotFoundError(user_id=user_id)
        return user


async def search_public_user(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    caller_id: UserID,
    search_pattern: str,
    limit: int,
) -> list:
    _pattern = f"%{search_pattern}%"

    query = (
        sa.select(*_public_user_cols(caller_id=caller_id))
        .where(
            (
                is_public(users.c.privacy_hide_username, caller_id)
                & users.c.name.ilike(_pattern)
            )
            | (
                is_public(users.c.privacy_hide_email, caller_id)
                & users.c.email.ilike(_pattern)
            )
            | (
                is_public(users.c.privacy_hide_fullname, caller_id)
                & (
                    users.c.first_name.ilike(_pattern)
                    | users.c.last_name.ilike(_pattern)
                )
            )
        )
        .limit(limit)
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.stream(query)
        return [got async for got in result]


async def get_user_or_raise(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    return_column_names: list[str] | None = None,
) -> dict[str, Any]:
    if not return_column_names:  # None or empty list, returns all
        return_column_names = list(users.columns.keys())

    assert return_column_names is not None  # nosec
    assert set(return_column_names).issubset(users.columns.keys())  # nosec

    query = sa.select(*(users.columns[name] for name in return_column_names)).where(
        users.c.id == user_id
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.execute(query)
        row = result.first()
        if row is None:
            raise UserNotFoundError(user_id=user_id)

        user: dict[str, Any] = row._asdict()
        return user


async def get_user_primary_group_id(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
) -> GroupID:
    async with pass_or_acquire_connection(engine, connection) as conn:
        primary_gid: GroupID | None = await conn.scalar(
            sa.select(
                users.c.primary_gid,
            ).where(users.c.id == user_id)
        )
        if primary_gid is None:
            raise UserNotFoundError(user_id=user_id)
        return primary_gid


async def get_users_ids_in_group(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    group_id: GroupID,
) -> set[UserID]:
    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.stream(
            sa.select(
                user_to_groups.c.uid,
            ).where(user_to_groups.c.gid == group_id)
        )
        return {row.uid async for row in result}


async def get_user_id_from_pgid(app: web.Application, *, primary_gid: int) -> UserID:
    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        user_id: UserID = await conn.scalar(
            sa.select(
                users.c.id,
            ).where(users.c.primary_gid == primary_gid)
        )
        return user_id


async def get_user_email_legacy(engine: AsyncEngine, *, user_id: UserID | None) -> str:
    if not user_id:
        return "not_a_user@unknown.com"
    async with pass_or_acquire_connection(engine=engine) as conn:
        email: str | None = await conn.scalar(
            sa.select(
                users.c.email,
            ).where(users.c.id == user_id)
        )
        return email or "Unknown"


async def get_user_fullname(app: web.Application, *, user_id: UserID) -> FullNameDict:
    """
    :raises UserNotFoundError:
    """
    user_id = _parse_as_user(user_id)

    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        result = await conn.execute(
            sa.select(
                users.c.first_name,
                users.c.last_name,
            ).where(users.c.id == user_id)
        )
        user = result.first()
        if not user:
            raise UserNotFoundError(user_id=user_id)

        return FullNameDict(
            first_name=user.first_name,
            last_name=user.last_name,
        )


async def get_guest_user_ids_and_names(
    app: web.Application,
) -> list[tuple[UserID, UserNameID]]:
    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        result = await conn.stream(
            sa.select(
                users.c.id,
                users.c.name,
            ).where(users.c.role == UserRole.GUEST)
        )

        return TypeAdapter(list[tuple[UserID, UserNameID]]).validate_python(
            [(row.id, row.name) async for row in result]
        )


async def get_user_role(app: web.Application, *, user_id: UserID) -> UserRole:
    """
    :raises UserNotFoundError:
    """
    user_id = _parse_as_user(user_id)

    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        user_role = await conn.scalar(
            sa.select(
                users.c.role,
            ).where(users.c.id == user_id)
        )
        if user_role is None:
            raise UserNotFoundError(user_id=user_id)
        assert isinstance(user_role, UserRole)  # nosec
        return user_role


async def list_user_permissions(
    app: web.Application,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: str,
) -> list[UserPermission]:
    override_services_specifications = UserPermission(
        name="override_services_specifications",
        allowed=False,
    )
    engine = get_asyncpg_engine(app)
    with contextlib.suppress(GroupExtraPropertiesNotFoundError):
        async with pass_or_acquire_connection(engine, connection) as conn:
            user_group_extra_properties = (
                await GroupExtraPropertiesRepo.get_aggregated_properties_for_user(
                    conn, user_id=user_id, product_name=product_name
                )
            )
        override_services_specifications.allowed = (
            user_group_extra_properties.override_services_specifications
        )

    return [override_services_specifications]


async def do_update_expired_users(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
) -> list[UserID]:
    async with transaction_context(engine, connection) as conn:
        result = await conn.stream(
            users.update()
            .values(
                status=UserStatus.EXPIRED,
            )
            .where(
                (users.c.expires_at.is_not(None))
                & (users.c.status == UserStatus.ACTIVE)
                & (users.c.expires_at < sa.sql.func.now())
            )
            .returning(users.c.id)
        )
        return [row.id async for row in result]


async def update_user_status(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    new_status: UserStatus,
):
    async with transaction_context(engine, connection) as conn:
        await conn.execute(
            users.update()
            .values(
                status=new_status,
            )
            .where(users.c.id == user_id)
        )


async def get_user_products(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
) -> list[Row]:
    """Returns the products the user is part of, i.e.
    the user is registered and assigned to the product's group
    """
    async with pass_or_acquire_connection(engine, connection) as conn:
        product_name_subq = (
            sa.select(
                products.c.name,
            )
            .where(products.c.group_id == groups.c.gid)
            .label("product_name")
        )
        products_group_ids_subq = sa.select(
            products.c.group_id,
        ).distinct()
        query = (
            sa.select(
                groups.c.gid,
                product_name_subq,
            )
            .select_from(
                users.join(user_to_groups, user_to_groups.c.uid == users.c.id).join(
                    groups,
                    (groups.c.gid == user_to_groups.c.gid)
                    & groups.c.gid.in_(products_group_ids_subq),
                )
            )
            .where(users.c.id == user_id)
            .order_by(groups.c.gid)
        )
        result = await conn.stream(query)
        return [row async for row in result]


async def get_user_billing_details(
    engine: AsyncEngine, connection: AsyncConnection | None = None, *, user_id: UserID
) -> UserBillingDetails:
    """
    Raises:
        BillingDetailsNotFoundError
    """
    async with pass_or_acquire_connection(engine, connection) as conn:
        query = UsersRepo.get_billing_details_query(user_id=user_id)
        result = await conn.execute(query)
        row = result.first()
        if not row:
            raise BillingDetailsNotFoundError(user_id=user_id)
        return UserBillingDetails.model_validate(row)


async def delete_user_by_id(
    engine: AsyncEngine, connection: AsyncConnection | None = None, *, user_id: UserID
) -> bool:
    async with transaction_context(engine, connection) as conn:
        result = await conn.execute(
            delete(users)
            .where(users.c.id == user_id)
            .returning(users.c.id)  # Return the ID of the deleted row otherwise None
        )
        deleted_user = result.first()

        # If no row was deleted, the user did not exist
        return bool(deleted_user)


async def is_user_in_product_name(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> bool:
    query = (
        sa.select(users.c.id)
        .select_from(
            users.join(
                user_to_groups,
                user_to_groups.c.uid == users.c.id,
            ).join(
                products,
                products.c.group_id == user_to_groups.c.gid,
            )
        )
        .where((users.c.id == user_id) & (products.c.name == product_name))
    )
    async with pass_or_acquire_connection(engine, connection) as conn:
        value = await conn.scalar(query)
        assert value is None or value == user_id  # nosec
        return value is not None


#
# USER PROFILE
#


async def get_my_profile(app: web.Application, *, user_id: UserID) -> MyProfile:
    user_id = _parse_as_user(user_id)

    async with pass_or_acquire_connection(engine=get_asyncpg_engine(app)) as conn:
        result = await conn.stream(
            sa.select(
                # users -> MyProfile map
                users.c.id,
                users.c.name.label("user_name"),
                users.c.first_name,
                users.c.last_name,
                users.c.email,
                users.c.role,
                sa.func.json_build_object(
                    "hide_username",
                    users.c.privacy_hide_username,
                    "hide_fullname",
                    users.c.privacy_hide_fullname,
                    "hide_email",
                    users.c.privacy_hide_email,
                ).label("privacy"),
                sa.case(
                    (
                        users.c.expires_at.isnot(None),
                        sa.func.date(users.c.expires_at),
                    ),
                    else_=None,
                ).label("expiration_date"),
            ).where(users.c.id == user_id)
        )
        row = await result.first()
        if not row:
            raise UserNotFoundError(user_id=user_id)

        my_profile = MyProfile.model_validate(row, from_attributes=True)
        assert my_profile.id == user_id  # nosec

    return my_profile


async def update_user_profile(
    app: web.Application,
    *,
    user_id: UserID,
    update: ToUserUpdateDB,
) -> None:
    """
    Raises:
        UserNotFoundError
        UserNameAlreadyExistsError
    """
    user_id = _parse_as_user(user_id)

    if updated_values := update.to_db():
        try:
            async with transaction_context(engine=get_asyncpg_engine(app)) as conn:
                await conn.execute(
                    users.update()
                    .where(
                        users.c.id == user_id,
                    )
                    .values(**updated_values)
                )

        except IntegrityError as err:
            if user_name := updated_values.get("name"):
                raise UserNameDuplicateError(
                    user_name=user_name,
                    alternative_user_name=generate_alternative_username(user_name),
                    user_id=user_id,
                    updated_values=updated_values,
                ) from err

            raise  # not due to name duplication

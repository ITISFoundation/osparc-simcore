import contextlib

import sqlalchemy as sa
from aiohttp import web
from models_library.users import GroupID, UserBillingDetails, UserID, UserPermission
from simcore_postgres_database.models.groups import groups, user_to_groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import UserStatus, users
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesNotFoundError,
    GroupExtraPropertiesRepo,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from simcore_postgres_database.utils_users import UsersRepo
from simcore_service_webserver.users.exceptions import UserNotFoundError
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from ..db.plugin import get_asyncpg_engine
from .exceptions import BillingDetailsNotFoundError

_ALL = None


async def get_user_or_raise(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
    return_column_names: list[str] | None = _ALL,
) -> Row:
    if return_column_names == _ALL:
        return_column_names = list(users.columns.keys())

    assert return_column_names is not None  # nosec
    assert set(return_column_names).issubset(users.columns.keys())  # nosec

    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.stream(
            sa.select(*(users.columns[name] for name in return_column_names)).where(
                users.c.id == user_id
            )
        )
        row = await result.first()
        if row is None:
            raise UserNotFoundError(uid=user_id)
        return row


async def get_users_ids_in_group(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    group_id: GroupID,
) -> set[UserID]:
    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.stream(
            sa.select(user_to_groups.c.uid).where(user_to_groups.c.gid == group_id)
        )
        return {row.uid async for row in result}


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
                await GroupExtraPropertiesRepo.get_aggregated_properties_for_user_v2(
                    engine, conn, user_id=user_id, product_name=product_name
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
            .values(status=UserStatus.EXPIRED)
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
            users.update().values(status=new_status).where(users.c.id == user_id)
        )


async def search_users_and_get_profile(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    email_like: str,
) -> list[Row]:

    users_alias = sa.alias(users, name="users_alias")

    invited_by = (
        sa.select(users_alias.c.name)
        .where(users_pre_registration_details.c.created_by == users_alias.c.id)
        .label("invited_by")
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        columns = (
            users.c.first_name,
            users.c.last_name,
            users.c.email,
            users.c.phone,
            users_pre_registration_details.c.pre_email,
            users_pre_registration_details.c.pre_first_name,
            users_pre_registration_details.c.pre_last_name,
            users_pre_registration_details.c.institution,
            users_pre_registration_details.c.pre_phone,
            users_pre_registration_details.c.address,
            users_pre_registration_details.c.city,
            users_pre_registration_details.c.state,
            users_pre_registration_details.c.postal_code,
            users_pre_registration_details.c.country,
            users_pre_registration_details.c.user_id,
            users_pre_registration_details.c.extras,
            users.c.status,
            invited_by,
        )

        left_outer_join = (
            sa.select(*columns)
            .select_from(
                users_pre_registration_details.outerjoin(
                    users, users.c.id == users_pre_registration_details.c.user_id
                )
            )
            .where(users_pre_registration_details.c.pre_email.like(email_like))
        )
        right_outer_join = (
            sa.select(*columns)
            .select_from(
                users.outerjoin(
                    users_pre_registration_details,
                    users.c.id == users_pre_registration_details.c.user_id,
                )
            )
            .where(users.c.email.like(email_like))
        )

        result = await conn.stream(sa.union(left_outer_join, right_outer_join))
        return [row async for row in result]


async def get_user_products(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    user_id: UserID,
) -> list[Row]:
    async with pass_or_acquire_connection(engine, connection) as conn:
        product_name_subq = (
            sa.select(products.c.name)
            .where(products.c.group_id == groups.c.gid)
            .label("product_name")
        )
        products_gis_subq = sa.select(products.c.group_id).distinct().subquery()
        query = (
            sa.select(
                groups.c.gid,
                product_name_subq,
            )
            .select_from(
                users.join(user_to_groups, user_to_groups.c.uid == users.c.id).join(
                    groups,
                    (groups.c.gid == user_to_groups.c.gid)
                    & groups.c.gid.in_(products_gis_subq),
                )
            )
            .where(users.c.id == user_id)
            .order_by(groups.c.gid)
        )
        result = await conn.stream(query)
        return [row async for row in result]


async def new_user_details(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    email: str,
    created_by: UserID,
    **other_values,
) -> None:
    async with transaction_context(engine, connection) as conn:
        await conn.execute(
            sa.insert(users_pre_registration_details).values(
                created_by=created_by, pre_email=email, **other_values
            )
        )


async def get_user_billing_details(
    engine: AsyncEngine, connection: AsyncConnection | None = None, *, user_id: UserID
) -> UserBillingDetails:
    """
    Raises:
        BillingDetailsNotFoundError
    """
    async with pass_or_acquire_connection(engine, connection) as conn:
        query = UsersRepo.get_billing_details_query(user_id=user_id)
        result = await conn.stream(query)
        row = await result.fetchone()
        if not row:
            raise BillingDetailsNotFoundError(user_id=user_id)
        return UserBillingDetails.model_validate(row)

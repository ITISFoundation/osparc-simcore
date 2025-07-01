import contextlib
import logging
from typing import Any, cast

import sqlalchemy as sa
from aiohttp import web
from common_library.exclude import Unset, is_unset
from common_library.users_enums import AccountRequestStatus, UserRole
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
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_postgres_database.utils import as_postgres_sql_query_str
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
from ._common.models import FullNameDict, ToUserUpdateDB
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


#
# PRE-REGISTRATION
#


async def create_user_pre_registration(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    email: str,
    created_by: UserID | None = None,
    product_name: ProductName,
    link_to_existing_user: bool = True,
    **other_values,
) -> int:
    """Creates a user pre-registration entry.

    Args:
        engine: Database engine
        connection: Optional existing connection
        email: Email address for the pre-registration
        created_by: ID of the user creating the pre-registration (None for anonymous)
        product_name: Product name the user is requesting access to
        link_to_existing_user: Whether to link the pre-registration to an existing user with the same email
        **other_values: Additional values to insert in the pre-registration entry

    Returns:
        ID of the created pre-registration
    """
    async with transaction_context(engine, connection) as conn:
        # If link_to_existing_user is True, try to find a matching user
        user_id = None
        if link_to_existing_user:
            result = await conn.execute(
                sa.select(users.c.id).where(users.c.email == email)
            )
            user = result.one_or_none()
            if user:
                user_id = user.id

        # Insert the pre-registration record
        values = {
            "pre_email": email,
            "product_name": product_name,
            **other_values,
        }

        # Only add created_by if not None
        if created_by is not None:
            values["created_by"] = created_by

        # Add user_id if found
        if user_id is not None:
            values["user_id"] = user_id

        result = await conn.execute(
            sa.insert(users_pre_registration_details)
            .values(**values)
            .returning(users_pre_registration_details.c.id)
        )
        pre_registration_id: int = result.scalar_one()
        return pre_registration_id


async def list_user_pre_registrations(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    filter_by_pre_email: str | None = None,
    filter_by_product_name: ProductName | Unset = Unset.VALUE,
    filter_by_account_request_status: AccountRequestStatus | None = None,
    pagination_limit: int = 50,
    pagination_offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Lists user pre-registrations with optional filters.

    Args:
        engine: Database engine
        connection: Optional existing connection
        filter_by_pre_email: Filter by email pattern (SQL LIKE pattern)
        filter_by_product_name: Filter by product name
        filter_by_account_request_status: Filter by account request status
        pagination_limit: Maximum number of results to return
        pagination_offset: Number of results to skip (for pagination)

    Returns:
        Tuple of (list of pre-registration records, total count)
    """
    # Base query conditions
    where_conditions = []

    # Apply filters if provided
    if filter_by_pre_email is not None:
        where_conditions.append(
            users_pre_registration_details.c.pre_email.ilike(f"%{filter_by_pre_email}%")
        )

    if not is_unset(filter_by_product_name):
        where_conditions.append(
            users_pre_registration_details.c.product_name == filter_by_product_name
        )

    if filter_by_account_request_status is not None:
        where_conditions.append(
            users_pre_registration_details.c.account_request_status
            == filter_by_account_request_status
        )

    # Combine conditions
    where_clause = sa.and_(*where_conditions) if where_conditions else sa.true()

    # Create an alias for the users table for the created_by join
    creator_users_alias = sa.alias(users, name="creator")
    reviewer_users_alias = sa.alias(users, name="reviewer")

    # Count query for pagination
    count_query = (
        sa.select(sa.func.count().label("total"))
        .select_from(users_pre_registration_details)
        .where(where_clause)
    )

    # Main query to get pre-registration data
    main_query = (
        sa.select(
            users_pre_registration_details.c.id,
            users_pre_registration_details.c.user_id,
            users_pre_registration_details.c.pre_email,
            users_pre_registration_details.c.pre_first_name,
            users_pre_registration_details.c.pre_last_name,
            users_pre_registration_details.c.pre_phone,
            users_pre_registration_details.c.institution,
            users_pre_registration_details.c.address,
            users_pre_registration_details.c.city,
            users_pre_registration_details.c.state,
            users_pre_registration_details.c.postal_code,
            users_pre_registration_details.c.country,
            users_pre_registration_details.c.product_name,
            users_pre_registration_details.c.account_request_status,
            users_pre_registration_details.c.extras,
            users_pre_registration_details.c.created,
            users_pre_registration_details.c.modified,
            users_pre_registration_details.c.created_by,
            creator_users_alias.c.name.label("created_by_name"),
            users_pre_registration_details.c.account_request_reviewed_by,
            reviewer_users_alias.c.name.label("reviewed_by_name"),
            users_pre_registration_details.c.account_request_reviewed_at,
        )
        .select_from(
            users_pre_registration_details.outerjoin(
                creator_users_alias,
                users_pre_registration_details.c.created_by == creator_users_alias.c.id,
            ).outerjoin(
                reviewer_users_alias,
                users_pre_registration_details.c.account_request_reviewed_by
                == reviewer_users_alias.c.id,
            )
        )
        .where(where_clause)
        .order_by(
            users_pre_registration_details.c.created.desc(),
            users_pre_registration_details.c.pre_email,
        )
        .limit(pagination_limit)
        .offset(pagination_offset)
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        # Get total count
        count_result = await conn.execute(count_query)
        total_count = count_result.scalar_one()

        # Get pre-registration records
        result = await conn.execute(main_query)
        records = result.mappings().all()

    return cast(list[dict[str, Any]], list(records)), total_count


async def review_user_pre_registration(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    pre_registration_id: int,
    reviewed_by: UserID,
    new_status: AccountRequestStatus,
    invitation_extras: dict[str, Any] | None = None,
) -> None:
    """Updates the account request status of a pre-registered user.

    Args:
        engine: The database engine
        connection: Optional existing connection
        pre_registration_id: ID of the pre-registration record
        reviewed_by: ID of the user who reviewed the request
        new_status: New status (APPROVED or REJECTED)
        invitation_extras: Optional invitation data to store in extras field
    """
    if new_status not in (AccountRequestStatus.APPROVED, AccountRequestStatus.REJECTED):
        msg = f"Invalid status for review: {new_status}. Must be APPROVED or REJECTED."
        raise ValueError(msg)

    async with transaction_context(engine, connection) as conn:
        # Base update values
        update_values = {
            "account_request_status": new_status,
            "account_request_reviewed_by": reviewed_by,
            "account_request_reviewed_at": sa.func.now(),
        }

        # Add invitation extras to the existing extras if provided
        if invitation_extras is not None:
            assert list(invitation_extras.keys()) == "invitation"  # nosec

            # Get the current extras first
            current_extras_result = await conn.execute(
                sa.select(users_pre_registration_details.c.extras).where(
                    users_pre_registration_details.c.id == pre_registration_id
                )
            )
            current_extras_row = current_extras_result.one_or_none()
            current_extras = (
                current_extras_row.extras
                if current_extras_row and current_extras_row.extras
                else {}
            )

            # Merge with invitation extras
            merged_extras = {**current_extras, **invitation_extras}
            update_values["extras"] = merged_extras

        await conn.execute(
            users_pre_registration_details.update()
            .values(**update_values)
            .where(users_pre_registration_details.c.id == pre_registration_id)
        )


#
# PRE AND REGISTERED USERS
#


async def search_merged_pre_and_registered_users(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    email_like: str,
    product_name: ProductName | None = None,
) -> list[Row]:
    users_alias = sa.alias(users, name="users_alias")

    invited_by = (
        sa.select(
            users_alias.c.name,
        )
        .where(users_pre_registration_details.c.created_by == users_alias.c.id)
        .label("invited_by")
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        columns = (
            users_pre_registration_details.c.id,
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
            users_pre_registration_details.c.account_request_status,
            users_pre_registration_details.c.account_request_reviewed_by,
            users_pre_registration_details.c.account_request_reviewed_at,
            users.c.status,
            invited_by,
            users_pre_registration_details.c.created,
        )

        join_condition = users.c.id == users_pre_registration_details.c.user_id
        if product_name:
            join_condition = join_condition & (
                users_pre_registration_details.c.product_name == product_name
            )

        left_outer_join = (
            sa.select(*columns)
            .select_from(
                users_pre_registration_details.outerjoin(users, join_condition)
            )
            .where(users_pre_registration_details.c.pre_email.like(email_like))
        )
        right_outer_join = (
            sa.select(*columns)
            .select_from(
                users.outerjoin(
                    users_pre_registration_details,
                    join_condition,
                )
            )
            .where(users.c.email.like(email_like))
        )

        result = await conn.stream(sa.union(left_outer_join, right_outer_join))
        return [row async for row in result]


async def list_merged_pre_and_registered_users(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    product_name: ProductName,
    filter_any_account_request_status: list[AccountRequestStatus] | None = None,
    filter_include_deleted: bool = False,
    pagination_limit: int = 50,
    pagination_offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Retrieves and merges users from both users and pre-registration tables.

    This returns:
    1. Users who are registered with the platform (in users table)
    2. Users who are pre-registered (in users_pre_registration_details table)
    3. Users who are both registered and pre-registered

    Args:
        engine: Database engine
        connection: Optional existing connection
        product_name: Product name to filter by
        filter_any_account_request_status: If provided, only returns users with account request status in this list
            (only pre-registered users with any of these statuses will be included)
        filter_include_deleted: Whether to include deleted users
        pagination_limit: Maximum number of results to return
        pagination_offset: Number of results to skip (for pagination)

    Returns:
        Tuple of (list of merged user data, total count)
    """
    # Base where conditions for both queries
    pre_reg_where = [users_pre_registration_details.c.product_name == product_name]
    users_where = []

    # Add account request status filter if specified
    if filter_any_account_request_status:
        pre_reg_where.append(
            users_pre_registration_details.c.account_request_status.in_(
                filter_any_account_request_status
            )
        )

    # Add filter for deleted users
    if not filter_include_deleted:
        users_where.append(users.c.status != UserStatus.DELETED)

    # Query for pre-registered users that are not yet in the users table
    # We need to left join with users to identify if the pre-registered user is already in the system
    pre_reg_query = (
        sa.select(
            users_pre_registration_details.c.id,
            users_pre_registration_details.c.pre_email.label("email"),
            users_pre_registration_details.c.pre_first_name.label("first_name"),
            users_pre_registration_details.c.pre_last_name.label("last_name"),
            users_pre_registration_details.c.pre_phone.label("phone"),
            users_pre_registration_details.c.institution,
            users_pre_registration_details.c.address,
            users_pre_registration_details.c.city,
            users_pre_registration_details.c.state,
            users_pre_registration_details.c.postal_code,
            users_pre_registration_details.c.country,
            users_pre_registration_details.c.user_id.label("pre_reg_user_id"),
            users_pre_registration_details.c.extras,
            users_pre_registration_details.c.created,
            users_pre_registration_details.c.account_request_status,
            users_pre_registration_details.c.account_request_reviewed_by,
            users_pre_registration_details.c.account_request_reviewed_at,
            users.c.id.label("user_id"),
            users.c.name.label("user_name"),
            users.c.status,
            # Use created_by directly instead of a subquery
            users_pre_registration_details.c.created_by.label("created_by"),
            sa.literal(True).label("is_pre_registered"),
        )
        .select_from(
            users_pre_registration_details.outerjoin(
                users, users_pre_registration_details.c.user_id == users.c.id
            )
        )
        .where(sa.and_(*pre_reg_where))
    )

    # Query for users that are associated with the product through groups
    users_query = (
        sa.select(
            sa.literal(None).label("id"),
            users.c.email,
            users.c.first_name,
            users.c.last_name,
            users.c.phone,
            sa.literal(None).label("institution"),
            sa.literal(None).label("address"),
            sa.literal(None).label("city"),
            sa.literal(None).label("state"),
            sa.literal(None).label("postal_code"),
            sa.literal(None).label("country"),
            sa.literal(None).label("pre_reg_user_id"),
            sa.literal(None).label("extras"),
            users.c.created_at.label("created"),
            sa.literal(None).label("account_request_status"),
            sa.literal(None).label("account_request_reviewed_by"),
            sa.literal(None).label("account_request_reviewed_at"),
            users.c.id.label("user_id"),
            users.c.name.label("user_name"),
            users.c.status,
            # Match the created_by field from the pre_reg query
            sa.literal(None).label("created_by"),
            sa.literal(False).label("is_pre_registered"),
        )
        .select_from(
            users.join(user_to_groups, user_to_groups.c.uid == users.c.id)
            .join(groups, groups.c.gid == user_to_groups.c.gid)
            .join(products, products.c.group_id == groups.c.gid)
        )
        .where(sa.and_(products.c.name == product_name, *users_where))
    )

    # If filtering by account request status, we only want pre-registered users with any of those statuses
    # No need to union with regular users as they don't have account_request_status
    merged_query: sa.sql.Select | sa.sql.CompoundSelect
    if filter_any_account_request_status:
        merged_query = pre_reg_query
    else:
        merged_query = pre_reg_query.union_all(users_query)

    # Add distinct on email to eliminate duplicates
    merged_query_subq = merged_query.subquery()
    distinct_query = (
        sa.select(merged_query_subq)
        .select_from(merged_query_subq)
        .distinct(merged_query_subq.c.email)
        .order_by(
            merged_query_subq.c.email,
            # Prioritize pre-registration records if duplicate emails exist
            merged_query_subq.c.is_pre_registered.desc(),
            merged_query_subq.c.created.desc(),
        )
        .limit(pagination_limit)
        .offset(pagination_offset)
    )

    # Count query (for pagination)
    count_query = sa.select(sa.func.count().label("total")).select_from(
        sa.select(merged_query_subq.c.email)
        .select_from(merged_query_subq)
        .distinct()
        .subquery()
    )

    _logger.debug(
        "%s\n%s\n%s\n%s",
        "-" * 100,
        as_postgres_sql_query_str(distinct_query),
        "-" * 100,
        as_postgres_sql_query_str(count_query),
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        # Get total count
        count_result = await conn.execute(count_query)
        total_count = count_result.scalar_one()

        # Get user records
        result = await conn.execute(distinct_query)
        records = result.mappings().all()

    return cast(list[dict[str, Any]], records), total_count

import logging
from typing import Any, cast

import sqlalchemy as sa
from common_library.exclude import Unset, is_unset
from common_library.users_enums import AccountRequestStatus
from models_library.products import ProductName
from models_library.users import (
    UserID,
)
from simcore_postgres_database.models.groups import groups, user_to_groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import UserStatus, users
from simcore_postgres_database.models.users_details import (
    users_pre_registration_details,
)
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

_logger = logging.getLogger(__name__)


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
            result = await conn.execute(sa.select(users.c.id).where(users.c.email == email))
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
            sa.insert(users_pre_registration_details).values(**values).returning(users_pre_registration_details.c.id)
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
        where_conditions.append(users_pre_registration_details.c.pre_email.ilike(f"%{filter_by_pre_email}%"))

    if not is_unset(filter_by_product_name):
        where_conditions.append(users_pre_registration_details.c.product_name == filter_by_product_name)

    if filter_by_account_request_status is not None:
        where_conditions.append(
            users_pre_registration_details.c.account_request_status == filter_by_account_request_status
        )

    # Combine conditions
    where_clause = sa.and_(*where_conditions) if where_conditions else sa.true()

    # Create an alias for the users table for the created_by join
    creator_users_alias = sa.alias(users, name="creator")
    reviewer_users_alias = sa.alias(users, name="reviewer")

    # Count query for pagination
    count_query = (
        sa.select(sa.func.count().label("total")).select_from(users_pre_registration_details).where(where_clause)
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
                users_pre_registration_details.c.account_request_reviewed_by == reviewer_users_alias.c.id,
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
            assert list(invitation_extras.keys()) == ["invitation"]  # nosec

            # Get the current extras first
            current_extras_result = await conn.execute(
                sa.select(users_pre_registration_details.c.extras).where(
                    users_pre_registration_details.c.id == pre_registration_id
                )
            )
            current_extras_row = current_extras_result.one_or_none()
            current_extras = current_extras_row.extras if current_extras_row and current_extras_row.extras else {}

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


def _create_account_request_reviewed_by_username_subquery() -> Any:
    """Creates a reusable subquery for getting reviewer username by ID."""
    reviewer_alias = sa.alias(users, name="reviewer_alias")
    return (
        sa.select(
            reviewer_alias.c.name,
        )
        .where(users_pre_registration_details.c.account_request_reviewed_by == reviewer_alias.c.id)
        .label("account_request_reviewed_by_username")
    )


def _build_left_outer_join_query(
    email_like: str | None,
    product_name: ProductName | None,
    columns: tuple,
) -> sa.sql.Select | None:
    left_where_conditions = []
    if email_like is not None:
        left_where_conditions.append(users_pre_registration_details.c.pre_email.like(email_like))
    join_condition = users.c.id == users_pre_registration_details.c.user_id
    if product_name:
        join_condition = join_condition & (users_pre_registration_details.c.product_name == product_name)
    left_outer_join = sa.select(*columns).select_from(users_pre_registration_details.outerjoin(users, join_condition))

    return left_outer_join.where(sa.and_(*left_where_conditions)) if left_where_conditions else None


def _build_right_outer_join_query(
    email_like: str | None,
    user_name_like: str | None,
    primary_group_id: int | None,
    product_name: ProductName | None,
    columns: tuple,
) -> sa.sql.Select | None:
    right_where_conditions = []
    if email_like is not None:
        right_where_conditions.append(users.c.email.like(email_like))
    if user_name_like is not None:
        right_where_conditions.append(users.c.name.like(user_name_like))
    if primary_group_id is not None:
        right_where_conditions.append(users.c.primary_gid == primary_group_id)
    join_condition = users.c.id == users_pre_registration_details.c.user_id
    if product_name:
        join_condition = join_condition & (users_pre_registration_details.c.product_name == product_name)
    right_outer_join = sa.select(*columns).select_from(
        users.outerjoin(
            users_pre_registration_details,
            join_condition,
        )
    )

    return right_outer_join.where(sa.and_(*right_where_conditions)) if right_where_conditions else None


async def search_merged_pre_and_registered_users(
    engine: AsyncEngine,
    connection: AsyncConnection | None = None,
    *,
    filter_by_email_like: str | None = None,
    filter_by_user_name_like: str | None = None,
    filter_by_primary_group_id: int | None = None,
    product_name: ProductName | None = None,
) -> list[Row]:
    """Searches and merges users from both users and pre-registration tables"""
    users_alias = sa.alias(users, name="users_alias")

    invited_by = (
        sa.select(
            users_alias.c.name,
        )
        .where(users_pre_registration_details.c.created_by == users_alias.c.id)
        .label("invited_by")
    )

    account_request_reviewed_by_username = _create_account_request_reviewed_by_username_subquery()

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
        users_pre_registration_details.c.user_id.label("pre_reg_user_id"),
        users_pre_registration_details.c.extras,
        users_pre_registration_details.c.account_request_status,
        users_pre_registration_details.c.account_request_reviewed_by,
        users_pre_registration_details.c.account_request_reviewed_at,
        invited_by,
        account_request_reviewed_by_username,  # account_request_reviewed_by converted to username
        users_pre_registration_details.c.created,
        # NOTE: some users have no pre-registration details (e.g. s4l-lite)
        users.c.id.label("user_id"),  # real user_id from users table
        users.c.name.label("user_name"),
        users.c.primary_gid.label("user_primary_group_id"),
        users.c.status,
    )

    left_outer_join = _build_left_outer_join_query(
        filter_by_email_like,
        product_name,
        columns,
    )
    right_outer_join = _build_right_outer_join_query(
        filter_by_email_like,
        filter_by_user_name_like,
        filter_by_primary_group_id,
        product_name,
        columns,
    )

    queries = []
    if left_outer_join is not None:
        queries.append(left_outer_join)
    if right_outer_join is not None:
        queries.append(right_outer_join)

    if not queries:
        # No search criteria provided, return empty result
        return []

    final_query = queries[0] if len(queries) == 1 else sa.union(*queries)

    async with pass_or_acquire_connection(engine, connection) as conn:
        result = await conn.execute(final_query)
        return result.fetchall()


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
            users_pre_registration_details.c.account_request_status.in_(filter_any_account_request_status)
        )

    # Add filter for deleted users
    if not filter_include_deleted:
        users_where.append(users.c.status != UserStatus.DELETED)

    # Create subquery for reviewer username
    account_request_reviewed_by_username = _create_account_request_reviewed_by_username_subquery()

    # Query for pre-registered users
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
            users.c.primary_gid.label("user_primary_group_id"),
            users.c.status,
            # Use created_by directly instead of a subquery
            users_pre_registration_details.c.created_by.label("created_by"),
            account_request_reviewed_by_username,
            sa.literal_column("true").label("is_pre_registered"),
        )
        .select_from(
            users_pre_registration_details.outerjoin(users, users_pre_registration_details.c.user_id == users.c.id)
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
            users.c.primary_gid.label("user_primary_group_id"),
            users.c.status,
            # Match the created_by field from the pre_reg query
            sa.literal(None).label("created_by"),
            sa.literal(None).label("account_request_reviewed_by_username"),
            sa.literal_column("false").label("is_pre_registered"),
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
        sa.select(merged_query_subq.c.email).select_from(merged_query_subq).distinct().subquery()
    )

    async with pass_or_acquire_connection(engine, connection) as conn:
        # Get total count
        count_result = await conn.execute(count_query)
        total_count = count_result.scalar_one()

        # Get user records
        result = await conn.execute(distinct_query)
        records = result.mappings().all()

    return cast(list[dict[str, Any]], records), total_count

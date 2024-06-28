import sqlalchemy as sa
from models_library.products import ProductName
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER, array_agg
from sqlalchemy.sql import and_, or_
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.selectable import Select

from ..tables import services_access_rights, services_meta_data, user_to_groups, users


def list_services_stmt(
    *,
    gids: list[int] | None = None,
    execute_access: bool | None = None,
    write_access: bool | None = None,
    combine_access_with_and: bool | None = True,
    product_name: str | None = None,
) -> Select:
    stmt = sa.select(services_meta_data)
    if gids or execute_access or write_access:
        conditions = []

        # access rights
        logic_operator = and_ if combine_access_with_and else or_
        default = bool(combine_access_with_and)

        access_query_part = logic_operator(
            services_access_rights.c.execute_access if execute_access else default,
            services_access_rights.c.write_access if write_access else default,
        )
        conditions.append(access_query_part)

        # on groups
        if gids:
            conditions.append(
                or_(*[services_access_rights.c.gid == gid for gid in gids])
            )

        # and product name
        if product_name:
            conditions.append(services_access_rights.c.product_name == product_name)

        stmt = (
            sa.select(
                [services_meta_data],
            )
            .distinct(services_meta_data.c.key, services_meta_data.c.version)
            .select_from(services_meta_data.join(services_access_rights))
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(services_meta_data.c.key, services_meta_data.c.version)

    return stmt


def _version(column_or_value):
    # converts version value string to array[integer] that can be compared
    # i.e. '1.2.3' -> [1, 2, 3]
    return sa.func.string_to_array(column_or_value, ".").cast(ARRAY(INTEGER))


class AccessRightsClauses:
    can_execute = services_access_rights.c.execute_access
    can_read = (
        services_access_rights.c.execute_access | services_access_rights.c.write_access
    )
    can_edit = services_access_rights.c.write_access
    is_owner = (
        services_access_rights.c.execute_access & services_access_rights.c.write_access
    )


def batch_get_services(
    product_name: ProductName, selection: list[tuple[ServiceKey, ServiceVersion]]
):
    return (
        sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version,
            users.c.email.label("owner_email"),
            services_meta_data.c.name,
            services_meta_data.c.description,
            services_meta_data.c.thumbnail,
        )
        .select_from(
            services_meta_data.join(
                services_access_rights,
                (services_meta_data.c.key == services_access_rights.c.key)
                & (services_meta_data.c.version == services_access_rights.c.version)
                & (services_access_rights.c.product_name == product_name),
            ).join(users, services_meta_data.c.owner == users.c.id)
        )
        .where(
            or_(
                (services_meta_data.c.key == key)
                & (services_meta_data.c.version == version)
                for key, version in selection
            )
        )
    )


def total_count_stmt(
    *,
    product_name: ProductName,
    user_id: UserID,
    access_rights: sa.sql.ClauseElement,
):
    return (
        sa.select(func.count(sa.distinct(services_meta_data.c.key)))
        .select_from(
            services_meta_data.join(
                services_access_rights,
                (services_meta_data.c.key == services_access_rights.c.key)
                & (services_meta_data.c.version == services_access_rights.c.version)
                & (services_access_rights.c.product_name == product_name),
            ).join(
                user_to_groups,
                (user_to_groups.c.gid == services_access_rights.c.gid)
                & (user_to_groups.c.uid == user_id),
            )
        )
        .where(access_rights)
    )


def list_services_with_history_stmt(
    *,
    product_name: ProductName,
    user_id: UserID,
    access_rights: sa.sql.ClauseElement,
    limit: int | None,
    offset: int | None,
):
    #
    # Common Table Expression (CTE) to select distinct service names with pagination.
    # This allows limiting the subquery to the required pagination instead of paginating at the last query.
    # SEE https://learnsql.com/blog/cte-with-examples/
    #
    cte = (
        sa.select(services_meta_data.c.key)
        .distinct()
        .select_from(
            services_meta_data.join(
                services_access_rights,
                (services_meta_data.c.key == services_access_rights.c.key)
                & (services_meta_data.c.version == services_access_rights.c.version)
                & (services_access_rights.c.product_name == product_name),
            ).join(
                user_to_groups,
                (user_to_groups.c.gid == services_access_rights.c.gid)
                & (user_to_groups.c.uid == user_id),
            )
        )
        .where(access_rights)
        .order_by(services_meta_data.c.key)  # NOTE: add here the order
        .limit(limit)
        .offset(offset)
        .cte("paginated_services")
    )

    subquery = (
        sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version,
            services_meta_data.c.deprecated,
            services_meta_data.c.created,
        )
        .select_from(
            services_meta_data.join(
                cte,
                services_meta_data.c.key == cte.c.key,
            )
            # joins because access-rights might change per version
            .join(
                services_access_rights,
                (services_meta_data.c.key == services_access_rights.c.key)
                & (services_meta_data.c.version == services_access_rights.c.version)
                & (services_access_rights.c.product_name == product_name),
            ).join(
                user_to_groups,
                (user_to_groups.c.gid == services_access_rights.c.gid)
                & (user_to_groups.c.uid == user_id),
            )
        )
        .where(access_rights)
        .order_by(
            services_meta_data.c.key,
            sa.desc(_version(services_meta_data.c.version)),  # latest version first
        )
        .subquery()
    )

    return sa.select(
        subquery.c.key,
        array_agg(
            func.json_build_object(
                "version",
                subquery.c.version,
                "deprecated",
                subquery.c.deprecated,
                "created",
                subquery.c.created,
            )
        ).label("history"),
    ).group_by(subquery.c.key)

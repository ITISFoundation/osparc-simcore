import sqlalchemy as sa
from models_library.products import ProductName
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER, array_agg
from sqlalchemy.sql import and_, or_
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.selectable import Select

from ..tables import (
    services_access_rights,
    services_compatibility,
    services_meta_data,
    user_to_groups,
    users,
)


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
                services_meta_data,
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


def _join_services_with_access_rights():
    # services_meta_data | services_access_rights | user_to_groups
    return services_meta_data.join(
        services_access_rights,
        (services_meta_data.c.key == services_access_rights.c.key)
        & (services_meta_data.c.version == services_access_rights.c.version),
    ).join(
        user_to_groups,
        (user_to_groups.c.gid == services_access_rights.c.gid),
    )


def _has_access_rights(
    product_name: ProductName,
    user_id: UserID,
    access_rights: sa.sql.ClauseElement,
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    return (
        (services_meta_data.c.key == service_key)
        & (services_meta_data.c.version == service_version)
        & (user_to_groups.c.uid == user_id)
        & (services_access_rights.c.product_name == product_name)
        & access_rights
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


def list_latest_services_with_history_stmt(
    *,
    product_name: ProductName,
    user_id: UserID,
    access_rights: sa.sql.ClauseElement,
    limit: int | None,
    offset: int | None,
):
    # get all distinct services key fitting a page
    # and its corresponding latest version
    cte = (
        sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version.label("latest_version"),
        )
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
        .order_by(
            services_meta_data.c.key,
            sa.desc(_version(services_meta_data.c.version)),  # latest first
        )
        .distinct(services_meta_data.c.key)  # get only first
        .limit(limit)
        .offset(offset)
        .cte("cte")
    )

    # get all information of latest's services listed in CTE
    latest_query = (
        sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version,
            users.c.email.label("owner_email"),
            services_meta_data.c.name,
            services_meta_data.c.description,
            services_meta_data.c.thumbnail,
            services_meta_data.c.version_display,
            services_meta_data.c.classifiers,
            services_meta_data.c.created,
            services_meta_data.c.modified,
            services_meta_data.c.deprecated,
            services_meta_data.c.quality,
        )
        .join(
            cte,
            (services_meta_data.c.key == cte.c.key)
            & (services_meta_data.c.version == cte.c.latest_version),
        )
        # NOTE: owner can be NULL
        .join(
            user_to_groups,
            services_meta_data.c.owner == user_to_groups.c.gid,
            isouter=True,
        )
        .join(users, user_to_groups.c.uid == users.c.id, isouter=True)
        .subquery("latest_sq")
    )

    # get history for every unique service-key in CTE
    _accessible_sq = (
        sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version,
        )
        .distinct()
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
            )
            .join(
                user_to_groups,
                (user_to_groups.c.gid == services_access_rights.c.gid)
                & (user_to_groups.c.uid == user_id),
            )
            .outerjoin(
                services_compatibility,
                (services_meta_data.c.key == services_compatibility.c.key)
                & (services_meta_data.c.version == services_compatibility.c.version),
            )
        )
        .where(access_rights)
        .subquery("accessible_sq")
    )

    history_subquery = (
        sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version,
            services_meta_data.c.version_display,
            services_meta_data.c.deprecated,
            services_meta_data.c.created,
            services_compatibility.c.custom_policy,  # CompatiblePolicyDict | None
        )
        .select_from(
            services_meta_data.join(
                _accessible_sq,
                (services_meta_data.c.key == _accessible_sq.c.key)
                & (services_meta_data.c.version == _accessible_sq.c.version),
            ).outerjoin(
                services_compatibility,
                (services_meta_data.c.key == services_compatibility.c.key)
                & (services_meta_data.c.version == services_compatibility.c.version),
            )
        )
        .order_by(
            services_meta_data.c.key,
            sa.desc(_version(services_meta_data.c.version)),  # latest version first
        )
        .subquery("history_sq")
    )

    return (
        sa.select(
            latest_query.c.key,
            latest_query.c.version,
            # display
            latest_query.c.name,
            latest_query.c.description,
            latest_query.c.thumbnail,
            latest_query.c.version_display,
            # ownership
            latest_query.c.owner_email,
            # tags
            latest_query.c.classifiers,
            latest_query.c.quality,
            # lifetime
            latest_query.c.created,
            latest_query.c.modified,
            latest_query.c.deprecated,
            # releases (NOTE: at some points we should limit this list?)
            array_agg(
                func.json_build_object(
                    "version",
                    history_subquery.c.version,
                    "version_display",
                    history_subquery.c.version_display,
                    "deprecated",
                    history_subquery.c.deprecated,
                    "created",
                    history_subquery.c.created,
                    "compatibility_policy",  # NOTE: this is the `policy`
                    history_subquery.c.custom_policy,
                )
            ).label("history"),
        )
        .join(
            history_subquery,
            latest_query.c.key == history_subquery.c.key,
        )
        .group_by(
            history_subquery.c.key,
            latest_query.c.key,
            latest_query.c.version,
            latest_query.c.owner_email,
            latest_query.c.name,
            latest_query.c.description,
            latest_query.c.thumbnail,
            latest_query.c.version_display,
            latest_query.c.classifiers,
            latest_query.c.created,
            latest_query.c.modified,
            latest_query.c.deprecated,
            latest_query.c.quality,
        )
        .order_by(history_subquery.c.key)
    )


def can_get_service_stmt(
    *,
    product_name: ProductName,
    user_id: UserID,
    access_rights: sa.sql.ClauseElement,
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    subquery = (
        sa.select(1)
        .select_from(_join_services_with_access_rights())
        .where(
            _has_access_rights(
                product_name=product_name,
                user_id=user_id,
                access_rights=access_rights,
                service_key=service_key,
                service_version=service_version,
            )
        )
        .limit(1)
    )

    return sa.select(sa.exists(subquery))


def get_service_stmt(
    *,
    product_name: ProductName,
    user_id: UserID,
    access_rights: sa.sql.ClauseElement,
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    owner_subquery = (
        sa.select(users.c.email)
        .select_from(user_to_groups.join(users, user_to_groups.c.uid == users.c.id))
        .where(user_to_groups.c.gid == services_meta_data.c.owner)
        .limit(1)
        .scalar_subquery()
    )

    return (
        sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version,
            # display
            services_meta_data.c.name,
            services_meta_data.c.description,
            services_meta_data.c.thumbnail,
            services_meta_data.c.version_display,
            # ownership
            owner_subquery.label("owner_email"),
            # tags
            services_meta_data.c.classifiers,
            services_meta_data.c.quality,
            # lifetime
            services_meta_data.c.created,
            services_meta_data.c.modified,
            services_meta_data.c.deprecated,
            # w/o releases history!
        )
        .select_from(_join_services_with_access_rights())
        .where(
            _has_access_rights(
                product_name=product_name,
                user_id=user_id,
                access_rights=access_rights,
                service_key=service_key,
                service_version=service_version,
            )
        )
        .limit(1)
    )


def get_service_history_stmt(
    *,
    product_name: ProductName,
    user_id: UserID,
    access_rights: sa.sql.ClauseElement,
    service_key: ServiceKey,
):

    _sq = (
        sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version,
            services_meta_data.c.version_display,
            services_meta_data.c.deprecated,
            services_meta_data.c.created,
            services_compatibility.c.custom_policy,  # CompatiblePolicyDict | None
        )
        .select_from(
            # joins because access-rights might change per version
            services_meta_data.join(
                services_access_rights,
                (services_meta_data.c.key == services_access_rights.c.key)
                & (services_meta_data.c.version == services_access_rights.c.version),
            )
            .join(
                user_to_groups,
                (user_to_groups.c.gid == services_access_rights.c.gid),
            )
            .outerjoin(
                services_compatibility,
                (services_meta_data.c.key == services_compatibility.c.key)
                & (services_meta_data.c.version == services_compatibility.c.version),
            )
        )
        .where(
            (services_meta_data.c.key == service_key)
            & (services_access_rights.c.product_name == product_name)
            & (user_to_groups.c.uid == user_id)
            & access_rights
        )
        .distinct()
    ).subquery()

    history_subquery = (
        sa.select(_sq)
        .order_by(
            sa.desc(_version(_sq.c.version)),  # latest version first
        )
        .alias("history_subquery")
    )

    return (
        sa.select(
            array_agg(
                func.json_build_object(
                    "version",
                    history_subquery.c.version,
                    "version_display",
                    history_subquery.c.version_display,
                    "deprecated",
                    history_subquery.c.deprecated,
                    "created",
                    history_subquery.c.created,
                    "compatibility_policy",  # NOTE: this is the `policy`
                    history_subquery.c.custom_policy,
                )
            ).label("history"),
        )
        .select_from(history_subquery)
        .group_by(history_subquery.c.key)
    )

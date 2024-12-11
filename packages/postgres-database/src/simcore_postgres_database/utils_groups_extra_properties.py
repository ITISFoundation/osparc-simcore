import datetime
import logging
import warnings
from dataclasses import dataclass, fields
from typing import Any

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from .models.groups import GroupType, groups, user_to_groups
from .models.groups_extra_properties import groups_extra_properties
from .utils_models import FromRowMixin
from .utils_repos import pass_or_acquire_connection

_logger = logging.getLogger(__name__)

_WARNING_FMSG = (
    f"{__name__}.{{}} uses aiopg which has been deprecated in this repo. Use {{}} instead. "
    "SEE https://github.com/ITISFoundation/osparc-simcore/issues/4529"
)


class GroupExtraPropertiesError(Exception):
    ...


class GroupExtraPropertiesNotFoundError(GroupExtraPropertiesError):
    ...


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupExtraProperties(FromRowMixin):
    group_id: int
    product_name: str
    internet_access: bool
    override_services_specifications: bool
    use_on_demand_clusters: bool
    enable_telemetry: bool
    created: datetime.datetime
    modified: datetime.datetime
    enable_efs: bool


async def _list_table_entries_ordered_by_group_type_stmt(
    user_id: int, product_name: str
):
    return (
        sa.select(
            groups_extra_properties,
            groups.c.type,
            sa.case(
                # NOTE: the ordering is important for the aggregation afterwards
                (groups.c.type == GroupType.EVERYONE, sa.literal(3)),
                (groups.c.type == GroupType.STANDARD, sa.literal(2)),
                (groups.c.type == GroupType.PRIMARY, sa.literal(1)),
                else_=sa.literal(4),
            ).label("type_order"),
        )
        .select_from(
            sa.join(
                sa.join(
                    groups_extra_properties,
                    user_to_groups,
                    groups_extra_properties.c.group_id == user_to_groups.c.gid,
                ),
                groups,
                groups_extra_properties.c.group_id == groups.c.gid,
            )
        )
        .where(
            (groups_extra_properties.c.product_name == product_name)
            & (user_to_groups.c.uid == user_id)
        )
        .alias()
    )


def _merge_extra_properties_booleans(
    instance1: GroupExtraProperties, instance2: GroupExtraProperties
) -> GroupExtraProperties:
    merged_properties: dict[str, Any] = {}
    for field in fields(instance1):
        value1 = getattr(instance1, field.name)
        value2 = getattr(instance2, field.name)

        if isinstance(value1, bool):
            merged_properties[field.name] = value1 or value2
        else:
            merged_properties[field.name] = value1
    return GroupExtraProperties(**merged_properties)  # pylint: disable=missing-kwoa


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupExtraPropertiesRepo:
    @staticmethod
    def _get_stmt(gid: int, product_name: str):
        return sa.select(groups_extra_properties).where(
            (groups_extra_properties.c.group_id == gid)
            & (groups_extra_properties.c.product_name == product_name)
        )

    @staticmethod
    async def get(
        connection: SAConnection, *, gid: int, product_name: str
    ) -> GroupExtraProperties:
        warnings.warn(
            _WARNING_FMSG.format("get", "get_v2"),
            DeprecationWarning,
            stacklevel=1,
        )

        query = GroupExtraPropertiesRepo._get_stmt(gid, product_name)
        result = await connection.execute(query)
        assert result  # nosec
        if row := await result.first():
            return GroupExtraProperties.from_row_proxy(row)
        msg = f"Properties for group {gid} not found"
        raise GroupExtraPropertiesNotFoundError(msg)

    @staticmethod
    async def get_v2(
        engine: AsyncEngine,
        connection: AsyncConnection | None = None,
        *,
        gid: int,
        product_name: str,
    ) -> GroupExtraProperties:
        async with pass_or_acquire_connection(engine, connection) as conn:
            query = GroupExtraPropertiesRepo._get_stmt(gid, product_name)
            result = await conn.stream(query)
            assert result  # nosec
            if row := await result.first():
                return GroupExtraProperties.from_orm(row)
            msg = f"Properties for group {gid} not found"
            raise GroupExtraPropertiesNotFoundError(msg)

    @staticmethod
    def _aggregate(rows, user_id, product_name):
        merged_standard_extra_properties = None
        for row in rows:
            group_extra_properties = GroupExtraProperties.from_row_proxy(row)
            match row.type:
                case GroupType.PRIMARY:
                    # this always has highest priority
                    return group_extra_properties
                case GroupType.STANDARD:
                    if merged_standard_extra_properties:
                        merged_standard_extra_properties = (
                            _merge_extra_properties_booleans(
                                merged_standard_extra_properties,
                                group_extra_properties,
                            )
                        )
                    else:
                        merged_standard_extra_properties = group_extra_properties
                case GroupType.EVERYONE:
                    # if there are standard properties, they take precedence
                    return (
                        merged_standard_extra_properties
                        if merged_standard_extra_properties
                        else group_extra_properties
                    )
                case _:
                    _logger.warning(
                        "Unexpected GroupType found in %s db table! Please adapt code here!",
                        groups_extra_properties.name,
                    )
        if merged_standard_extra_properties:
            return merged_standard_extra_properties
        msg = f"Properties for user {user_id} in {product_name} not found"
        raise GroupExtraPropertiesNotFoundError(msg)

    @staticmethod
    async def get_aggregated_properties_for_user(
        connection: SAConnection,
        *,
        user_id: int,
        product_name: str,
    ) -> GroupExtraProperties:
        warnings.warn(
            _WARNING_FMSG.format(
                "get_aggregated_properties_for_user",
                "get_aggregated_properties_for_user_v2",
            ),
            DeprecationWarning,
            stacklevel=1,
        )

        list_stmt = _list_table_entries_ordered_by_group_type_stmt(
            user_id=user_id, product_name=product_name
        )

        result = await connection.execute(
            sa.select(list_stmt).order_by(list_stmt.c.type_order)
        )
        assert result  # nosec

        rows: list[RowProxy] | None = await result.fetchall()
        assert rows is not None  # nosec

        return GroupExtraPropertiesRepo._aggregate(rows, user_id, product_name)

    @staticmethod
    async def get_aggregated_properties_for_user_v2(
        engine: AsyncEngine,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        product_name: str,
    ) -> GroupExtraProperties:
        async with pass_or_acquire_connection(engine, connection) as conn:

            list_stmt = _list_table_entries_ordered_by_group_type_stmt(
                user_id=user_id, product_name=product_name
            )
            result = await conn.stream(
                sa.select(list_stmt).order_by(list_stmt.c.type_order)
            )
            rows = [row async for row in result]
            return GroupExtraPropertiesRepo._aggregate(rows, user_id, product_name)

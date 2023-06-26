import datetime
from dataclasses import dataclass, fields

import sqlalchemy
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.groups_extra_properties import (
    groups_extra_properties,
)

from .models.groups import GroupType, groups, user_to_groups
from .utils_models import FromRowMixin


class GroupExtraPropertiesError(Exception):
    ...


class GroupExtraPropertiesNotFound(GroupExtraPropertiesError):
    ...


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupExtraProperties(FromRowMixin):
    group_id: int
    product_name: str
    internet_access: bool
    override_services_specifications: bool
    created: datetime.datetime
    modified: datetime.datetime


async def _list_table_entries_ordered_by_group_type(
    connection: SAConnection, user_id: int, product_name: str
) -> list[RowProxy]:
    subquery = (
        sqlalchemy.select(
            *[
                groups_extra_properties,
                groups.c.type,
                sqlalchemy.case(
                    [
                        # NOTE: the ordering is important for the aggregation afterwards
                        (groups.c.type == "EVERYONE", sqlalchemy.literal(3)),
                        (groups.c.type == "STANDARD", sqlalchemy.literal(2)),
                        (groups.c.type == "PRIMARY", sqlalchemy.literal(1)),
                    ],
                    else_=sqlalchemy.literal(4),
                ).label("type_order"),
            ]
        )
        .select_from(
            sqlalchemy.join(
                sqlalchemy.join(
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

    result = await connection.execute(
        sqlalchemy.select(subquery).order_by(subquery.c.type_order)
    )
    assert result  # nosec

    rows = await result.fetchall()
    assert rows is not None  # nosec
    return rows


def _merge_extra_properties_booleans(
    instance1: GroupExtraProperties, instance2: GroupExtraProperties
) -> GroupExtraProperties:
    merged_properties = {}
    for field in fields(instance1):
        value1 = getattr(instance1, field.name)
        value2 = getattr(instance2, field.name)

        if isinstance(value1, bool):
            merged_properties[field.name] = value1 or value2
        else:
            merged_properties[field.name] = value1
    return GroupExtraProperties(**merged_properties)  # type: ignore


@dataclass(frozen=True, slots=True, kw_only=True)
class GroupExtraPropertiesRepo:
    @staticmethod
    async def get(
        connection: SAConnection, *, gid: int, product_name: str
    ) -> GroupExtraProperties:
        get_stmt = sqlalchemy.select(groups_extra_properties).where(
            (groups_extra_properties.c.group_id == gid)
            & (groups_extra_properties.c.product_name == product_name)
        )
        result = await connection.execute(get_stmt)
        assert result  # nosec
        if row := await result.first():
            return GroupExtraProperties.from_row(row)
        raise GroupExtraPropertiesNotFound(f"Properties for group {gid} not found")

    @staticmethod
    async def get_aggregated_properties_for_user(
        connection: SAConnection,
        *,
        user_id: int,
        product_name: str,
    ) -> GroupExtraProperties:
        rows = await _list_table_entries_ordered_by_group_type(
            connection, user_id, product_name
        )
        merged_standard_extra_properties = None
        for row in rows:
            group_extra_properties = GroupExtraProperties.from_row(row)
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
        if merged_standard_extra_properties:
            return merged_standard_extra_properties
        raise GroupExtraPropertiesNotFound(
            f"Properties for user {user_id} in {product_name} not found"
        )

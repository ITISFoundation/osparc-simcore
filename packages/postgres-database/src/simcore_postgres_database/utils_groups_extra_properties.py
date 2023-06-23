import datetime
from dataclasses import dataclass

import sqlalchemy
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.groups_extra_properties import (
    groups_extra_properties,
)

from .models.groups import groups, user_to_groups
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

    async def get_aggregated_properties_for_user(
        self, connection: SAConnection, *, user_id: int, product_name: str
    ) -> GroupExtraProperties:
        subquery = (
            sqlalchemy.select(
                *[
                    groups_extra_properties,
                    groups.c.type,
                    sqlalchemy.case(
                        [
                            (groups.c.type == "EVERYONE", sqlalchemy.literal(1)),
                            (groups.c.type == "STANDARD", sqlalchemy.literal(2)),
                            (groups.c.type == "PRIMARY", sqlalchemy.literal(3)),
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
                (user_to_groups.c.uid == user_id)
                & (groups_extra_properties.c.product_name == product_name)
            )
            .alias()
        )

        query = sqlalchemy.select(subquery).order_by(subquery.c.type_order)

        result = await connection.execute(query)
        assert result  # nosec

        rows = await result.fetchall()
        assert rows is not None  # nosec

        everyone_extra_properties = GroupExtraProperties.from_row(rows[0])
        standard_extra_properties = [
            GroupExtraProperties.from_row(row for row in rows[1:-2])
        ]
        primary_extra_properties = GroupExtraProperties.from_row(rows[-1])

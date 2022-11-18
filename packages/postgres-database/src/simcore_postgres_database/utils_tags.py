""" Includes some utils for tags in db


    - All db logic is separated here and allows a simpler testing/development
"""

from dataclasses import dataclass
from typing import Any, TypedDict

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.groups import groups, user_to_groups
from simcore_postgres_database.models.tags import tags, tags_to_groups
from simcore_postgres_database.models.users import users

#
# errors
#


class NotFoundError(RuntimeError):
    pass


class NotAllowedError(RuntimeError):  # maps to AccessForbidden
    pass


#
# repo
#


class TagDict(TypedDict):
    id: int
    name: int
    description: str
    color: str


@dataclass
class TagsRepo:
    user_id: int

    @classmethod
    def _get_values(cls, data: dict[str, Any], required: set[str], optional: set[str]):
        values = {k: data[k] for k in required}
        for k in optional:
            if value := data.get(k):
                values[k] = value
        return values

    def _join_user_read_tags(self):
        # select read tags in user's groups
        j_user_read_tags = (
            tags.join(
                tags_to_groups,
                (tags.c.id == tags_to_groups.c.tag_id)
                & (tags_to_groups.c.read == True),
            )
            .join(groups)
            .join(user_to_groups, user_to_groups.c.uid == self.user_id)
        )
        return j_user_read_tags

    #
    # CRUD operations
    #

    async def list_(self, conn: SAConnection) -> list[TagDict]:
        j_user_read_tags = self._join_user_read_tags()
        select_stmt = (
            sa.select([tags.c.id, tags.c.name, tags.c.description, tags.c.color])
            .distinct(tags.c.id, tags.c.name, tags.c.description, tags.c.color)
            .select_from(j_user_read_tags)
            .order_by(tags.c.name)
            .limit(50)
        )

        # pylint: disable=not-an-iterable
        result = []
        async for row in conn.execute(select_stmt):
            row_dict = TagDict(row.items())
            result.append(row_dict)
        return result

    async def get(self, conn: SAConnection, tag_id: int) -> TagDict:
        j_user_read_tags = self._join_user_read_tags()
        select_stmt = (
            sa.select([tags.c.id, tags.c.name, tags.c.description, tags.c.color])
            .distinct(tags.c.id)
            .select_from(j_user_read_tags)
            .where(tags.c.id == tag_id)
        )

        result = await conn.execute(select_stmt)
        row = await result.first()
        if not row:
            raise NotFoundError
        return TagDict(row.items())

    async def update(
        self, conn: SAConnection, tag_id: int, tag_update: TagDict
    ) -> TagDict:
        # select write tags in user's groups
        j_user_write_tags = (
            tags.join(
                tags_to_groups,
                (tags.c.id == tag_id) & (tags_to_groups.c.write == True),
            )
            .join(groups)
            .join(user_to_groups, (user_to_groups.c.uid == self.user_id))
        )

        values = self._get_values(
            tag_update, required={}, optional={"description", "name", "color"}
        )

        update_stmt = (
            tags.update()
            .values(**values)
            .where(tags.c.id == tag_id)
            .returning(tags.c.id, tags.c.name, tags.c.description, tags.c.color)
        )

        can_update = await conn.scalar(
            sa.select([tags_to_groups.c.write])
            .select_from(j_user_write_tags)
            .distinct()
        )
        if not can_update:
            raise NotAllowedError()

        result = await conn.execute(update_stmt)
        if row_proxy := await result.first():
            return TagDict(row_proxy.items())

        raise NotFoundError

    async def create(self, conn: SAConnection, tag_create: TagDict) -> int:

        values = self._get_values(
            tag_create, required={"name", "color"}, optional={"description"}
        )
        insert_tag_stmt = (
            tags.insert()
            .values(**values)
            .returning(tags.c.id, tags.c.name, tags.c.description, tags.c.color)
        )

        async with conn.begin():
            # get primary gid
            primary_gid = await conn.scalar(
                sa.select([users.c.primary_gid]).where(users.c.id == self.user_id)
            )

            # insert new tag
            result = await conn.execute(insert_tag_stmt)
            if tag := await result.first():
                # take tag ownership
                await conn.execute(
                    tags_to_groups.insert().values(
                        tag_id=tag.id,
                        group_id=primary_gid,
                        read=True,
                        write=True,
                        delete=True,
                    )
                )
                return TagDict(tag.items())

    async def delete(self, conn: SAConnection, tag_id: int) -> None:
        # select delete tags in user's groups
        j_user_delete_tags = (
            tags.join(
                tags_to_groups,
                (tags.c.id == tag_id) & (tags_to_groups.c.delete == True),
            )
            .join(groups)
            .join(user_to_groups, (user_to_groups.c.uid == self.user_id))
        )

        # pylint: disable=no-value-for-parameter
        can_delete = await conn.scalar(
            sa.select([tags_to_groups.c.delete])
            .select_from(j_user_delete_tags)
            .distinct()
        )

        if not can_delete:
            raise NotAllowedError()

        assert can_delete  # nosec
        await conn.execute(tags.delete().where(tags.c.id == tag_id))

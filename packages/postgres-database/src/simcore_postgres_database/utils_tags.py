""" Includes some utils for tags in db


    - All db logic is separated here and allows a simpler testing/development
"""

from dataclasses import dataclass
from typing import Optional, TypedDict

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.groups import groups, user_to_groups
from simcore_postgres_database.models.tags import tags, tags_to_groups
from simcore_postgres_database.models.users import users

#
# errors
#


class TagNotFoundError(Exception):
    pass


class TagOperationNotAllowed(Exception):  # maps to AccessForbidden
    pass


#
# repo
#


class TagDict(TypedDict, total=False):
    id: int
    name: int
    description: str
    color: str


_TAG_COLUMNS = [tags.c.id, tags.c.name, tags.c.description, tags.c.color]


@dataclass
class AccessRights:
    read: bool
    write: bool
    delete: bool


@dataclass
class TagsRepo:
    user_id: int

    @classmethod
    def _get_values(cls, *, data: TagDict, required: set[str], optional: set[str]):
        values = {k: data[k] for k in required}  # type: ignore
        for k in optional:
            if value := data.get(k):
                values[k] = value
        return values

    def _user_tags_with(self, access_condition):
        j = (
            tags.join(
                tags_to_groups,
                (tags.c.id == tags_to_groups.c.tag_id) & access_condition,
            )
            .join(groups)
            .join(
                user_to_groups,
                (user_to_groups.c.gid == groups.c.gid)
                & (user_to_groups.c.uid == self.user_id),
            )
        )
        return j

    def _join_user_can(
        self,
        access_condition,
        tag_id: int,
    ):
        # FIXME: for access-checks there is no need to join tags table
        # since we can works with the tag_id of tags_to_groups
        j = tags.join(
            tags_to_groups,
            (tags.c.id == tag_id)
            & (tags_to_groups.c.tag_id == tag_id)  # explicit foreigh-key constraint
            & (access_condition),
        ).join(
            user_to_groups,
            (
                tags_to_groups.c.group_id == user_to_groups.c.gid
            )  # explicit foreigh-key constraint
            & (user_to_groups.c.uid == self.user_id),
        )
        return j

    def _join_user_to_tags(
        self,
        access_condition,
    ):
        j = user_to_groups.join(
            tags_to_groups,
            (user_to_groups.c.uid == self.user_id)
            & (user_to_groups.c.gid == tags_to_groups.c.group_id)
            & (access_condition),
        ).join(tags)
        return j

    async def access_count(self, conn: SAConnection, tag_id: int, access: str) -> int:
        """Returns 0 if no access or >0 that is the count of groups giving this access to the user"""
        access_col = {
            "read": tags_to_groups.c.read,
            "write": tags_to_groups.c.write,
            "delete": tags_to_groups.c.delete,
        }[access]

        j = self._join_user_can(
            access_condition=(access_col == True),
            tag_id=tag_id,
        )
        stmt = sa.select(sa.func.count(user_to_groups.c.uid)).select_from(j)

        # The number of occurrences of the user_id = how many groups are giving this access permission
        permissions_count: Optional[int] = await conn.scalar(stmt)
        return permissions_count if permissions_count else 0

    #
    # CRUD operations
    #

    async def list(self, conn: SAConnection) -> list[TagDict]:
        select_stmt = (
            sa.select(_TAG_COLUMNS)
            .select_from(self._join_user_to_tags(tags_to_groups.c.read == True))
            .order_by(tags.c.name)
        )

        # pylint: disable=not-an-iterable
        items = []
        async for row in conn.execute(select_stmt):
            items.append(TagDict(row.items()))  # type: ignore
        return items

    async def get(self, conn: SAConnection, tag_id: int) -> TagDict:

        select_stmt = (
            sa.select(_TAG_COLUMNS)
            .distinct(tags.c.id)
            .select_from(self._user_tags_with(tags_to_groups.c.read == True))
            .where(tags.c.id == tag_id)
        )

        result = await conn.execute(select_stmt)
        row = await result.first()
        if not row:
            raise TagNotFoundError(f"{tag_id=} not found")
        return TagDict(row.items())  # type: ignore

    async def update(
        self, conn: SAConnection, tag_id: int, tag_update: TagDict
    ) -> TagDict:
        # select write tags in user's groups
        j_user_write_tags = self._user_tags_with(tags_to_groups.c.write == True)

        values = self._get_values(
            data=tag_update, required=set(), optional={"description", "name", "color"}
        )

        update_stmt = (
            tags.update()
            .values(**values)
            .where(tags.c.id == tag_id)
            .returning(*_TAG_COLUMNS)
        )

        can_update = await conn.scalar(
            sa.select([tags_to_groups.c.write]).select_from(j_user_write_tags).where()
        )
        if not can_update:
            raise TagOperationNotAllowed(
                f"Insufficent access rights to update {tag_id=}"
            )

        result = await conn.execute(update_stmt)
        row = await result.first()
        if not row:
            raise TagNotFoundError(f"{tag_id=} not found")

        return TagDict(row.items())  # type: ignore

    async def create(self, conn: SAConnection, tag_create: TagDict) -> TagDict:

        values = self._get_values(
            data=tag_create, required={"name", "color"}, optional={"description"}
        )
        insert_tag_stmt = tags.insert().values(**values).returning(*_TAG_COLUMNS)

        async with conn.begin():

            # insert new tag
            result = await conn.execute(insert_tag_stmt)
            row = await result.first()
            assert row  # nosec

            # take tag ownership

            primary_gid = await conn.scalar(
                sa.select([users.c.primary_gid]).where(users.c.id == self.user_id)
            )
            await conn.execute(
                tags_to_groups.insert().values(
                    tag_id=row.id,
                    group_id=primary_gid,
                    read=True,
                    write=True,
                    delete=True,
                )
            )
            return TagDict(row.items())  # type: ignore

    async def delete(self, conn: SAConnection, tag_id: int) -> None:
        # select delete tags in user's groups
        can_delete = await conn.scalar(
            sa.select([tags_to_groups.c.delete]).select_from(
                self._user_tags_with(tags_to_groups.c.delete == True)
            )
        )

        if not can_delete:
            raise TagOperationNotAllowed(
                f"Insufficent access rights to delete {tag_id=}"
            )

        assert can_delete  # nosec
        await conn.execute(tags.delete().where(tags.c.id == tag_id))

""" Repository pattern, errors and data structures for models.tags
"""

import functools
import itertools
from dataclasses import dataclass
from typing import TypedDict

import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.tags import tags, tags_to_groups
from simcore_postgres_database.models.users import users


#
# Errors
#
class BaseTagError(Exception):
    pass


class TagNotFoundError(BaseTagError):
    pass


class TagOperationNotAllowedError(BaseTagError):  # maps to AccessForbidden
    pass


#
# Repository: interface layer over pg database
#


_TAG_COLUMNS = [
    tags.c.id,
    tags.c.name,
    tags.c.description,
    tags.c.color,
]

_ACCESS_COLUMNS = [
    tags_to_groups.c.read,
    tags_to_groups.c.write,
    tags_to_groups.c.delete,
]


_COLUMNS = _TAG_COLUMNS + _ACCESS_COLUMNS


class TagDict(TypedDict, total=True):
    id: int
    name: str
    description: str
    color: str
    # access rights
    read: bool
    write: bool
    delete: bool


@dataclass(frozen=True)
class TagsRepo:
    user_id: int

    def _join_user_groups_tag(
        self,
        access_condition,
        tag_id: int,
    ):
        return user_to_groups.join(
            tags_to_groups,
            (user_to_groups.c.uid == self.user_id)
            & (user_to_groups.c.gid == tags_to_groups.c.group_id)
            & (access_condition)
            & (tags_to_groups.c.tag_id == tag_id),
        )

    def _join_user_to_given_tag(self, access_condition, tag_id: int):
        return self._join_user_groups_tag(
            access_condition=access_condition,
            tag_id=tag_id,
        ).join(tags)

    def _join_user_to_tags(
        self,
        access_condition,
    ):
        return user_to_groups.join(
            tags_to_groups,
            (user_to_groups.c.uid == self.user_id)
            & (user_to_groups.c.gid == tags_to_groups.c.group_id)
            & (access_condition),
        ).join(tags)

    async def access_count(
        self,
        conn: SAConnection,
        tag_id: int,
        *,
        read: bool | None = None,
        write: bool | None = None,
        delete: bool | None = None,
    ) -> int:
        """
        Returns 0 if tag does not match access
        Returns >0 if it does and represents the number of groups granting this access to the user
        """
        access = []
        if read is not None:
            access.append(tags_to_groups.c.read == read)
        if write is not None:
            access.append(tags_to_groups.c.write == write)
        if delete is not None:
            access.append(tags_to_groups.c.delete == delete)

        if not access:
            msg = "Undefined access"
            raise ValueError(msg)

        j = self._join_user_groups_tag(
            access_condition=functools.reduce(sa.and_, access),
            tag_id=tag_id,
        )
        stmt = sa.select(sa.func.count(user_to_groups.c.uid)).select_from(j)

        # The number of occurrences of the user_id = how many groups are giving this access permission
        permissions_count: int | None = await conn.scalar(stmt)
        return permissions_count if permissions_count else 0

    #
    # CRUD operations
    #

    async def create(
        self,
        conn: SAConnection,
        *,
        name: str,
        color: str,
        description: str | None = None,  # =nullable
        read: bool = True,
        write: bool = True,
        delete: bool = True,
    ) -> TagDict:
        values = {"name": name, "color": color}
        if description:
            values["description"] = description

        async with conn.begin():
            # insert new tag
            insert_stmt = tags.insert().values(**values).returning(*_TAG_COLUMNS)
            result = await conn.execute(insert_stmt)
            tag = await result.first()
            assert tag  # nosec

            # take tag ownership
            scalar_subq = (
                sa.select(users.c.primary_gid)
                .where(users.c.id == self.user_id)
                .scalar_subquery()
            )
            result = await conn.execute(
                tags_to_groups.insert()
                .values(
                    tag_id=tag.id,
                    group_id=scalar_subq,
                    read=read,
                    write=write,
                    delete=delete,
                )
                .returning(*_ACCESS_COLUMNS)
            )
            access = await result.first()
            assert access

            return TagDict(itertools.chain(tag.items(), access.items()))  # type: ignore

    async def list_all(self, conn: SAConnection) -> list[TagDict]:
        select_stmt = (
            sa.select(*_COLUMNS)
            .select_from(self._join_user_to_tags(tags_to_groups.c.read.is_(True)))
            .order_by(tags.c.id)
        )

        return [TagDict(row.items()) async for row in conn.execute(select_stmt)]  # type: ignore

    async def get(self, conn: SAConnection, tag_id: int) -> TagDict:
        select_stmt = sa.select(*_COLUMNS).select_from(
            self._join_user_to_given_tag(tags_to_groups.c.read.is_(True), tag_id=tag_id)
        )

        result = await conn.execute(select_stmt)
        row = await result.first()
        if not row:
            msg = f"{tag_id=} not found: either no access or does not exists"
            raise TagNotFoundError(msg)
        return TagDict(row.items())  # type: ignore

    async def update(
        self,
        conn: SAConnection,
        tag_id: int,
        **fields,
    ) -> TagDict:
        updates = {
            name: value
            for name, value in fields.items()
            if name in {"name", "color", "description"}
        }

        if not updates:
            # no updates == get
            return await self.get(conn, tag_id=tag_id)

        update_stmt = (
            tags.update()
            .where(tags.c.id == tag_id)
            .where(
                (tags.c.id == tags_to_groups.c.tag_id)
                & (tags_to_groups.c.write.is_(True))
            )
            .where(
                (tags_to_groups.c.group_id == user_to_groups.c.gid)
                & (user_to_groups.c.uid == self.user_id)
            )
            .values(**updates)
            .returning(*_COLUMNS)
        )

        result = await conn.execute(update_stmt)
        row = await result.first()
        if not row:
            msg = f"{tag_id=} not updated: either no access or not found"
            raise TagOperationNotAllowedError(msg)

        return TagDict(row.items())  # type: ignore

    async def delete(self, conn: SAConnection, tag_id: int) -> None:
        delete_stmt = (
            tags.delete()
            .where(tags.c.id == tag_id)
            .where(
                (tags_to_groups.c.tag_id == tag_id)
                & (tags_to_groups.c.delete.is_(True))
            )
            .where(
                (tags_to_groups.c.group_id == user_to_groups.c.gid)
                & (user_to_groups.c.uid == self.user_id)
            )
            .returning(tags_to_groups.c.delete)
        )

        deleted = await conn.scalar(delete_stmt)
        if not deleted:
            msg = f"Could not delete {tag_id=}. Not found or insuficient access."
            raise TagOperationNotAllowedError(msg)

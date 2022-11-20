""" Repository pattern, errors and data structures for models.tags
"""

import functools
from dataclasses import dataclass
from typing import Any, Optional, TypedDict

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


class ValidationError(BaseTagError):
    pass


class TagNotFoundError(BaseTagError):
    pass


class TagOperationNotAllowed(BaseTagError):  # maps to AccessForbidden
    pass


#
# Repository: interface layer over pg database
#
class TagDict(TypedDict, total=True):
    # NOTE: ONLY used as returned value, otherwise used
    id: int
    name: int
    description: str
    color: str


_TAG_COLUMNS = [tags.c.id, tags.c.name, tags.c.description, tags.c.color]


@dataclass(frozen=True)
class TagsRepo:
    user_id: int

    @classmethod
    def _validate_data(
        cls, *, data: dict[str, Any], required: set[str], optional: set[str]
    ):
        try:
            values = {k: data[k] for k in required}  # type: ignore
        except KeyError as err:
            raise ValidationError(f"Missing required value: {err}") from err

        for k in optional:
            if value := data.get(k):
                values[k] = value
        return values

    def _join_user_groups_tag(
        self,
        access_condition,
        tag_id: int,
    ):
        j = user_to_groups.join(
            tags_to_groups,
            (user_to_groups.c.uid == self.user_id)
            & (user_to_groups.c.gid == tags_to_groups.c.group_id)
            & (access_condition)
            & (tags_to_groups.c.tag_id == tag_id),
        )
        return j

    def _join_user_to_given_tag(self, access_condition, tag_id: int):
        j = self._join_user_groups_tag(
            access_condition=access_condition,
            tag_id=tag_id,
        ).join(tags)
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

    async def access_count(
        self,
        conn: SAConnection,
        tag_id: int,
        *,
        read: Optional[bool] = None,
        write: Optional[bool] = None,
        delete: Optional[bool] = None,
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
            raise ValueError("Undefined access")

        j = self._join_user_groups_tag(
            access_condition=functools.reduce(sa.and_, access),
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
            .order_by(tags.c.id)
        )

        items = []
        async for row in conn.execute(select_stmt):
            items.append(TagDict(row.items()))  # type: ignore
        return items

    async def get(self, conn: SAConnection, tag_id: int) -> TagDict:
        select_stmt = sa.select(_TAG_COLUMNS).select_from(
            self._join_user_to_given_tag(tags_to_groups.c.read == True, tag_id=tag_id)
        )

        result = await conn.execute(select_stmt)
        row = await result.first()
        if not row:
            raise TagNotFoundError(
                f"{tag_id=} not found: either no access or does not exists"
            )
        return TagDict(row.items())  # type: ignore

    async def update(self, conn: SAConnection, tag_id: int, **tag_update) -> TagDict:
        updates = self._validate_data(
            data=tag_update, required=set(), optional={"description", "name", "color"}
        )

        update_stmt = (
            tags.update()
            .where(tags.c.id == tag_id)
            .where(
                (tags.c.id == tags_to_groups.c.tag_id)
                & (tags_to_groups.c.write == True)
            )
            .where(
                (tags_to_groups.c.group_id == user_to_groups.c.gid)
                & (user_to_groups.c.uid == self.user_id)
            )
            .values(**updates)
            .returning(*_TAG_COLUMNS)
        )

        result = await conn.execute(update_stmt)
        row = await result.first()
        if not row:
            raise TagOperationNotAllowed(
                f"{tag_id=} not updated: either no access or not found"
            )

        return TagDict(row.items())  # type: ignore

    async def create(
        self,
        conn: SAConnection,
        *,
        read: bool = True,
        write: bool = True,
        delete: bool = True,
        **tag_create,
    ) -> TagDict:

        values = self._validate_data(
            data=tag_create, required={"name", "color"}, optional={"description"}
        )

        async with conn.begin():
            # insert new tag
            insert_stmt = tags.insert().values(**values).returning(*_TAG_COLUMNS)
            result = await conn.execute(insert_stmt)
            row = await result.first()
            assert row  # nosec

            # take tag ownership
            scalar_subq = (
                sa.select(users.c.primary_gid)
                .where(users.c.id == self.user_id)
                .scalar_subquery()
            )
            await conn.execute(
                tags_to_groups.insert().values(
                    tag_id=row.id,
                    group_id=scalar_subq,
                    read=read,
                    write=write,
                    delete=delete,
                )
            )
            return TagDict(row.items())  # type: ignore

    async def delete(self, conn: SAConnection, tag_id: int) -> None:
        delete_stmt = (
            tags.delete()
            .where(tags.c.id == tag_id)
            .where(
                (tags_to_groups.c.tag_id == tag_id) & (tags_to_groups.c.delete == True)
            )
            .where(
                (tags_to_groups.c.group_id == user_to_groups.c.gid)
                & (user_to_groups.c.uid == self.user_id)
            )
            .returning(tags_to_groups.c.delete)
        )

        deleted = await conn.scalar(delete_stmt)
        if not deleted:
            raise TagOperationNotAllowed(
                f"Could not delete {tag_id=}. Not found or insuficient access."
            )

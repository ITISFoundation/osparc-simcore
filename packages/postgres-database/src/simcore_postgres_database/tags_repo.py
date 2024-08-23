""" Repository pattern, errors and data structures for models.tags
"""

import itertools
from dataclasses import dataclass
from typing import TypedDict

from aiopg.sa.connection import SAConnection

from .tags_sql import (
    count_users_with_access_rights_stmt,
    create_tag_stmt,
    delete_tag_stmt,
    get_tag_stmt,
    list_tags_stmt,
    set_tag_access_rights_stmt,
    update_tag_stmt,
)


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
        count_stmt = count_users_with_access_rights_stmt(
            user_id=self.user_id, tag_id=tag_id, read=read, write=write, delete=delete
        )
        permissions_count: int | None = await conn.scalar(count_stmt)
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

        if not read:
            read = write or delete
        if not write:
            write = delete

        async with conn.begin():
            # insert new tag
            insert_stmt = create_tag_stmt(**values)
            result = await conn.execute(insert_stmt)
            tag = await result.first()
            assert tag  # nosec

            # take tag ownership
            access_stmt = set_tag_access_rights_stmt(
                tag_id=tag.id,
                user_id=self.user_id,
                read=read,
                write=write,
                delete=delete,
            )
            result = await conn.execute(access_stmt)
            access = await result.first()
            assert access

            return TagDict(itertools.chain(tag.items(), access.items()))  # type: ignore

    async def list_all(self, conn: SAConnection) -> list[TagDict]:
        stmt_list = list_tags_stmt(user_id=self.user_id)
        return [TagDict(row.items()) async for row in conn.execute(stmt_list)]  # type: ignore

    async def get(self, conn: SAConnection, tag_id: int) -> TagDict:
        stmt_get = get_tag_stmt(user_id=self.user_id, tag_id=tag_id)
        result = await conn.execute(stmt_get)
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

        update_stmt = update_tag_stmt(user_id=self.user_id, tag_id=tag_id, **updates)
        result = await conn.execute(update_stmt)
        row = await result.first()
        if not row:
            msg = f"{tag_id=} not updated: either no access or not found"
            raise TagOperationNotAllowedError(msg)

        return TagDict(row.items())  # type: ignore

    async def delete(self, conn: SAConnection, tag_id: int) -> None:
        stmt_delete = delete_tag_stmt(user_id=self.user_id, tag_id=tag_id)

        deleted = await conn.scalar(stmt_delete)
        if not deleted:
            msg = f"Could not delete {tag_id=}. Not found or insuficient access."
            raise TagOperationNotAllowedError(msg)

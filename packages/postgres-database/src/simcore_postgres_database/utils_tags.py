""" Repository pattern, errors and data structures for models.tags
"""

from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from .utils_repos import pass_or_acquire_connection, transaction_context
from .utils_tags_sql import (
    count_groups_with_given_access_rights_stmt,
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


class TagsRepo:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def access_count(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        tag_id: int,
        read: bool | None = None,
        write: bool | None = None,
        delete: bool | None = None,
    ) -> int:
        """
        Returns 0 if tag does not match access
        Returns >0 if it does and represents the number of groups granting this access to the user
        """
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            count_stmt = count_groups_with_given_access_rights_stmt(
                user_id=user_id, tag_id=tag_id, read=read, write=write, delete=delete
            )
            permissions_count: int | None = await conn.scalar(count_stmt)
            return permissions_count if permissions_count else 0

    #
    # CRUD operations
    #

    async def create(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        name: str,
        color: str,
        description: str | None = None,  # =nullable
        read: bool = True,
        write: bool = True,
        delete: bool = True,
        priority: int | None = None,
    ) -> TagDict:
        """Creates tag and defaults to full access rights to `user_id`"""
        values: dict[str, str | int] = {
            "name": name,
            "color": color,
        }
        if description:
            values["description"] = description
        if priority is not None:
            values["priority"] = priority

        async with transaction_context(self.engine, connection) as conn:
            # insert new tag
            insert_stmt = create_tag_stmt(**values)
            result = await conn.execute(insert_stmt)
            tag = result.first()
            assert tag  # nosec

            # take tag ownership
            access_stmt = set_tag_access_rights_stmt(
                tag_id=tag.id,
                user_id=user_id,
                read=read,
                write=write,
                delete=delete,
            )
            result = await conn.execute(access_stmt)
            access = result.first()
            assert access  # nosec

            return TagDict(
                id=tag.id,
                name=tag.name,
                description=tag.description,
                color=tag.color,
                read=access.read,
                write=access.write,
                delete=access.delete,
            )

    async def list_all(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
    ) -> list[TagDict]:
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            stmt_list = list_tags_stmt(user_id=user_id)
            result = await conn.stream(stmt_list)
            return [
                TagDict(
                    id=row.id,
                    name=row.name,
                    description=row.description,
                    color=row.color,
                    read=row.read,
                    write=row.write,
                    delete=row.delete,
                )
                async for row in result
            ]

    async def get(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        tag_id: int,
    ) -> TagDict:
        stmt_get = get_tag_stmt(user_id=user_id, tag_id=tag_id)
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            result = await conn.execute(stmt_get)
            row = result.first()
            if not row:
                msg = f"{tag_id=} not found: either no access or does not exists"
                raise TagNotFoundError(msg)
            return TagDict(
                id=row.id,
                name=row.name,
                description=row.description,
                color=row.color,
                read=row.read,
                write=row.write,
                delete=row.delete,
            )

    async def update(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        tag_id: int,
        **fields,
    ) -> TagDict:
        async with transaction_context(self.engine, connection) as conn:
            updates = {
                name: value
                for name, value in fields.items()
                if name in {"name", "color", "description", "priority"}
            }

            if not updates:
                # no updates == get
                return await self.get(conn, user_id=user_id, tag_id=tag_id)

            update_stmt = update_tag_stmt(user_id=user_id, tag_id=tag_id, **updates)
            result = await conn.execute(update_stmt)
            row = result.first()
            if not row:
                msg = f"{tag_id=} not updated: either no access or not found"
                raise TagOperationNotAllowedError(msg)

            return TagDict(
                id=row.id,
                name=row.name,
                description=row.description,
                color=row.color,
                read=row.read,
                write=row.write,
                delete=row.delete,
            )

    async def delete(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        tag_id: int,
    ) -> None:
        stmt_delete = delete_tag_stmt(user_id=user_id, tag_id=tag_id)
        async with transaction_context(self.engine, connection) as conn:
            deleted = await conn.scalar(stmt_delete)
            if not deleted:
                msg = f"Could not delete {tag_id=}. Not found or insuficient access."
                raise TagOperationNotAllowedError(msg)

    #
    # ACCESS RIGHTS
    #

    async def create_access_rights(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        tag_id: int,
        group_id: int,
        read: bool,
        write: bool,
        delete: bool,
    ):
        raise NotImplementedError

    async def update_access_rights(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        tag_id: int,
        group_id: int,
        read: bool,
        write: bool,
        delete: bool,
    ):
        raise NotImplementedError

    async def delete_access_rights(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        tag_id: int,
    ):
        raise NotImplementedError

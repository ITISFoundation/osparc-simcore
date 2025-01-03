""" Repository pattern, errors and data structures for models.tags
"""

from typing import TypedDict

from common_library.errors_classes import OsparcErrorMixin
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from .utils_repos import pass_or_acquire_connection, transaction_context
from .utils_tags_sql import (
    count_groups_with_given_access_rights_stmt,
    create_tag_stmt,
    delete_tag_sharing_stmt,
    delete_tag_stmt,
    get_tag_stmt,
    has_access_rights_stmt,
    list_tag_group_access_stmt,
    list_tags_stmt,
    share_tag_stmt,
    update_tag_stmt,
)


#
# Errors
#
class _BaseTagError(ValueError, OsparcErrorMixin):
    pass


class TagNotFoundError(_BaseTagError):
    pass


class TagOperationNotAllowedError(_BaseTagError):  # maps to AccessForbidden
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
            access_stmt = share_tag_stmt(
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
                raise TagNotFoundError(operation="get", tag_id=tag_id, user_id=user_id)
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
                raise TagOperationNotAllowedError(
                    operation="update", tag_id=tag_id, user_id=user_id
                )

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
                raise TagOperationNotAllowedError(
                    operation="delete", tag_id=tag_id, user_id=user_id
                )

    #
    # ACCESS RIGHTS
    #

    async def _has_access_rights(
        self,
        connection: AsyncConnection,
        *,
        caller_id: int,
        tag_id: int,
        read: bool = False,
        write: bool = False,
        delete: bool = False,
    ) -> bool:
        result = await connection.execute(
            has_access_rights_stmt(
                tag_id=tag_id,
                caller_user_id=caller_id,
                read=read,
                write=write,
                delete=delete,
            )
        )
        return result.fetchone() is not None

    async def list_tag_group_access(
        self,
        connection: AsyncConnection | None = None,
        *,
        # caller
        user_id: int,
        # target
        tag_id: int,
    ):
        async with pass_or_acquire_connection(self.engine, connection) as conn:
            if not await self._has_access_rights(
                conn, caller_id=user_id, tag_id=tag_id, read=True
            ):
                # TODO: empyt list or error?
                raise TagOperationNotAllowedError(
                    operation="share.list", user_id=user_id, tag_id=tag_id
                )

            result = await conn.execute(list_tag_group_access_stmt(tag_id=tag_id))
            return [dict(row) for row in result.fetchall()]

    async def create_or_update_access_rights(
        self,
        connection: AsyncConnection | None = None,
        *,
        # caller
        user_id: int,
        # target
        tag_id: int,
        group_id: int,
        # access-rights
        read: bool,
        write: bool,
        delete: bool,
    ):
        async with transaction_context(self.engine, connection) as conn:
            if not await self._has_access_rights(
                conn, caller_id=user_id, tag_id=tag_id, write=True
            ):
                raise TagOperationNotAllowedError(
                    operation="share.write", user_id=user_id, tag_id=tag_id
                )

            result = await conn.execute(
                share_tag_stmt(
                    tag_id=tag_id,
                    group_id=group_id,
                    read=read,
                    write=write,
                    delete=delete,
                )
            )
            row = result.first()
            return dict(row)

    async def delete_access_rights(
        self,
        connection: AsyncConnection | None = None,
        *,
        user_id: int,
        # target
        tag_id: int,
        group_id: int,
    ) -> bool:
        async with transaction_context(self.engine, connection) as conn:
            if not await self._has_access_rights(
                conn, caller_id=user_id, tag_id=tag_id, write=True
            ):
                raise TagOperationNotAllowedError(
                    operation="share.delete", user_id=user_id, tag_id=tag_id
                )

            deleted: bool = await conn.scalar(
                delete_tag_sharing_stmt(tag_id=tag_id, group_id=group_id)
            )
            return deleted

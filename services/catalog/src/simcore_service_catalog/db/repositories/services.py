import logging
from typing import List, Optional, Tuple

import sqlalchemy as sa
from aiopg.sa import SAConnection
from aiopg.sa.result import RowProxy
from models_library.services import ServiceAccessRightsAtDB, ServiceMetaDataAtDB
from psycopg2.errors import ForeignKeyViolation  # pylint: disable=no-name-in-module
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import and_, or_
from sqlalchemy.sql.selectable import Select

from ..tables import services_access_rights, services_meta_data, users
from ._base import BaseRepository

logger = logging.getLogger(__name__)


def _make_list_services_query(
    gids: Optional[List[int]] = None,
    execute_access: Optional[bool] = None,
    write_access: Optional[bool] = None,
    combine_access_with_and: Optional[bool] = True,
    product_name: Optional[str] = None,
) -> Select:
    query = sa.select([services_meta_data])
    if gids or execute_access or write_access:
        access_query_part = and_(
            services_access_rights.c.execute_access if execute_access else True,
            services_access_rights.c.write_access if write_access else True,
        )
        if not combine_access_with_and:
            access_query_part = or_(
                services_access_rights.c.execute_access if execute_access else True,
                services_access_rights.c.write_access if write_access else True,
            )
        query = (
            sa.select(
                [services_meta_data],
                distinct=[services_meta_data.c.key, services_meta_data.c.version],
            )
            .select_from(services_meta_data.join(services_access_rights))
            .where(
                and_(
                    or_(*[services_access_rights.c.gid == gid for gid in gids])
                    if gids
                    else True,
                    access_query_part,
                    (services_access_rights.c.product_name == product_name)
                    if product_name
                    else True,
                )
            )
            .order_by(services_meta_data.c.key, services_meta_data.c.version)
        )
    return query


class ServicesRepository(BaseRepository):
    async def list_services(
        self,
        gids: Optional[List[int]] = None,
        execute_access: Optional[bool] = None,
        write_access: Optional[bool] = None,
        combine_access_with_and: Optional[bool] = True,
        product_name: Optional[str] = None,
    ) -> List[ServiceMetaDataAtDB]:
        services_in_db = []

        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                _make_list_services_query(
                    gids,
                    execute_access,
                    write_access,
                    combine_access_with_and,
                    product_name,
                )
            ):
                services_in_db.append(ServiceMetaDataAtDB(**row))
        return services_in_db

    async def list_services_and_rights_owner(
        self,
        gids: Optional[List[int]] = None,
        execute_access: Optional[bool] = None,
        write_access: Optional[bool] = None,
        combine_access_with_and: Optional[bool] = True,
        product_name: Optional[str] = None,
    ) -> List[Tuple[ServiceMetaDataAtDB, List[ServiceAccessRightsAtDB], str]]:
        services_in_db = []

        async with self.db_engine.acquire() as conn:
            async for row in conn.execute(
                _make_list_services_query(
                    gids,
                    execute_access,
                    write_access,
                    combine_access_with_and,
                    product_name,
                )
            ):
                services_in_db.append(
                    (
                        ServiceMetaDataAtDB(**row),
                        await self.get_service_access_rights(
                            row[services_meta_data.c.key],
                            row[services_meta_data.c.version],
                            product_name,
                            conn,
                        ),
                        await conn.scalar(
                            sa.select([users.c.email]).where(
                                users.c.primary_gid == row[services_meta_data.c.owner]
                            )
                        )
                        or None,
                    )
                )
        return services_in_db

    async def get_service(
        # pylint: disable=too-many-arguments
        self,
        key: str,
        version: str,
        gids: Optional[List[int]] = None,
        execute_access: Optional[bool] = None,
        write_access: Optional[bool] = None,
        product_name: Optional[str] = None,
    ) -> Optional[ServiceMetaDataAtDB]:
        query = sa.select([services_meta_data]).where(
            (services_meta_data.c.key == key)
            & (services_meta_data.c.version == version)
        )
        if gids or execute_access or write_access:
            query = (
                sa.select([services_meta_data])
                .select_from(services_meta_data.join(services_access_rights))
                .where(
                    and_(
                        (services_meta_data.c.key == key),
                        (services_meta_data.c.version == version),
                        or_(*[services_access_rights.c.gid == gid for gid in gids])
                        if gids
                        else True,
                        services_access_rights.c.execute_access
                        if execute_access
                        else True,
                        services_access_rights.c.write_access if write_access else True,
                        (services_access_rights.c.product_name == product_name)
                        if product_name
                        else True,
                    )
                )
            )
        async with self.db_engine.acquire() as conn:
            row: RowProxy = await (await conn.execute(query)).first()
        if row:
            return ServiceMetaDataAtDB(**row)

    async def create_service(
        self,
        new_service: ServiceMetaDataAtDB,
        new_service_access_rights: List[ServiceAccessRightsAtDB],
    ) -> ServiceMetaDataAtDB:
        async with self.db_engine.acquire() as conn:
            async with conn.begin() as _transaction:  # NOTE: this ensure proper rollback in case of issue
                row: RowProxy = await (
                    await conn.execute(
                        # pylint: disable=no-value-for-parameter
                        services_meta_data.insert()
                        .values(**new_service.dict(by_alias=True))
                        .returning(literal_column("*"))
                    )
                ).first()
                created_service = ServiceMetaDataAtDB(**row)
                for rights in new_service_access_rights:
                    insert_stmt = insert(services_access_rights).values(
                        **rights.dict(by_alias=True)
                    )
                    await conn.execute(insert_stmt)
        return created_service

    async def update_service(
        self, patched_service: ServiceMetaDataAtDB
    ) -> ServiceMetaDataAtDB:
        # update the services_meta_data table
        async with self.db_engine.acquire() as conn:
            row: RowProxy = await (
                await conn.execute(
                    # pylint: disable=no-value-for-parameter
                    services_meta_data.update()
                    .where(
                        (services_meta_data.c.key == patched_service.key)
                        & (services_meta_data.c.version == patched_service.version)
                    )
                    .values(**patched_service.dict(by_alias=True, exclude_unset=True))
                    .returning(literal_column("*"))
                )
            ).first()
        updated_service = ServiceMetaDataAtDB(**row)
        return updated_service

    async def get_service_access_rights(
        self,
        key: str,
        version: str,
        product_name: str,
        connection: Optional[SAConnection],
    ) -> List[ServiceAccessRightsAtDB]:
        services_in_db = []
        query = sa.select([services_access_rights]).where(
            (services_access_rights.c.key == key)
            & (services_access_rights.c.version == version)
            & (services_access_rights.c.product_name == product_name)
        )
        if connection:
            async for row in connection.execute(query):
                services_in_db.append(ServiceAccessRightsAtDB(**row))
        else:
            async with self.db_engine.acquire() as conn:
                async for row in conn.execute(query):
                    services_in_db.append(ServiceAccessRightsAtDB(**row))
        return services_in_db

    async def upsert_service_access_rights(
        self, new_access_rights: List[ServiceAccessRightsAtDB]
    ) -> None:
        # update the services_access_rights table (some might be added/removed/modified)
        for rights in new_access_rights:
            insert_stmt = insert(services_access_rights).values(
                **rights.dict(by_alias=True)
            )
            on_update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[
                    services_access_rights.c.key,
                    services_access_rights.c.version,
                    services_access_rights.c.gid,
                    services_access_rights.c.product_name,
                ],
                set_=rights.dict(by_alias=True, exclude_unset=True),
            )
            try:
                async with self.db_engine.acquire() as conn:
                    await conn.execute(
                        # pylint: disable=no-value-for-parameter
                        on_update_stmt
                    )
            except ForeignKeyViolation:
                logger.warning(
                    "The service %s:%s is missing from services_meta_data",
                    rights.key,
                    rights.version,
                )

    async def delete_service_access_rights(
        self, delete_access_rights: List[ServiceAccessRightsAtDB]
    ) -> None:
        async with self.db_engine.acquire() as conn:
            for rights in delete_access_rights:
                await conn.execute(
                    # pylint: disable=no-value-for-parameter
                    services_access_rights.delete().where(
                        (services_access_rights.c.key == rights.key)
                        & (services_access_rights.c.version == rights.version)
                        & (services_access_rights.c.gid == rights.gid)
                        & (services_access_rights.c.product_name == rights.product_name)
                    )
                )

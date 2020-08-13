from typing import List, Optional

import sqlalchemy as sa
from aiopg.sa.result import RowProxy
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import and_, or_

from ...models.domain.service import ServiceAccessRightsAtDB, ServiceMetaDataAtDB
from ..tables import services_access_rights, services_meta_data
from ._base import BaseRepository


class ServicesRepository(BaseRepository):
    async def list_services(
        self,
        gids: Optional[List[int]] = None,
        execute_access: Optional[bool] = None,
        write_access: Optional[bool] = None,
    ) -> List[ServiceMetaDataAtDB]:
        services_in_db = []

        query = sa.select([services_meta_data])
        if gids or execute_access or write_access:
            query = (
                sa.select([services_meta_data])
                .select_from(services_meta_data.join(services_access_rights))
                .where(
                    and_(
                        or_(*[services_access_rights.c.gid == gid for gid in gids])
                        if gids
                        else True,
                        services_access_rights.c.execute_access
                        if execute_access
                        else True,
                        services_access_rights.c.write_access if write_access else True,
                    )
                )
            )

        async for row in self.connection.execute(query):
            if row:
                services_in_db.append(ServiceMetaDataAtDB(**row))
        return services_in_db

    async def get_service(
        # pylint: disable=too-many-arguments
        self,
        key: str,
        version: str,
        gids: Optional[List[int]] = None,
        execute_access: Optional[bool] = None,
        write_access: Optional[bool] = None,
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
                        or_(*[services_access_rights.c.gid == gid for gid in gids])
                        if gids
                        else True,
                        services_access_rights.c.execute_access
                        if execute_access
                        else True,
                        services_access_rights.c.write_access if write_access else True,
                    )
                )
            )
        row: RowProxy = await (await self.connection.execute(query)).first()
        if row:
            return ServiceMetaDataAtDB(**row)

    async def create_service(
        self,
        new_service: ServiceMetaDataAtDB,
        new_service_access_rights: List[ServiceAccessRightsAtDB],
    ) -> ServiceMetaDataAtDB:
        row: RowProxy = await (
            await self.connection.execute(
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
            await self.connection.execute(insert_stmt)
        return created_service

    async def update_service(
        self, patched_service: ServiceMetaDataAtDB
    ) -> ServiceMetaDataAtDB:
        # update the services_meta_data table
        row: RowProxy = await (
            await self.connection.execute(
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
        self, key: str, version: str
    ) -> List[ServiceAccessRightsAtDB]:
        services_in_db = []
        query = sa.select([services_access_rights]).where(
            (services_access_rights.c.key == key)
            & (services_access_rights.c.version == version)
        )
        async for row in self.connection.execute(query):
            if row:
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
                ],
                set_=rights.dict(by_alias=True, exclude_unset=True),
            )
            await self.connection.execute(
                # pylint: disable=no-value-for-parameter
                on_update_stmt
            )

    async def delete_service_access_rights(
        self, delete_access_rights: List[ServiceAccessRightsAtDB]
    ) -> None:
        for rights in delete_access_rights:
            await self.connection.execute(
                # pylint: disable=no-value-for-parameter
                services_access_rights.delete().where(
                    (services_access_rights.c.key == rights.key)
                    & (services_access_rights.c.version == rights.version)
                    & (services_access_rights.c.gid == rights.gid)
                )
            )

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import sqlalchemy as sa
from models_library.services_db import ServiceAccessRightsAtDB, ServiceMetaDataAtDB
from psycopg2.errors import ForeignKeyViolation  # pylint: disable=no-name-in-module
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import and_, or_
from sqlalchemy.sql.expression import tuple_
from sqlalchemy.sql.selectable import Select

from ..tables import services_access_rights, services_meta_data
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
        logic_operator = and_ if combine_access_with_and else or_
        default = (
            True  # pylint: disable=simplifiable-if-expression
            if combine_access_with_and
            else False
        )
        access_query_part = logic_operator(
            services_access_rights.c.execute_access if execute_access else default,
            services_access_rights.c.write_access if write_access else default,
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
    """
    API that operates on services_access_rights and services_meta_data tables
    """

    async def list_services(
        self,
        *,
        gids: Optional[List[int]] = None,
        execute_access: Optional[bool] = None,
        write_access: Optional[bool] = None,
        combine_access_with_and: Optional[bool] = True,
        product_name: Optional[str] = None,
    ) -> List[ServiceMetaDataAtDB]:
        services_in_db = []

        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(
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

    async def list_service_releases(
        self,
        key: str,
        *,
        major: Optional[int] = None,
        minor: Optional[int] = None,
        limit_count: Optional[int] = None,
    ) -> List[ServiceMetaDataAtDB]:
        """Lists LAST n releases of a given service, sorted from latest first

        major, minor is used to filter as major.minor.* or major.*
        limit_count limits returned value. None or non-positive values returns all matches
        """
        if minor is not None and major is None:
            raise ValueError("Expected only major.*.* or major.minor.*")

        search_condition = services_meta_data.c.key == key
        if major is not None:
            if minor is not None:
                # All patches
                search_condition &= services_meta_data.c.version.like(
                    f"{major}.{minor}.%"
                )
            else:
                # All minor and patches
                search_condition &= services_meta_data.c.version.like(f"{major}.%")

        query = (
            sa.select([services_meta_data])
            .where(search_condition)
            .order_by(sa.desc(services_meta_data.c.version))
        )

        if limit_count and limit_count > 0:
            query = query.limit(limit_count)

        releases = []
        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(query):
                releases.append(ServiceMetaDataAtDB(**row))

        return releases

    async def get_latest_release(self, key: str) -> Optional[ServiceMetaDataAtDB]:
        """Returns last release or None if service was never released"""
        releases = await self.list_service_releases(key, limit_count=1)
        return releases[0] if releases else None

    async def get_service(
        self,
        key: str,
        version: str,
        *,
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
        async with self.db_engine.connect() as conn:
            result = await conn.execute(query)
            row = result.first()
        if row:
            return ServiceMetaDataAtDB(**row)

    async def create_service(
        self,
        new_service: ServiceMetaDataAtDB,
        new_service_access_rights: List[ServiceAccessRightsAtDB],
    ) -> ServiceMetaDataAtDB:

        for access_rights in new_service_access_rights:
            if (
                access_rights.key != new_service.key
                or access_rights.version != new_service.version
            ):
                raise ValueError(
                    f"{access_rights} does not correspond to service {new_service.key}:{new_service.version}"
                )

        async with self.db_engine.connect() as conn:
            # NOTE: this ensure proper rollback in case of issue
            async with conn.begin() as _transaction:
                result = await conn.execute(
                    # pylint: disable=no-value-for-parameter
                    services_meta_data.insert()
                    .values(**new_service.dict(by_alias=True))
                    .returning(literal_column("*"))
                )
                row = result.first()
                assert row  # nosec
                created_service = ServiceMetaDataAtDB(**row)

                for access_rights in new_service_access_rights:
                    insert_stmt = pg_insert(services_access_rights).values(
                        **access_rights.dict(by_alias=True)
                    )
                    await conn.execute(insert_stmt)
        return created_service

    async def update_service(
        self, patched_service: ServiceMetaDataAtDB
    ) -> ServiceMetaDataAtDB:
        # update the services_meta_data table
        async with self.db_engine.connect() as conn:
            result = await conn.execute(
                # pylint: disable=no-value-for-parameter
                services_meta_data.update()
                .where(
                    (services_meta_data.c.key == patched_service.key)
                    & (services_meta_data.c.version == patched_service.version)
                )
                .values(**patched_service.dict(by_alias=True, exclude_unset=True))
                .returning(literal_column("*"))
            )
            row = result.first()
            assert row  # nosec
        updated_service = ServiceMetaDataAtDB(**row)
        return updated_service

    async def get_service_access_rights(
        self,
        key: str,
        version: str,
        product_name: Optional[str] = None,
    ) -> List[ServiceAccessRightsAtDB]:
        """
        - If product_name is not specificed, then all are considered in the query
        """
        services_in_db = []
        search_expression = (services_access_rights.c.key == key) & (
            services_access_rights.c.version == version
        )
        if product_name:
            search_expression &= services_access_rights.c.product_name == product_name

        query = sa.select([services_access_rights]).where(search_expression)

        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(query):
                services_in_db.append(ServiceAccessRightsAtDB(**row))
        return services_in_db

    async def list_services_access_rights(
        self, key_versions: List[Tuple[str, str]], product_name: Optional[str] = None
    ) -> Dict[Tuple[str, str], List[ServiceAccessRightsAtDB]]:
        """Batch version of get_service_access_rights"""
        service_to_access_rights = defaultdict(list)
        query = (
            sa.select([services_access_rights])
            .select_from(services_access_rights)
            .where(
                tuple_(
                    services_access_rights.c.key, services_access_rights.c.version
                ).in_(key_versions)
                & (services_access_rights.c.product_name == product_name)
                if product_name
                else True
            )
        )
        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(query):
                service_to_access_rights[
                    (
                        row[services_access_rights.c.key],
                        row[services_access_rights.c.version],
                    )
                ].append(ServiceAccessRightsAtDB(**row))
        return service_to_access_rights

    async def upsert_service_access_rights(
        self, new_access_rights: List[ServiceAccessRightsAtDB]
    ) -> None:
        # update the services_access_rights table (some might be added/removed/modified)
        for rights in new_access_rights:
            insert_stmt = pg_insert(services_access_rights).values(
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
                async with self.db_engine.connect() as conn:
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
        async with self.db_engine.connect() as conn:
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

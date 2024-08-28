import itertools
import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import packaging.version
import sqlalchemy as sa
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.groups import GroupAtDB, GroupTypeInModel
from models_library.products import ProductName
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import GroupID, UserID
from psycopg2.errors import ForeignKeyViolation
from pydantic import PositiveInt, ValidationError, parse_obj_as
from simcore_postgres_database.utils_services import create_select_latest_services_query
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import and_, or_
from sqlalchemy.sql.expression import tuple_

from ...models.services_db import (
    ReleaseFromDB,
    ServiceAccessRightsAtDB,
    ServiceMetaDataAtDB,
    ServiceWithHistoryFromDB,
)
from ...models.services_specifications import ServiceSpecificationsAtDB
from ..tables import services_access_rights, services_meta_data, services_specifications
from ._base import BaseRepository
from ._services_sql import (
    AccessRightsClauses,
    can_get_service_stmt,
    get_service_history_stmt,
    get_service_stmt,
    list_latest_services_with_history_stmt,
    list_services_stmt,
    total_count_stmt,
)

_logger = logging.getLogger(__name__)


def _is_newer(
    old: ServiceSpecificationsAtDB | None,
    new: ServiceSpecificationsAtDB,
) -> bool:
    return old is None or (
        packaging.version.parse(old.service_version)
        < packaging.version.parse(new.service_version)
    )


def _merge_specs(
    everyone_spec: ServiceSpecificationsAtDB | None,
    team_specs: dict[GroupID, ServiceSpecificationsAtDB],
    user_spec: ServiceSpecificationsAtDB | None,
) -> dict[str, Any]:
    merged_spec = {}
    for spec in itertools.chain([everyone_spec], team_specs.values(), [user_spec]):
        if spec is not None:
            merged_spec.update(spec.dict(include={"sidecar", "service"}))
    return merged_spec


class ServicesRepository(BaseRepository):
    """
    API that operates on services_access_rights and services_meta_data tables
    """

    async def list_services(
        self,
        *,
        gids: list[int] | None = None,
        execute_access: bool | None = None,
        write_access: bool | None = None,
        combine_access_with_and: bool | None = True,
        product_name: str | None = None,
    ) -> list[ServiceMetaDataAtDB]:

        async with self.db_engine.connect() as conn:
            return [
                ServiceMetaDataAtDB.from_orm(row)
                async for row in await conn.stream(
                    list_services_stmt(
                        gids=gids,
                        execute_access=execute_access,
                        write_access=write_access,
                        combine_access_with_and=combine_access_with_and,
                        product_name=product_name,
                    )
                )
            ]

    async def list_service_releases(
        self,
        key: str,
        *,
        major: int | None = None,
        minor: int | None = None,
        limit_count: int | None = None,
    ) -> list[ServiceMetaDataAtDB]:
        """Lists LAST n releases of a given service, sorted from latest first

        major, minor is used to filter as major.minor.* or major.*
        limit_count limits returned value. None or non-positive values returns all matches
        """
        if minor is not None and major is None:
            msg = "Expected only major.*.* or major.minor.*"
            raise ValueError(msg)

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
            sa.select(services_meta_data)
            .where(search_condition)
            .order_by(sa.desc(services_meta_data.c.version))
        )

        if limit_count and limit_count > 0:
            query = query.limit(limit_count)

        async with self.db_engine.connect() as conn:
            releases = [
                ServiceMetaDataAtDB.from_orm(row)
                async for row in await conn.stream(query)
            ]

        # Now sort naturally from latest first: (This is lame, the sorting should be done in the db)
        def _by_version(x: ServiceMetaDataAtDB) -> packaging.version.Version:
            return packaging.version.parse(x.version)

        return sorted(releases, key=_by_version, reverse=True)

    async def get_latest_release(self, key: str) -> ServiceMetaDataAtDB | None:
        """Returns last release or None if service was never released"""
        services_latest = create_select_latest_services_query().alias("services_latest")

        query = (
            sa.select(services_meta_data)
            .select_from(
                services_latest.join(
                    services_meta_data,
                    (services_meta_data.c.key == services_latest.c.key)
                    & (services_meta_data.c.version == services_latest.c.latest),
                )
            )
            .where(services_latest.c.key == key)
        )
        async with self.db_engine.connect() as conn:
            result = await conn.execute(query)
            row = result.first()
        if row:
            return ServiceMetaDataAtDB.from_orm(row)
        return None  # mypy

    async def get_service(
        self,
        key: str,
        version: str,
        *,
        gids: list[int] | None = None,
        execute_access: bool | None = None,
        write_access: bool | None = None,
        product_name: str | None = None,
    ) -> ServiceMetaDataAtDB | None:

        query = sa.select(services_meta_data).where(
            (services_meta_data.c.key == key)
            & (services_meta_data.c.version == version)
        )
        if gids or execute_access or write_access:

            query = sa.select(services_meta_data).select_from(
                services_meta_data.join(services_access_rights)
            )

            conditions = [
                services_meta_data.c.key == key,
                services_meta_data.c.version == version,
            ]
            if gids:
                conditions.append(
                    or_(*[services_access_rights.c.gid == gid for gid in gids])
                )
            if execute_access is not None:
                conditions.append(services_access_rights.c.execute_access)
            if write_access is not None:
                conditions.append(services_access_rights.c.write_access)
            if product_name:
                conditions.append(services_access_rights.c.product_name == product_name)

            query = query.where(and_(*conditions))

        async with self.db_engine.connect() as conn:
            result = await conn.execute(query)
            row = result.first()
        if row:
            return ServiceMetaDataAtDB.from_orm(row)
        return None  # mypy

    async def create_or_update_service(
        self,
        new_service: ServiceMetaDataAtDB,
        new_service_access_rights: list[ServiceAccessRightsAtDB],
    ) -> ServiceMetaDataAtDB:
        for access_rights in new_service_access_rights:
            if (
                access_rights.key != new_service.key
                or access_rights.version != new_service.version
            ):
                msg = f"{access_rights} does not correspond to service {new_service.key}:{new_service.version}"
                raise ValueError(msg)

        async with self.db_engine.begin() as conn:
            # NOTE: this ensure proper rollback in case of issue
            result = await conn.execute(
                # pylint: disable=no-value-for-parameter
                services_meta_data.insert()
                .values(**new_service.dict(by_alias=True))
                .returning(literal_column("*"))
            )
            row = result.first()
            assert row  # nosec
            created_service = ServiceMetaDataAtDB.from_orm(row)

            for access_rights in new_service_access_rights:
                insert_stmt = pg_insert(services_access_rights).values(
                    **jsonable_encoder(access_rights, by_alias=True)
                )
                await conn.execute(insert_stmt)
        return created_service

    async def update_service(self, patched_service: ServiceMetaDataAtDB) -> None:

        stmt_update = (
            services_meta_data.update()
            .where(
                (services_meta_data.c.key == patched_service.key)
                & (services_meta_data.c.version == patched_service.version)
            )
            .values(
                **patched_service.dict(
                    by_alias=True,
                    exclude_unset=True,
                    exclude={"key", "version"},
                )
            )
        )
        async with self.db_engine.begin() as conn:
            await conn.execute(stmt_update)

    async def can_get_service(
        self,
        # access-rights
        product_name: ProductName,
        user_id: UserID,
        # get args
        key: ServiceKey,
        version: ServiceVersion,
    ) -> bool:
        """Returns False if it cannot get the service i.e. not found or does not have access"""
        async with self.db_engine.begin() as conn:
            result = await conn.execute(
                can_get_service_stmt(
                    product_name=product_name,
                    user_id=user_id,
                    access_rights=AccessRightsClauses.can_read,
                    service_key=key,
                    service_version=version,
                )
            )
            return bool(result.scalar())

    async def can_update_service(
        self,
        # access-rights
        product_name: ProductName,
        user_id: UserID,
        # get args
        key: ServiceKey,
        version: ServiceVersion,
    ) -> bool:
        async with self.db_engine.begin() as conn:
            result = await conn.execute(
                can_get_service_stmt(
                    product_name=product_name,
                    user_id=user_id,
                    access_rights=AccessRightsClauses.can_edit,
                    service_key=key,
                    service_version=version,
                )
            )
            return bool(result.scalar())

    async def get_service_with_history(
        self,
        # access-rights
        product_name: ProductName,
        user_id: UserID,
        # get args
        key: ServiceKey,
        version: ServiceVersion,
    ) -> ServiceWithHistoryFromDB | None:

        stmt_get = get_service_stmt(
            product_name=product_name,
            user_id=user_id,
            access_rights=AccessRightsClauses.can_read,
            service_key=key,
            service_version=version,
        )

        async with self.db_engine.begin() as conn:
            result = await conn.execute(stmt_get)
            row = result.one_or_none()

        if row:
            stmt_history = get_service_history_stmt(
                product_name=product_name,
                user_id=user_id,
                access_rights=AccessRightsClauses.can_read,
                service_key=key,
            )
            async with self.db_engine.begin() as conn:
                result = await conn.execute(stmt_history)
                row_h = result.one_or_none()

            return ServiceWithHistoryFromDB(
                key=row.key,
                version=row.version,
                # display
                name=row.name,
                description=row.description,
                thumbnail=row.thumbnail,
                version_display=row.version_display,
                # ownership
                owner_email=row.owner_email,
                # tagging
                classifiers=row.classifiers,
                quality=row.quality,
                # lifetime
                created=row.created,
                modified=row.modified,
                deprecated=row.deprecated,
                # releases
                history=row_h.history if row_h else [],
            )
        return None

    async def list_latest_services(
        self,
        *,
        # access-rights
        product_name: ProductName,
        user_id: UserID,
        # list args: pagination
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[PositiveInt, list[ServiceWithHistoryFromDB]]:

        # get page
        stmt_total = total_count_stmt(
            product_name=product_name,
            user_id=user_id,
            access_rights=AccessRightsClauses.can_read,
        )
        stmt_page = list_latest_services_with_history_stmt(
            product_name=product_name,
            user_id=user_id,
            access_rights=AccessRightsClauses.can_read,
            limit=limit,
            offset=offset,
        )

        async with self.db_engine.begin() as conn:
            result = await conn.execute(stmt_total)
            total_count = result.scalar() or 0

            result = await conn.execute(stmt_page)
            rows = result.fetchall()
            assert len(rows) <= total_count  # nosec

        # compose history with latest
        items_page = [
            ServiceWithHistoryFromDB(
                key=r.key,
                version=r.version,
                # display
                name=r.name,
                description=r.description,
                thumbnail=r.thumbnail,
                version_display=r.version_display,
                # ownership
                owner_email=r.owner_email,
                # tagging
                classifiers=r.classifiers,
                quality=r.quality,
                # lifetime
                created=r.created,
                modified=r.modified,
                deprecated=r.deprecated,
                # releases
                history=r.history,
            )
            for r in rows
        ]

        return (total_count, items_page)

    async def get_service_history(
        self,
        # access-rights
        product_name: ProductName,
        user_id: UserID,
        # get args
        key: ServiceKey,
    ) -> list[ReleaseFromDB] | None:

        stmt_history = get_service_history_stmt(
            product_name=product_name,
            user_id=user_id,
            access_rights=AccessRightsClauses.can_read,
            service_key=key,
        )
        async with self.db_engine.begin() as conn:
            result = await conn.execute(stmt_history)
            row = result.one_or_none()

        return parse_obj_as(list[ReleaseFromDB], row.history) if row else None

    # Service Access Rights ----

    async def get_service_access_rights(
        self,
        key: str,
        version: str,
        product_name: str | None = None,
    ) -> list[ServiceAccessRightsAtDB]:
        """
        - If product_name is not specificed, then all are considered in the query
        """
        search_expression = (services_access_rights.c.key == key) & (
            services_access_rights.c.version == version
        )
        if product_name:
            search_expression &= services_access_rights.c.product_name == product_name

        query = sa.select(services_access_rights).where(search_expression)

        async with self.db_engine.connect() as conn:
            return [
                ServiceAccessRightsAtDB.from_orm(row)
                async for row in await conn.stream(query)
            ]

    async def list_services_access_rights(
        self,
        key_versions: Iterable[tuple[str, str]],
        product_name: str | None = None,
    ) -> dict[tuple[str, str], list[ServiceAccessRightsAtDB]]:
        """Batch version of get_service_access_rights"""
        service_to_access_rights = defaultdict(list)
        query = (
            sa.select(services_access_rights)
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
                service_to_access_rights[(row.key, row.version)].append(
                    ServiceAccessRightsAtDB.from_orm(row)
                )
        return service_to_access_rights

    async def upsert_service_access_rights(
        self, new_access_rights: list[ServiceAccessRightsAtDB]
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
                set_=rights.dict(
                    by_alias=True,
                    exclude_unset=True,
                    exclude={"key", "version", "gid", "product_name"},
                ),
            )
            try:
                async with self.db_engine.begin() as conn:
                    result = await conn.execute(on_update_stmt)
                    assert result  # nosec
            except ForeignKeyViolation:
                _logger.warning(
                    "The service %s:%s is missing from services_meta_data",
                    rights.key,
                    rights.version,
                )

    async def delete_service_access_rights(
        self, delete_access_rights: list[ServiceAccessRightsAtDB]
    ) -> None:
        async with self.db_engine.begin() as conn:
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

    # Service Specs ---
    async def get_service_specifications(
        self,
        key: ServiceKey,
        version: ServiceVersion,
        groups: tuple[GroupAtDB, ...],
        *,
        allow_use_latest_service_version: bool = False,
    ) -> ServiceSpecifications | None:
        """returns the service specifications for service 'key:version' and for 'groups'
            returns None if nothing found

        :param allow_use_latest_service_version: if True, then the latest version of the specs will be returned, defaults to False
        """
        _logger.debug(
            "getting specifications from db for %s", f"{key}:{version} for {groups=}"
        )
        gid_to_group_map = {group.gid: group for group in groups}

        everyone_specs = None
        primary_specs = None
        teams_specs: dict[GroupID, ServiceSpecificationsAtDB] = {}

        queried_version = packaging.version.parse(version)
        # we should instead use semver enabled postgres [https://pgxn.org/dist/semver/doc/semver.html]
        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(
                sa.select(services_specifications).where(
                    (services_specifications.c.service_key == key)
                    & (
                        (services_specifications.c.service_version == version)
                        if not allow_use_latest_service_version
                        else True
                    )
                    & (services_specifications.c.gid.in_(group.gid for group in groups))
                ),
            ):
                try:
                    _logger.debug("found following %s", f"{row=}")
                    # validate the specs first
                    db_service_spec = ServiceSpecificationsAtDB.from_orm(row)
                    db_spec_version = packaging.version.parse(
                        db_service_spec.service_version
                    )
                    if allow_use_latest_service_version and (
                        db_spec_version > queried_version
                    ):
                        # NOTE: in this case we look for the latest version only (e.g <=queried_version)
                        # and we skip them if they are above
                        continue
                    # filter by group type
                    group = gid_to_group_map[row.gid]
                    if (group.group_type == GroupTypeInModel.STANDARD) and _is_newer(
                        teams_specs.get(db_service_spec.gid),
                        db_service_spec,
                    ):
                        teams_specs[db_service_spec.gid] = db_service_spec
                    elif (group.group_type == GroupTypeInModel.EVERYONE) and _is_newer(
                        everyone_specs, db_service_spec
                    ):
                        everyone_specs = db_service_spec
                    elif (group.group_type == GroupTypeInModel.PRIMARY) and _is_newer(
                        primary_specs, db_service_spec
                    ):
                        primary_specs = db_service_spec

                except ValidationError as exc:
                    _logger.warning(
                        "skipping service specifications for group '%s' as invalid: %s",
                        f"{row.gid}",
                        f"{exc}",
                    )

        if merged_specifications := _merge_specs(
            everyone_specs, teams_specs, primary_specs
        ):
            return ServiceSpecifications.parse_obj(merged_specifications)
        return None  # mypy

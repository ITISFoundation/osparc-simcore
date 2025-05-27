import itertools
import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import packaging.version
import sqlalchemy as sa
from common_library.groups_enums import GroupType
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.groups import GroupAtDB, GroupID
from models_library.products import ProductName
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from psycopg2.errors import ForeignKeyViolation
from pydantic import PositiveInt, TypeAdapter, ValidationError
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.services import (
    services_access_rights,
    services_meta_data,
)
from simcore_postgres_database.models.services_compatibility import (
    services_compatibility,
)
from simcore_postgres_database.models.services_specifications import (
    services_specifications,
)
from simcore_postgres_database.utils_repos import pass_or_acquire_connection
from simcore_postgres_database.utils_services import create_select_latest_services_query
from sqlalchemy import sql
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..models.services_db import (
    ReleaseDBGet,
    ServiceAccessRightsDB,
    ServiceDBFilters,
    ServiceMetaDataDBCreate,
    ServiceMetaDataDBGet,
    ServiceMetaDataDBPatch,
    ServiceWithHistoryDBGet,
)
from ..models.services_specifications import ServiceSpecificationsAtDB
from . import _services_sql
from ._base import BaseRepository
from ._services_sql import (
    SERVICES_META_DATA_COLS,
    AccessRightsClauses,
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
            merged_spec.update(spec.model_dump(include={"sidecar", "service"}))
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
    ) -> list[ServiceMetaDataDBGet]:

        async with self.db_engine.connect() as conn:
            return [
                ServiceMetaDataDBGet.model_validate(row)
                async for row in await conn.stream(
                    _services_sql.list_services_stmt(
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
    ) -> list[ServiceMetaDataDBGet]:
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
            sa.select(*SERVICES_META_DATA_COLS)
            .where(search_condition)
            .order_by(sa.desc(services_meta_data.c.version))
        )

        if limit_count and limit_count > 0:
            query = query.limit(limit_count)

        async with self.db_engine.connect() as conn:
            releases = [
                ServiceMetaDataDBGet.model_validate(row)
                async for row in await conn.stream(query)
            ]

        # Now sort naturally from latest first: (This is lame, the sorting should be done in the db)
        def _by_version(x: ServiceMetaDataDBGet) -> packaging.version.Version:
            return packaging.version.parse(x.version)

        return sorted(releases, key=_by_version, reverse=True)

    async def get_latest_release(self, key: str) -> ServiceMetaDataDBGet | None:
        """Returns last release or None if service was never released"""
        services_latest = create_select_latest_services_query().alias("services_latest")

        query = (
            sa.select(*SERVICES_META_DATA_COLS)
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
            return ServiceMetaDataDBGet.model_validate(row)
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
    ) -> ServiceMetaDataDBGet | None:

        query = sa.select(*SERVICES_META_DATA_COLS)

        if gids or execute_access or write_access:
            conditions = [
                services_meta_data.c.key == key,
                services_meta_data.c.version == version,
            ]
            if gids:
                conditions.append(
                    sql.or_(*[services_access_rights.c.gid == gid for gid in gids])
                )
            if execute_access is not None:
                conditions.append(services_access_rights.c.execute_access)
            if write_access is not None:
                conditions.append(services_access_rights.c.write_access)
            if product_name:
                conditions.append(services_access_rights.c.product_name == product_name)

            query = query.select_from(
                services_meta_data.join(services_access_rights)
            ).where(sql.and_(*conditions))
        else:
            query = query.where(
                (services_meta_data.c.key == key)
                & (services_meta_data.c.version == version)
            )

        async with self.db_engine.connect() as conn:
            result = await conn.execute(query)
            row = result.first()
        if row:
            return ServiceMetaDataDBGet.model_validate(row)
        return None  # mypy

    async def create_or_update_service(
        self,
        new_service: ServiceMetaDataDBCreate,
        new_service_access_rights: list[ServiceAccessRightsDB],
    ) -> ServiceMetaDataDBGet:
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
                .values(**new_service.model_dump(exclude_unset=True))
                .returning(*SERVICES_META_DATA_COLS)
            )
            row = result.first()
            assert row  # nosec
            created_service = ServiceMetaDataDBGet.model_validate(row)

            for access_rights in new_service_access_rights:
                insert_stmt = pg_insert(services_access_rights).values(
                    **jsonable_encoder(access_rights, by_alias=True)
                )
                await conn.execute(insert_stmt)
        return created_service

    async def update_service(
        self,
        service_key: ServiceKey,
        service_version: ServiceVersion,
        patched_service: ServiceMetaDataDBPatch,
    ) -> None:

        stmt_update = (
            services_meta_data.update()
            .where(
                (services_meta_data.c.key == service_key)
                & (services_meta_data.c.version == service_version)
            )
            .values(
                **patched_service.model_dump(
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
                _services_sql.can_get_service_stmt(
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
                _services_sql.can_get_service_stmt(
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
    ) -> ServiceWithHistoryDBGet | None:

        stmt_get = _services_sql.get_service_stmt(
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
            stmt_history = _services_sql.get_service_history_stmt(
                product_name=product_name,
                user_id=user_id,
                access_rights=AccessRightsClauses.can_read,
                service_key=key,
            )
            async with self.db_engine.begin() as conn:
                result = await conn.execute(stmt_history)
                row_h = result.one_or_none()

            return ServiceWithHistoryDBGet(
                key=row.key,
                version=row.version,
                # display
                name=row.name,
                description=row.description,
                description_ui=row.description_ui,
                icon=row.icon,
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

    async def list_all_services(
        self,
        *,
        # access-rights
        product_name: ProductName,
        user_id: UserID,
        # list args: pagination
        pagination_limit: int | None = None,
        pagination_offset: int | None = None,
        filters: ServiceDBFilters | None = None,
    ) -> tuple[PositiveInt, list[ServiceMetaDataDBGet]]:
        # Create base query that's common to both count and content queries
        base_query = (
            sa.select(services_meta_data.c.key, services_meta_data.c.version)
            .select_from(
                services_meta_data.join(
                    services_access_rights,
                    (services_meta_data.c.key == services_access_rights.c.key)
                    & (
                        services_meta_data.c.version == services_access_rights.c.version
                    ),
                ).join(
                    user_to_groups,
                    (user_to_groups.c.gid == services_access_rights.c.gid),
                )
            )
            .where(
                (services_access_rights.c.product_name == product_name)
                & (user_to_groups.c.uid == user_id)
                & AccessRightsClauses.can_read
            )
            .distinct()
        )

        if filters:
            base_query = _services_sql.apply_services_filters(base_query, filters)

        # Subquery for efficient counting and further joins
        subquery = base_query.subquery()

        # Count query - only counts distinct key/version pairs
        stmt_total = sa.select(sa.func.count()).select_from(subquery)

        # Content query - gets all details with pagination
        stmt_page = (
            sa.select(*SERVICES_META_DATA_COLS)
            .select_from(
                subquery.join(
                    services_meta_data,
                    (subquery.c.key == services_meta_data.c.key)
                    & (subquery.c.version == services_meta_data.c.version),
                )
            )
            .order_by(
                services_meta_data.c.key,
                sa.desc(_services_sql.by_version(services_meta_data.c.version)),
            )
        )

        # Apply pagination to content query
        if pagination_offset is not None:
            stmt_page = stmt_page.offset(pagination_offset)
        if pagination_limit is not None:
            stmt_page = stmt_page.limit(pagination_limit)

        # Execute both queries
        async with self.db_engine.connect() as conn:
            result = await conn.execute(stmt_total)
            total_count = result.scalar() or 0

            items_page = [
                ServiceMetaDataDBGet.model_validate(row)
                async for row in await conn.stream(stmt_page)
            ]

        return (total_count, items_page)

    async def list_latest_services(
        self,
        *,
        # access-rights
        product_name: ProductName,
        user_id: UserID,
        # list args: pagination
        pagination_limit: int | None = None,
        pagination_offset: int | None = None,
        filters: ServiceDBFilters | None = None,
    ) -> tuple[PositiveInt, list[ServiceWithHistoryDBGet]]:

        # get page
        stmt_total = _services_sql.latest_services_total_count_stmt(
            product_name=product_name,
            user_id=user_id,
            access_rights=AccessRightsClauses.can_read,
            filters=filters,
        )
        stmt_page = _services_sql.list_latest_services_stmt(
            product_name=product_name,
            user_id=user_id,
            access_rights=AccessRightsClauses.can_read,
            limit=pagination_limit,
            offset=pagination_offset,
            filters=filters,
        )

        async with self.db_engine.connect() as conn:
            result = await conn.execute(stmt_total)
            total_count = result.scalar() or 0

            result = await conn.execute(stmt_page)
            rows = result.fetchall()
            assert len(rows) <= total_count  # nosec

        # compose history with latest
        items_page = [
            ServiceWithHistoryDBGet(
                key=r.key,
                version=r.version,
                # display
                name=r.name,
                description=r.description,
                description_ui=r.description_ui,
                thumbnail=r.thumbnail,
                icon=r.icon,
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
                history=[],  # NOTE: for listing we will not add history. Only get service will produce history
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
    ) -> list[ReleaseDBGet]:
        """
        DEPRECATED: use get_service_history_page instead!
        """
        stmt_history = _services_sql.get_service_history_stmt(
            product_name=product_name,
            user_id=user_id,
            access_rights=AccessRightsClauses.can_read,
            service_key=key,
        )
        async with self.db_engine.connect() as conn:
            result = await conn.execute(stmt_history)
            row = result.one_or_none()

        return (
            TypeAdapter(list[ReleaseDBGet]).validate_python(row.history) if row else []
        )

    async def get_service_history_page(
        self,
        *,
        # access-rights
        product_name: ProductName,
        user_id: UserID,
        # get args
        key: ServiceKey,
        # list args: pagination
        pagination_limit: int | None = None,
        pagination_offset: int | None = None,
        filters: ServiceDBFilters | None = None,
    ) -> tuple[PositiveInt, list[ReleaseDBGet]]:

        base_stmt = (
            # Search on service (key, *) for (product_name, user_id w/ access)
            sql.select(
                services_meta_data.c.key,
                services_meta_data.c.version,
            )
            .select_from(
                services_meta_data.join(
                    services_access_rights,
                    (services_meta_data.c.key == services_access_rights.c.key)
                    & (
                        services_meta_data.c.version == services_access_rights.c.version
                    ),
                ).join(
                    user_to_groups,
                    (user_to_groups.c.gid == services_access_rights.c.gid),
                )
            )
            .where(
                (services_meta_data.c.key == key)
                & (services_access_rights.c.product_name == product_name)
                & (user_to_groups.c.uid == user_id)
                & AccessRightsClauses.can_read
            )
        )

        if filters:
            base_stmt = _services_sql.apply_services_filters(base_stmt, filters)

        base_subquery = base_stmt.subquery()

        # Query to count the TOTAL number of rows
        count_query = sql.select(sql.func.count()).select_from(base_subquery)

        # Query to retrieve page with additional columns, ordering, offset, and limit
        page_query = (
            sql.select(
                services_meta_data.c.key,
                services_meta_data.c.version,
                services_meta_data.c.version_display,
                services_meta_data.c.deprecated,
                services_meta_data.c.created,
                # CompatiblePolicyDict | None
                services_compatibility.c.custom_policy.label("compatibility_policy"),
            )
            .select_from(
                # NOTE: these joins are avoided in count_query
                base_subquery.join(
                    services_meta_data,
                    (base_subquery.c.key == services_meta_data.c.key)
                    & (base_subquery.c.version == services_meta_data.c.version),
                ).outerjoin(
                    services_compatibility,
                    (services_meta_data.c.key == services_compatibility.c.key)
                    & (
                        services_meta_data.c.version == services_compatibility.c.version
                    ),
                )
            )
            .order_by(sql.desc(_services_sql.by_version(services_meta_data.c.version)))
            .offset(pagination_offset)
            .limit(pagination_limit)
        )

        async with pass_or_acquire_connection(self.db_engine) as conn:
            total_count: PositiveInt = await conn.scalar(count_query) or 0

            result = await conn.stream(page_query)
            items: list[ReleaseDBGet] = [
                ReleaseDBGet.model_validate(row, from_attributes=True)
                async for row in result
            ]

        return total_count, items

    # Service Access Rights ----

    async def get_service_access_rights(
        self,
        key: str,
        version: str,
        product_name: str | None = None,
    ) -> list[ServiceAccessRightsDB]:
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
                ServiceAccessRightsDB.model_validate(row)
                async for row in await conn.stream(query)
            ]

    async def batch_get_services_access_rights(
        self,
        key_versions: Iterable[tuple[str, str]],
        product_name: str | None = None,
    ) -> dict[tuple[str, str], list[ServiceAccessRightsDB]]:
        """Batch version of get_service_access_rights"""
        service_to_access_rights = defaultdict(list)
        query = (
            sa.select(services_access_rights)
            .select_from(services_access_rights)
            .where(
                sql.tuple_(
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
                    ServiceAccessRightsDB.model_validate(row)
                )
        return service_to_access_rights

    async def upsert_service_access_rights(
        self, new_access_rights: list[ServiceAccessRightsDB]
    ) -> None:
        # update the services_access_rights table (some might be added/removed/modified)
        for rights in new_access_rights:
            insert_stmt = pg_insert(services_access_rights).values(
                **rights.model_dump(by_alias=True)
            )
            on_update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[
                    services_access_rights.c.key,
                    services_access_rights.c.version,
                    services_access_rights.c.gid,
                    services_access_rights.c.product_name,
                ],
                set_=rights.model_dump(
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
        self, delete_access_rights: list[ServiceAccessRightsDB]
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
                    db_service_spec = ServiceSpecificationsAtDB.model_validate(row)
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
                    if (group.group_type == GroupType.STANDARD) and _is_newer(
                        teams_specs.get(db_service_spec.gid),
                        db_service_spec,
                    ):
                        teams_specs[db_service_spec.gid] = db_service_spec
                    elif (group.group_type == GroupType.EVERYONE) and _is_newer(
                        everyone_specs, db_service_spec
                    ):
                        everyone_specs = db_service_spec
                    elif (group.group_type == GroupType.PRIMARY) and _is_newer(
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
            return ServiceSpecifications.model_validate(merged_specifications)
        return None  # mypy

import logging
from collections import defaultdict
from collections.abc import Iterable
from itertools import chain
from typing import Any, cast

import packaging.version
import sqlalchemy as sa
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.groups import GroupAtDB, GroupTypeInModel
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_db import ServiceAccessRightsAtDB, ServiceMetaDataAtDB
from models_library.users import GroupID
from psycopg2.errors import ForeignKeyViolation
from pydantic import ValidationError
from simcore_postgres_database.utils_services import create_select_latest_services_query
from sqlalchemy import literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import and_, or_
from sqlalchemy.sql.expression import tuple_
from sqlalchemy.sql.selectable import Select

from ...models.service_specifications import ServiceSpecificationsAtDB
from ..tables import services_access_rights, services_meta_data, services_specifications
from ._base import BaseRepository

logger = logging.getLogger(__name__)


def _make_list_services_query(
    gids: list[int] | None = None,
    execute_access: bool | None = None,
    write_access: bool | None = None,
    combine_access_with_and: bool | None = True,
    product_name: str | None = None,
) -> Select:
    query = sa.select(services_meta_data)
    if gids or execute_access or write_access:
        logic_operator = and_ if combine_access_with_and else or_
        default = bool(combine_access_with_and)
        access_query_part = logic_operator(
            services_access_rights.c.execute_access if execute_access else default,
            services_access_rights.c.write_access if write_access else default,
        )
        query = (
            sa.select(
                [services_meta_data],
            )
            .distinct(services_meta_data.c.key, services_meta_data.c.version)
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
        gids: list[int] | None = None,
        execute_access: bool | None = None,
        write_access: bool | None = None,
        combine_access_with_and: bool | None = True,
        product_name: str | None = None,
    ) -> list[ServiceMetaDataAtDB]:
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
                services_in_db.append(ServiceMetaDataAtDB.from_orm(row))
        return services_in_db

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

        releases = []
        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(query):
                releases.append(ServiceMetaDataAtDB.from_orm(row))

        # Now sort naturally from latest first: (This is lame, the sorting should be done in the db)
        def _by_version(x: ServiceMetaDataAtDB) -> packaging.version.Version:
            return cast(packaging.version.Version, packaging.version.parse(x.version))

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
            query = (
                sa.select(services_meta_data)
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
            return ServiceMetaDataAtDB.from_orm(row)
        return None  # mypy

    async def create_service(
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
                    **access_rights.dict(by_alias=True)
                )
                await conn.execute(insert_stmt)
        return created_service

    async def update_service(
        self, patched_service: ServiceMetaDataAtDB
    ) -> ServiceMetaDataAtDB:
        # update the services_meta_data table
        async with self.db_engine.begin() as conn:
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
        return ServiceMetaDataAtDB.from_orm(row)

    async def get_service_access_rights(
        self,
        key: str,
        version: str,
        product_name: str | None = None,
    ) -> list[ServiceAccessRightsAtDB]:
        """
        - If product_name is not specificed, then all are considered in the query
        """
        services_in_db = []
        search_expression = (services_access_rights.c.key == key) & (
            services_access_rights.c.version == version
        )
        if product_name:
            search_expression &= services_access_rights.c.product_name == product_name

        query = sa.select(services_access_rights).where(search_expression)

        async with self.db_engine.connect() as conn:
            async for row in await conn.stream(query):
                services_in_db.append(ServiceAccessRightsAtDB.from_orm(row))
        return services_in_db

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
                service_to_access_rights[
                    (
                        row[services_access_rights.c.key],
                        row[services_access_rights.c.version],
                    )
                ].append(ServiceAccessRightsAtDB.from_orm(row))
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
                logger.warning(
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

    async def get_service_specifications(
        self,
        key: ServiceKey,
        version: ServiceVersion,
        groups: tuple[GroupAtDB, ...],
        allow_use_latest_service_version: bool = False,
    ) -> ServiceSpecifications | None:
        """returns the service specifications for service 'key:version' and for 'groups'
            returns None if nothing found

        :param allow_use_latest_service_version: if True, then the latest version of the specs will be returned, defaults to False
        """
        logger.debug(
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
                    logger.debug("found following %s", f"{row=}")
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
                    logger.warning(
                        "skipping service specifications for group '%s' as invalid: %s",
                        f"{row.gid}",
                        f"{exc}",
                    )

        if merged_specifications := _merge_specs(
            everyone_specs, teams_specs, primary_specs
        ):
            return ServiceSpecifications.parse_obj(merged_specifications)
        return None  # mypy


def _is_newer(
    old: ServiceSpecificationsAtDB | None,
    new: ServiceSpecificationsAtDB,
):
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
    for spec in chain([everyone_spec], team_specs.values(), [user_spec]):
        if spec is not None:
            merged_spec.update(spec.dict(include={"sidecar", "service"}))
    return merged_spec

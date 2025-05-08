"""Includes manifest (services in the registry) and function-service (front-end/back-end services)"""

import logging
from contextlib import suppress
from typing import Literal

from models_library.api_schemas_catalog.services import (
    LatestServiceGet,
    MyServiceGet,
    ServiceGetV2,
    ServiceUpdateV2,
)
from models_library.api_schemas_directorv2.services import ServiceExtras
from models_library.basic_types import VersionStr
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.rest_pagination import PageLimitInt, PageTotalCount
from models_library.services_access import ServiceGroupAccessRightsV2
from models_library.services_history import Compatibility, ServiceRelease
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import HttpUrl, NonNegativeInt
from servicelib.logging_errors import (
    create_troubleshotting_log_kwargs,
)
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogInconsistentError,
    CatalogItemNotFoundError,
)

from ..clients.director import DirectorClient
from ..models.services_db import (
    ServiceAccessRightsAtDB,
    ServiceFiltersDB,
    ServiceMetaDataDBPatch,
    ServiceWithHistoryDBGet,
)
from ..models.services_ports import ServicePort
from ..repository.groups import GroupsRepository
from ..repository.services import ServicesRepository
from . import manifest
from .compatibility import evaluate_service_compatibility_map
from .function_services import is_function_service

_logger = logging.getLogger(__name__)


def _aggregate(
    service_db: ServiceWithHistoryDBGet,
    access_rights_db: list[ServiceAccessRightsAtDB],
    service_manifest: ServiceMetaDataPublished,
) -> dict:
    return {
        "key": service_db.key,
        "version": service_db.version,
        "name": service_db.name,
        "thumbnail": HttpUrl(service_db.thumbnail) if service_db.thumbnail else None,
        "icon": HttpUrl(service_db.icon) if service_db.icon else None,
        "description": service_db.description,
        "description_ui": service_db.description_ui,
        "version_display": service_db.version_display,
        "service_type": service_manifest.service_type,
        "contact": service_manifest.contact,
        "authors": service_manifest.authors,
        "owner": (service_db.owner_email if service_db.owner_email else None),
        "inputs": service_manifest.inputs or {},
        "outputs": service_manifest.outputs or {},
        "boot_options": service_manifest.boot_options,
        "min_visible_inputs": service_manifest.min_visible_inputs,
        "access_rights": {
            a.gid: ServiceGroupAccessRightsV2.model_construct(
                execute=a.execute_access,
                write=a.write_access,
            )
            for a in access_rights_db
        },
        "classifiers": service_db.classifiers,
        "quality": service_db.quality,
        # NOTE: history/release field is removed
    }


def _to_latest_get_schema(
    service_db: ServiceWithHistoryDBGet,
    access_rights_db: list[ServiceAccessRightsAtDB],
    service_manifest: ServiceMetaDataPublished,
) -> LatestServiceGet:

    assert len(service_db.history) == 0  # nosec

    return LatestServiceGet.model_validate(
        {
            **_aggregate(service_db, access_rights_db, service_manifest),
            "release": ServiceRelease.model_construct(
                version=service_db.version,
                version_display=service_db.version_display,
                released=service_db.created,
                retired=service_db.deprecated,
                compatibility=None,
            ),
        }
    )


def _to_get_schema(
    service_db: ServiceWithHistoryDBGet,
    access_rights_db: list[ServiceAccessRightsAtDB],
    service_manifest: ServiceMetaDataPublished,
    compatibility_map: dict[ServiceVersion, Compatibility | None] | None = None,
) -> ServiceGetV2:
    compatibility_map = compatibility_map or {}

    return ServiceGetV2.model_validate(
        {
            **_aggregate(service_db, access_rights_db, service_manifest),
            "history": [
                ServiceRelease.model_construct(
                    version=h.version,
                    version_display=h.version_display,
                    released=h.created,
                    retired=h.deprecated,
                    compatibility=compatibility_map.get(h.version),
                )
                for h in service_db.history
            ],
        }
    )


async def list_latest_catalog_services(
    repo: ServicesRepository,
    director_api: DirectorClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt | None,
    offset: NonNegativeInt = 0,
    filters: ServiceFiltersDB | None = None,
) -> tuple[PageTotalCount, list[LatestServiceGet]]:

    # defines the order
    total_count, services = await repo.list_latest_services(
        product_name=product_name,
        user_id=user_id,
        limit=limit,
        offset=offset,
        filters=filters,
    )

    if services:
        # injects access-rights
        access_rights: dict[tuple[str, str], list[ServiceAccessRightsAtDB]] = (
            await repo.batch_get_services_access_rights(
                ((sc.key, sc.version) for sc in services), product_name=product_name
            )
        )
        if not access_rights:
            raise CatalogForbiddenError(
                name="any service",
                user_id=user_id,
                product_name=product_name,
            )

    # Get manifest of those with access rights
    got = await manifest.get_batch_services(
        [
            (sc.key, sc.version)
            for sc in services
            if access_rights.get((sc.key, sc.version))
        ],
        director_api,
    )
    service_manifest = {
        (sc.key, sc.version): sc
        for sc in got
        if isinstance(sc, ServiceMetaDataPublished)
    }

    # Log a warning for missing services
    missing_services = [
        (sc.key, sc.version)
        for sc in services
        if (sc.key, sc.version) not in service_manifest
    ]
    if missing_services:
        msg = f"Found {len(missing_services)} services that are in the database but missing in the registry manifest"
        _logger.warning(
            **create_troubleshotting_log_kwargs(
                msg,
                error=CatalogInconsistentError(
                    missing_services=missing_services,
                    user_id=user_id,
                    product_name=product_name,
                    filters=filters,
                    limit=limit,
                    offset=offset,
                ),
                tip="This might be due to malfunction of the background-task or that this call was done while the sync was taking place",
            )
        )

    # Aggregate the services manifest and access-rights
    items = [
        _to_latest_get_schema(
            service_db=sc,
            access_rights_db=ar,
            service_manifest=sm,
        )
        for sc in services
        if (
            (ar := access_rights.get((sc.key, sc.version)))
            and (sm := service_manifest.get((sc.key, sc.version)))
        )
    ]

    return total_count, items


async def get_catalog_service(
    repo: ServicesRepository,
    director_api: DirectorClient,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ServiceGetV2:

    access_rights = await check_catalog_service_permissions(
        repo=repo,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        permission="read",
    )

    service = await repo.get_service_with_history(
        product_name=product_name,
        user_id=user_id,
        key=service_key,
        version=service_version,
    )
    if not service:
        # no service found provided `access_rights`
        raise CatalogForbiddenError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    service_manifest = await manifest.get_service(
        key=service_key,
        version=service_version,
        director_client=director_api,
    )

    compatibility_map = await evaluate_service_compatibility_map(
        repo,
        product_name=product_name,
        user_id=user_id,
        service_release_history=service.history,
    )

    return _to_get_schema(service, access_rights, service_manifest, compatibility_map)


async def update_catalog_service(
    repo: ServicesRepository,
    director_api: DirectorClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update: ServiceUpdateV2,
) -> ServiceGetV2:

    if is_function_service(service_key):
        raise CatalogForbiddenError(
            name=f"function service {service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    # Check access rights first
    access_rights = await check_catalog_service_permissions(
        repo=repo,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        permission="write",
    )

    # Updates service_meta_data
    await repo.update_service(
        service_key,
        service_version,
        ServiceMetaDataDBPatch.model_validate(
            update.model_dump(
                exclude_unset=True, exclude={"access_rights"}, mode="json"
            ),
        ),
    )

    # Updates service_access_rights (they can be added/removed/modified)
    if update.access_rights:

        # before
        previous_gids = [r.gid for r in access_rights]

        # new
        new_access_rights = [
            ServiceAccessRightsAtDB(
                key=service_key,
                version=service_version,
                gid=gid,
                execute_access=rights.execute,
                write_access=rights.write,
                product_name=product_name,
            )
            for gid, rights in update.access_rights.items()
        ]
        await repo.upsert_service_access_rights(new_access_rights)

        # then delete the ones that were removed
        removed_access_rights = [
            ServiceAccessRightsAtDB(
                key=service_key,
                version=service_version,
                gid=gid,
                product_name=product_name,
            )
            for gid in previous_gids
            if gid not in update.access_rights
        ]
        await repo.delete_service_access_rights(removed_access_rights)

    return await get_catalog_service(
        repo=repo,
        director_api=director_api,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )


async def check_catalog_service_permissions(
    repo: ServicesRepository,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    permission: Literal["read", "write"],
) -> list[ServiceAccessRightsAtDB]:
    """Raises if the service cannot be accessed with the specified permission level

    Args:
        repo: Repository for services
        product_name: Product name
        user_id: User ID
        service_key: Service key
        service_version: Service version
        permission: Permission level to check, either "read" or "write".

    Raises:
        CatalogItemNotFoundError: service (key,version) not found
        CatalogForbiddenError: insufficient access rights to get the requested access
    """

    access_rights = await repo.get_service_access_rights(
        key=service_key,
        version=service_version,
        product_name=product_name,
    )
    if not access_rights:
        raise CatalogItemNotFoundError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    has_permission = False
    if permission == "read":
        has_permission = await repo.can_get_service(
            product_name=product_name,
            user_id=user_id,
            key=service_key,
            version=service_version,
        )
    elif permission == "write":
        has_permission = await repo.can_update_service(
            product_name=product_name,
            user_id=user_id,
            key=service_key,
            version=service_version,
        )

    if not has_permission:
        raise CatalogForbiddenError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    return access_rights


async def batch_get_user_services(
    repo: ServicesRepository,
    groups_repo: GroupsRepository,
    *,
    product_name: ProductName,
    user_id: UserID,
    ids: list[
        tuple[
            ServiceKey,
            ServiceVersion,
        ]
    ],
) -> list[MyServiceGet]:

    services_access_rights = await repo.batch_get_services_access_rights(
        key_versions=ids, product_name=product_name
    )

    user_groups = await groups_repo.list_user_groups(user_id=user_id)
    my_group_ids = {g.gid for g in user_groups}

    my_services = []
    for service_key, service_version in ids:

        # Evaluate user's access-rights to this service key:version
        access_rights = services_access_rights.get((service_key, service_version), [])
        my_access_rights = ServiceGroupAccessRightsV2(execute=False, write=False)
        for ar in access_rights:
            if ar.gid in my_group_ids:
                my_access_rights.execute |= ar.execute_access
                my_access_rights.write |= ar.write_access

        # Get service metadata
        service_db = await repo.get_service(
            product_name=product_name,
            key=service_key,
            version=service_version,
        )
        assert service_db  # nosec

        # Find service owner (if defined!)
        owner: GroupID | None = service_db.owner
        if not owner:
            # NOTE can be more than one. Just get first.
            with suppress(StopIteration):
                owner = next(
                    ar.gid
                    for ar in access_rights
                    if ar.write_access and ar.execute_access
                )

        # Evaluate `compatibility`
        compatibility: Compatibility | None = None
        if my_access_rights.execute or my_access_rights.write:
            history = await repo.get_service_history(
                # NOTE: that the service history might be different for each user
                # since access rights are defined on a version basis (i.e. one use can have access to v1 but ot to v2)
                product_name=product_name,
                user_id=user_id,
                key=service_key,
            )
            assert history  # nosec

            compatibility_map = await evaluate_service_compatibility_map(
                repo,
                product_name=product_name,
                user_id=user_id,
                service_release_history=history,
            )

            compatibility = compatibility_map.get(service_db.version)

        my_services.append(
            MyServiceGet(
                key=service_db.key,
                release=ServiceRelease(
                    version=service_db.version,
                    version_display=service_db.version_display,
                    released=service_db.created,
                    retired=service_db.deprecated,
                    compatibility=compatibility,
                ),
                owner=owner,
                my_access_rights=my_access_rights,
            )
        )

    return my_services


async def list_user_service_release_history(
    repo: ServicesRepository,
    *,
    # access-rights
    product_name: ProductName,
    user_id: UserID,
    # target service
    service_key: ServiceKey,
    # pagination
    limit: PageLimitInt | None = None,
    offset: NonNegativeInt | None = None,
    # filters
    filters: ServiceFiltersDB | None = None,
    # options
    include_compatibility: bool = False,
) -> tuple[PageTotalCount, list[ServiceRelease]]:

    total_count, history = await repo.get_service_history_page(
        # NOTE: that the service history might be different for each user
        # since access rights are defined on a version basis (i.e. one use can have access to v1 but ot to v2)
        product_name=product_name,
        user_id=user_id,
        key=service_key,
        limit=limit,
        offset=offset,
        filters=filters,
    )

    compatibility_map: dict[ServiceVersion, Compatibility | None] = {}
    if include_compatibility:
        msg = "This operation is heavy and for the moment is not necessary"
        raise NotImplementedError(msg)

    items = [
        # domain -> domain
        ServiceRelease.model_construct(
            version=h.version,
            version_display=h.version_display,
            released=h.created,
            retired=h.deprecated,
            compatibility=compatibility_map.get(h.version),
        )
        for h in history
    ]

    return total_count, items


async def get_user_services_ports(
    repo: ServicesRepository,
    director_api: DirectorClient,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> list[ServicePort]:
    """Get service ports (inputs and outputs) for a specific service version.

    Raises:
        CatalogItemNotFoundError: When service is not found
        CatalogForbiddenError: When user doesn't have access rights
    """

    # Check access rights first
    await check_catalog_service_permissions(
        repo=repo,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        permission="read",
    )

    # Get service ports from manifest
    return await manifest.get_service_ports(
        director_client=director_api,
        key=service_key,
        version=service_version,
    )


async def get_catalog_service_extras(
    director_api: DirectorClient, service_key: ServiceKey, service_version: VersionStr
) -> ServiceExtras:
    return await director_api.get_service_extras(
        service_key=service_key, service_version=service_version
    )

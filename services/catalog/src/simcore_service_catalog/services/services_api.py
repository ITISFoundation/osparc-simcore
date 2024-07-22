import logging

from models_library.api_schemas_catalog.services import (
    ServiceGetV2,
    ServiceGroupAccessRightsV2,
    ServiceUpdate,
)
from models_library.products import ProductName
from models_library.rest_pagination import PageLimitInt
from models_library.services_enums import ServiceType
from models_library.services_history import Compatibility, ServiceRelease
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import NonNegativeInt
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)
from simcore_service_catalog.models.services_db import (
    ServiceAccessRightsAtDB,
    ServiceMetaDataAtDB,
    ServiceWithHistoryFromDB,
)
from simcore_service_catalog.services import manifest
from simcore_service_catalog.services.director import DirectorApi

from ..db.repositories.services import ServicesRepository
from .compatibility import evaluate_service_compatibility_map
from .function_services import is_function_service

_logger = logging.getLogger(__name__)


def _deduce_service_type_from(key: str) -> ServiceType:
    for e in ServiceType:
        tag = e.value if e != ServiceType.COMPUTATIONAL else "comp"
        if tag in key:
            return e
    raise ValueError(key)


def _db_to_api_model(
    service_db: ServiceWithHistoryFromDB,
    access_rights_db: list[ServiceAccessRightsAtDB],
    service_manifest: ServiceMetaDataPublished,
    compatibility_map: dict[ServiceKey, Compatibility] | None = None,
) -> ServiceGetV2:
    compatibility_map = compatibility_map or {}
    assert (  # nosec
        _deduce_service_type_from(service_db.key) == service_manifest.service_type
    )

    return ServiceGetV2(
        key=service_db.key,
        version=service_db.version,
        name=service_db.name,
        thumbnail=service_db.thumbnail or None,
        description=service_db.description,
        version_display=service_db.version_display,
        type=service_manifest.service_type,
        contact=service_manifest.contact,
        authors=service_manifest.authors,
        owner=service_db.owner_email or None,
        inputs=service_manifest.inputs or {},
        outputs=service_manifest.outputs or {},
        boot_options=service_manifest.boot_options,
        min_visible_inputs=service_manifest.min_visible_inputs,
        access_rights={
            a.gid: ServiceGroupAccessRightsV2.construct(
                execute=a.execute_access,
                write=a.write_access,
            )
            for a in access_rights_db
        },
        classifiers=service_db.classifiers,
        quality=service_db.quality,
        history=[
            ServiceRelease.construct(
                version=h.version,
                released=h.created,
                retired=h.deprecated,
                compatibility=compatibility_map.get(h.version),
            )
            for h in service_db.history
        ],
    )


async def list_services_paginated(
    repo: ServicesRepository,
    director_api: DirectorApi,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt | None,
    offset: NonNegativeInt = 0,
) -> tuple[NonNegativeInt, list[ServiceGetV2]]:

    # defines the order
    total_count, services = await repo.list_latest_services(
        product_name=product_name, user_id=user_id, limit=limit, offset=offset
    )

    # injects access-rights
    access_rights: dict[
        tuple[str, str], list[ServiceAccessRightsAtDB]
    ] = await repo.list_services_access_rights(
        ((s.key, s.version) for s in services), product_name=product_name
    )
    if not access_rights:
        raise CatalogForbiddenError(
            name="any service",
            user_id=user_id,
            product_name=product_name,
        )

    # get manifest of those with access rights
    got = await manifest.get_batch_services(
        [(s.key, s.version) for s in services if access_rights.get((s.key, s.version))],
        director_api,
    )
    service_manifest = {
        (s.key, s.version): s for s in got if isinstance(s, ServiceMetaDataPublished)
    }

    items = [
        _db_to_api_model(
            service_db=s, access_rights_db=ar, service_manifest=sm, compatibility_map=cm
        )
        for s in services
        if (
            (ar := access_rights.get((s.key, s.version)))
            and (sm := service_manifest.get((s.key, s.version)))
            and (
                # NOTE: This operation might be resource-intensive.
                # It is temporarily implemented on a trial basis.
                cm := await evaluate_service_compatibility_map(
                    repo,
                    product_name=product_name,
                    user_id=user_id,
                    service_release_history=s.history,
                )
            )
        )
    ]

    return total_count, items


async def get_service(
    repo: ServicesRepository,
    director_api: DirectorApi,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ServiceGetV2:

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

    service = await repo.get_service_with_history(
        product_name=product_name,
        user_id=user_id,
        key=service_key,
        version=service_version,
    )
    if not service:
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

    return _db_to_api_model(service, access_rights, service_manifest, compatibility_map)


async def update_service(
    repo: ServicesRepository,
    director_api: DirectorApi,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update: ServiceUpdate,
) -> ServiceGetV2:

    if is_function_service(service_key):
        raise CatalogForbiddenError(
            name=f"function service {service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    if not await repo.get_service_access_rights(
        key=service_key, version=service_version, product_name=product_name
    ):
        raise CatalogItemNotFoundError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    # Updates service_meta_data
    if not await repo.update_service(
        ServiceMetaDataAtDB(
            key=service_key,
            version=service_version,
            **update.dict(exclude_unset=True),
        )
    ):
        raise CatalogForbiddenError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    # Updates service_access_rights (they can be added/removed/modified)
    if update.access_rights:

        # before
        current_access_rights = await repo.get_service_access_rights(
            service_key, service_version, product_name=product_name
        )
        before_gids = [r.gid for r in current_access_rights]

        # new
        new_access_rights = [
            ServiceAccessRightsAtDB(
                key=service_key,
                version=service_version,
                gid=gid,
                execute_access=rights.execute_access,
                write_access=rights.write_access,
                product_name=product_name,
            )
            for gid, rights in update.access_rights.items()
        ]
        await repo.upsert_service_access_rights(new_access_rights)

        # then delete the ones that were removed
        remove_gids = [gid for gid in before_gids if gid not in update.access_rights]
        delete_access_rights = [
            ServiceAccessRightsAtDB(
                key=service_key,
                version=service_version,
                gid=gid,
                product_name=product_name,
            )
            for gid in remove_gids
        ]
        await repo.delete_service_access_rights(delete_access_rights)

    return await get_service(
        repo=repo,
        director_api=director_api,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )


async def check_for_service(
    repo: ServicesRepository,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> None:
    """Raises if the service canot be read

    Raises:
        CatalogItemNotFoundError: service (key,version) not found
        CatalogForbiddenError: insufficient access rights to get read accss
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

    if not await repo.can_get_service(
        product_name=product_name,
        user_id=user_id,
        key=service_key,
        version=service_version,
    ):
        raise CatalogForbiddenError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

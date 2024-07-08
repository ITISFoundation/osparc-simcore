import logging

from models_library.api_schemas_catalog.services import (
    ServiceGetV2,
    ServiceGroupAccessRightsV2,
    ServiceUpdate,
)
from models_library.products import ProductName
from models_library.rest_pagination import PageLimitInt
from models_library.services_authoring import Author, Badge
from models_library.services_enums import ServiceType
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

from ..db.repositories.services import ServicesRepository
from .function_services import is_function_service

_logger = logging.getLogger(__name__)


def _deduce_service_type_from(key: str) -> ServiceType:
    for e in ServiceType:
        tag = e.value if e != ServiceType.COMPUTATIONAL else "comp"
        if tag in key:
            return e
    raise ValueError(key)


def _to_api_model(
    db: ServiceWithHistoryFromDB, db_ar: list[ServiceAccessRightsAtDB]
) -> ServiceGetV2:
    return ServiceGetV2(
        key=db.key,
        version=db.version,
        name=db.name,
        thumbnail=db.thumbnail or None,
        description=db.description,
        version_display=f"V{db.version}",  # rg.version_display,
        type=_deduce_service_type_from(db.key),  # rg.service_type,
        badges=[
            Badge.Config.schema_extra["example"],
        ],  # rg.badges,
        contact=Author.Config.schema_extra["examples"][0]["email"],  # rg.contact,
        authors=Author.Config.schema_extra["examples"],
        owner=db.owner_email or None,
        inputs={},  # rg.inputs,
        outputs={},  # rg.outputs,
        boot_options=None,  # rg.boot_options,
        min_visible_inputs=None,  # rg.min_visible_inputs,
        access_rights={
            a.gid: ServiceGroupAccessRightsV2.construct(
                execute=a.execute_access,
                write=a.write_access,
            )
            for a in db_ar
        },  # db.access_rights,
        classifiers=db.classifiers,
        quality=db.quality,
        history=[h.to_api_model() for h in db.history],
    )


async def list_services_paginated(
    repo: ServicesRepository,
    # image_registry,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt | None,
    offset: NonNegativeInt = 0,
) -> tuple[NonNegativeInt, list[ServiceGetV2]]:

    # defines the order
    total_count, services_in_db = await repo.list_latest_services(
        product_name=product_name, user_id=user_id, limit=limit, offset=offset
    )

    # injects access-rights
    services_access_rights: dict[
        tuple[str, str], list[ServiceAccessRightsAtDB]
    ] = await repo.list_services_access_rights(
        ((s.key, s.version) for s in services_in_db), product_name=product_name
    )
    if not services_access_rights:
        raise CatalogForbiddenError(
            name="any service",
            user_id=user_id,
            product_name=product_name,
        )

    # NOTE: aggregates published (i.e. not editable) is still missing in this version
    items = [
        _to_api_model(db, db_ar)
        for db in services_in_db
        if (db_ar := services_access_rights.get((db.key, db.version)))
    ]

    return total_count, items


async def get_service(
    repo: ServicesRepository,
    # image_registry,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> ServiceGetV2:

    db_ar = await repo.get_service_access_rights(
        key=service_key,
        version=service_version,
        product_name=product_name,
    )
    if not db_ar:
        raise CatalogItemNotFoundError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    db = await repo.get_service_w_history(
        product_name=product_name,
        user_id=user_id,
        key=service_key,
        version=service_version,
    )
    if not db:
        raise CatalogForbiddenError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    return _to_api_model(db, db_ar)


async def update_service(
    repo: ServicesRepository,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update: ServiceUpdate,
) -> ServiceGetV2:
    assert repo  # nosec

    assert repo  # nosec
    assert product_name  # nosec
    assert user_id  # nosec

    if is_function_service(service_key):
        raise CatalogForbiddenError(
            name=f"function service {service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    db_ar = await repo.get_service_access_rights(
        key=service_key, version=service_version, product_name=product_name
    )
    if not db_ar:
        raise CatalogItemNotFoundError(
            name=f"{service_key}:{service_version}",
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=product_name,
        )

    # Updates service_meta_data
    db = await repo.update_service(
        ServiceMetaDataAtDB(
            key=service_key,
            version=service_version,
            **update.dict(exclude_unset=True),
        )
    )
    if not db:
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
        deleted_access_rights = [
            ServiceAccessRightsAtDB(
                key=service_key,
                version=service_version,
                gid=gid,
                product_name=product_name,
            )
            for gid in remove_gids
        ]
        await repo.delete_service_access_rights(deleted_access_rights)

    return await get_service(
        repo=repo,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )

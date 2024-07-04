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
from pydantic import NonNegativeInt, parse_obj_as
from simcore_service_catalog.models.services_db import (
    ServiceAccessRightsAtDB,
    ServiceWithHistoryFromDB,
)

from ..db.repositories.services import ServicesRepository

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

    db = await repo.get_service_w_history(
        product_name=product_name,
        user_id=user_id,
        key=service_key,
        version=service_version,
    )

    db_ar = await repo.get_service_access_rights(
        key=service_key, version=service_version, product_name=product_name
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

    _logger.debug("Moking update_service for %s...", f"{user_id=}")
    got = parse_obj_as(ServiceGetV2, ServiceGetV2.Config.schema_extra["examples"][0])
    got.key = service_key
    got.version = service_version
    return got.copy(update=update.dict(exclude_unset=True))

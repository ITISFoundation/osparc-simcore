from models_library.api_schemas_catalog.services import ServiceGetV2
from models_library.products import ProductName
from models_library.rest_pagination import PageLimitInt
from models_library.services_authoring import Author, Badge
from models_library.services_enums import ServiceType
from models_library.users import UserID
from pydantic import NonNegativeInt

from ..db.repositories.services import ServicesRepository


def _deduce_service_type_from(key: str) -> ServiceType:
    for e in ServiceType:
        if e.value in key:
            return e
    raise ValueError


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

    # # aggregates published (i.e. not editable)
    # got_batch = await image_registry.batch_get_services(
    #     services=[(s.key, s.version) for s in services_in_db],
    #     select=[
    #         "key",
    #         "version",
    #         "version_display",
    #         "service_type",
    #         "badges",
    #         "contact",
    #         "authors",
    #         "inputs",
    #         "outputs",
    #         "boot_options",
    #         "min_visible_inputs",
    #     ],
    # )
    # services_in_registry = {(i.key, i.version): i for i in got_batch.items}

    items = [
        ServiceGetV2(
            key=db.key,
            version=db.version,
            name=db.name,
            thumbnail=db.thumbnail or None,
            description=db.description,
            version_display=f"V{db.version}",  # rg.version_display,
            type=_deduce_service_type_from(db.key),  # rg.service_type,
            badges=Badge.Config.schema_extra["example"],  # rg.badges,
            contact=Author.Config.schema_extra["examples"][0]["email"],  # rg.contact,
            authors=Author.Config.schema_extra["examples"],
            owner=db.owner_email or None,
            inputs={},  # rg.inputs,
            outputs={},  # rg.outputs,
            boot_options=None,  # rg.boot_options,
            min_visible_inputs=None,  # rg.min_visible_inputs,
            access_rights=db.access_rights,
            classifiers=db.classifiers,
            quality=db.quality,
            history=db.history,
        )
        for db in services_in_db
        # if (rg := services_in_registry.get((db.key, db.version)))
    ]

    return total_count, items

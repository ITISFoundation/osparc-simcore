from models_library.api_schemas_catalog.services import ServiceGetV2
from models_library.products import ProductName
from models_library.rest_pagination import PageLimitInt
from models_library.users import UserID
from pydantic import NonNegativeInt

from ..db.repositories.services import ServicesRepository


async def list_services_paginated(
    repo: ServicesRepository,
    image_registry,  # TODO: image or director
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt | None,
    offset: NonNegativeInt = 0,
) -> tuple[NonNegativeInt, list[ServiceGetV2]]:

    # defines the order
    total_count, editable_services = await repo.list_latest_services(
        product_name=product_name, user_id=user_id, limit=limit, offset=offset
    )

    # aggregates published (i.e. not editable)
    # TODO: anticipate values we wish, do not transmit everything?
    got_batch = await image_registry.batch_get_services(
        services=[(s.key, s.version) for s in editable_services],
        select=[
            "key",
            "version",
            "version_display",
            "service_type",
            "badges",
            "contact",
            "authors",
            "inputs",
            "outputs",
            "boot_options",
            "min_visible_inputs",
        ],
    )
    published_services = {(i.key, i.version): i for i in got_batch.items}

    items = []
    for edit in editable_services:
        if read := published_services.get((edit.key, edit.version)):
            items.append(
                ServiceGetV2(
                    key=read.key,
                    version=read.version,
                    name=edit.name,
                    thumbnail=edit.thumbnail or None,
                    description=edit.description,
                    version_display=read.version_display,
                    type=read.service_type,
                    badges=read.badges,
                    contact=read.contact,
                    authors=read.authors,
                    owner=edit.owner_email or None,
                    inputs=read.inputs,
                    outputs=read.outputs,
                    boot_options=read.boot_options,
                    min_visible_inputs=read.min_visible_inputs,
                    access_rights=edit.access_rights,
                    classifiers=edit.classifiers,
                    quality=edit.quality,
                    history=edit.history,
                )
            )

    return total_count, items

from models_library.api_schemas_catalog.services import DEVServiceGet
from models_library.products import ProductName
from models_library.rest_pagination import PageLimitInt
from models_library.users import UserID
from pydantic import NonNegativeInt

from ..db.repositories.services import ServicesRepository


async def list_services_paginated(
    repo: ServicesRepository,
    product_name: ProductName,
    user_id: UserID,
    limit: PageLimitInt | None,
    offset: NonNegativeInt = 0,
) -> tuple[NonNegativeInt, list[DEVServiceGet]]:

    total_count, services = await repo.list_services_with_history(
        product_name=product_name, user_id=user_id, limit=limit, offset=offset
    )

    # TODO: get_batch latest and fill

    items = [
        DEVServiceGet(
            name=None,
            thumbnail=None,
            description=None,
            access_rights=None,
            key=s.key,
            version=s.version,
            version_display=None,
            release_version=None,
            history=s.history,
        )
        for s in services
    ]
    return total_count, items

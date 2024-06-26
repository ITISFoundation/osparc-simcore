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

    # TODO: add access-rights needed

    # user_id
    items = await repo.list_services_with_history(
        product_name=product_name, user_id=user_id, limit=limit, offset=offset
    )
    # TODO: add more info on latest version!

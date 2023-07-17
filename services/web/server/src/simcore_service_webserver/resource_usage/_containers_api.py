from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import NonNegativeInt

from . import resource_usage_tracker_client as resource_tracker_client


async def list_containers_usage_by_user_name_and_product(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    offset: int,
    limit: NonNegativeInt,
):
    data: dict = await resource_tracker_client.list_containers_by_user_and_product(
        app=app, user_id=user_id, product_name=product_name, offset=offset, limit=limit
    )
    return data

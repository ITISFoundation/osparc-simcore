from aiohttp import web
from models_library.products import ProductName
from models_library.users import UserID


async def empty_trash(app: web.Application, product_name: ProductName, user_id: UserID):
    raise NotImplementedError

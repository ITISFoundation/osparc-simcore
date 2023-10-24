from aiohttp import web
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def create_api_keys(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    new: ApiKeyCreate
) -> ApiKeyGet:
    raise NotImplementedError


@router.expose()
async def delete_api_keys(
    app: web.Application, *, product_name: ProductName, user_id: UserID, api_key: str
):
    raise NotImplementedError

from aiohttp import web
from models_library.users import UserID
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from settings_library.s3 import S3Settings


async def get_or_create_temporary_token_for_user(
    app: web.Application, _user_id: UserID
) -> S3Settings:
    app_settings = app[APP_CONFIG_KEY]
    return app_settings.STORAGE_S3

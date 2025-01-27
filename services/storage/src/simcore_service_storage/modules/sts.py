"""
STS stands for Security Token Service. This is where temporary S3 token may be generated.
https://docs.aws.amazon.com/STS/latest/APIReference/welcome.html
"""

from aiohttp import web
from models_library.users import UserID
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from settings_library.s3 import S3Settings

from ..core.settings import Settings


async def get_or_create_temporary_token_for_user(
    app: web.Application, _user_id: UserID
) -> S3Settings:
    app_settings: Settings = app[APP_CONFIG_KEY]
    return app_settings.STORAGE_S3

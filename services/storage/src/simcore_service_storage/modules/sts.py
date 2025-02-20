"""
STS stands for Security Token Service. This is where temporary S3 token may be generated.
https://docs.aws.amazon.com/STS/latest/APIReference/welcome.html
"""

from fastapi import FastAPI
from models_library.users import UserID
from settings_library.s3 import S3Settings

from ..core.settings import get_application_settings


async def get_or_create_temporary_token_for_user(
    app: FastAPI, _user_id: UserID
) -> S3Settings:
    app_settings = get_application_settings(app)
    assert app_settings.STORAGE_S3  # nosec
    return app_settings.STORAGE_S3

from aiohttp import web
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ...constants import MSG_WEAK_PASSWORD
from ...settings import LoginSettingsForProduct


def check_password_length_or_raise(new_password: str, settings: LoginSettingsForProduct) -> None:
    """Rejects passwords shorter than the product's configured minimum length"""
    if len(new_password) < settings.LOGIN_PASSWORD_MIN_LENGTH:
        raise web.HTTPUnprocessableEntity(
            text=MSG_WEAK_PASSWORD.format(LOGIN_PASSWORD_MIN_LENGTH=settings.LOGIN_PASSWORD_MIN_LENGTH),
            content_type=MIMETYPE_APPLICATION_JSON,
        )

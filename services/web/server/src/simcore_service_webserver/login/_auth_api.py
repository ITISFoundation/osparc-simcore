from datetime import datetime

from aiohttp import web
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ..products.api import Product
from ..security.api import check_password, encrypt_password
from ._constants import MSG_UNKNOWN_EMAIL, MSG_WRONG_PASSWORD
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import ACTIVE, USER, get_user_name_from_email, validate_user_status


async def get_user_by_email(app: web.Application, *, email: str) -> dict:
    db: AsyncpgStorage = get_plugin_storage(app)
    return await db.get_user({"email": email})


async def create_user(
    app: web.Application,
    *,
    email: str,
    password: str,
    status: str,
    expires_at: datetime | None
) -> dict:
    db: AsyncpgStorage = get_plugin_storage(app)

    user: dict = await db.create_user(
        {
            "name": get_user_name_from_email(email),
            "email": email,
            "password_hash": encrypt_password(password),
            "status": status,
            "role": USER,
            "expires_at": expires_at,
        }
    )
    return user


async def check_authorized_user_or_raise(
    user: dict, product: Product, email: str, password: str
) -> dict:

    if not user:
        raise web.HTTPUnauthorized(
            reason=MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )

    validate_user_status(user=user, support_email=product.support_email)

    if not check_password(password, user["password_hash"]):
        raise web.HTTPUnauthorized(
            reason=MSG_WRONG_PASSWORD, content_type=MIMETYPE_APPLICATION_JSON
        )

    assert user["status"] == ACTIVE, "db corrupted. Invalid status"  # nosec
    assert user["email"] == email, "db corrupted. Invalid email"  # nosec
    return user

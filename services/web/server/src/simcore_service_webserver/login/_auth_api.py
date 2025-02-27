from datetime import datetime
from typing import Any

from aiohttp import web
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserStatus
from simcore_postgres_database.utils_users import UsersRepo

from ..db.plugin import get_database_engine
from ..groups.api import is_user_by_email_in_group
from ..products.models import Product
from ..security.api import check_password, encrypt_password
from ._constants import MSG_UNKNOWN_EMAIL, MSG_WRONG_PASSWORD
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import validate_user_status


async def get_user_by_email(app: web.Application, *, email: str) -> dict[str, Any]:
    db: AsyncpgStorage = get_plugin_storage(app)
    user = await db.get_user({"email": email})
    return dict(user) if user else {}


async def create_user(
    app: web.Application,
    *,
    email: str,
    password: str,
    status_upon_creation: UserStatus,
    expires_at: datetime | None,
) -> dict[str, Any]:

    async with get_database_engine(app).acquire() as conn:
        user = await UsersRepo.new_user(
            conn,
            email=email,
            password_hash=encrypt_password(password),
            status=status_upon_creation,
            expires_at=expires_at,
        )
        await UsersRepo.join_and_update_from_pre_registration_details(
            conn, user.id, user.email
        )
    return dict(user.items())


async def check_authorized_user_credentials_or_raise(
    user: dict[str, Any],
    password: str,
    product: Product,
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
    return user


async def check_authorized_user_in_product_or_raise(
    app: web.Application,
    *,
    user: dict,
    product: Product,
) -> None:
    """Checks whether user is registered in this product"""
    email = user.get("email", "").lower()
    product_group_id = product.group_id
    assert product_group_id is not None  # nosec

    if product_group_id is not None and not await is_user_by_email_in_group(
        app, user_email=email, group_id=product_group_id
    ):
        raise web.HTTPUnauthorized(
            reason=MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )

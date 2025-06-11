from datetime import datetime
from typing import Any

from aiohttp import web
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserStatus
from simcore_postgres_database.utils_repos import transaction_context
from simcore_postgres_database.utils_users import UsersRepo
from simcore_service_webserver.db.plugin import get_asyncpg_engine
from simcore_service_webserver.security import security_service

from ..groups import api as groups_service
from ..products.models import Product
from . import _login_service
from ._constants import MSG_UNKNOWN_EMAIL, MSG_WRONG_PASSWORD
from ._login_repository_legacy import AsyncpgStorage, get_plugin_storage


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

    async with transaction_context(get_asyncpg_engine(app)) as conn:
        user = await UsersRepo.new_user(
            conn,
            email=email,
            password_hash=security_service.encrypt_password(password),
            status=status_upon_creation,
            expires_at=expires_at,
        )
        await UsersRepo.link_and_update_user_from_pre_registration(
            conn, new_user_id=user.id, new_user_email=user.email
        )
    return dict(user._mapping)  # pylint: disable=protected-access # noqa: SLF001


async def check_authorized_user_credentials_or_raise(
    user: dict[str, Any],
    password: str,
    product: Product,
) -> dict:

    if not user:
        raise web.HTTPUnauthorized(
            reason=MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )

    _login_service.validate_user_status(user=user, support_email=product.support_email)

    if not security_service.check_password(password, user["password_hash"]):
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

    if (
        product_group_id is not None
        and not await groups_service.is_user_by_email_in_group(
            app, user_email=email, group_id=product_group_id
        )
    ):
        raise web.HTTPUnauthorized(
            reason=MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )

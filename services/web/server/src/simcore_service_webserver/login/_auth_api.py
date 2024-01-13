from datetime import datetime

from aiohttp import web
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserStatus
from simcore_postgres_database.utils_users import UsersRepo

from ..db.plugin import get_database_engine
from ..products.api import Product
from ..security.api import check_password, encrypt_password
from ._constants import MSG_UNKNOWN_EMAIL, MSG_WRONG_PASSWORD
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import validate_user_status


async def get_user_by_email(app: web.Application, *, email: str) -> dict:
    db: AsyncpgStorage = get_plugin_storage(app)
    user: dict = await db.get_user({"email": email})
    return user


async def create_user(
    app: web.Application,
    *,
    email: str,
    password: str,
    status: UserStatus,
    expires_at: datetime | None
) -> dict:

    async with get_database_engine(app).acquire() as conn:
        user = await UsersRepo.new_user(
            conn,
            email=email,
            password_hash=encrypt_password(password),
            status=status,
            expires_at=expires_at,
        )
    return dict(user.items())


async def check_authorized_user_or_raise(
    user: dict,
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

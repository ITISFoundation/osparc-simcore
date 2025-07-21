from datetime import datetime
from typing import TypedDict

from aiohttp import web
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.models.users import UserStatus
from simcore_postgres_database.utils_repos import transaction_context
from simcore_postgres_database.utils_users import UsersRepo

from ..db.plugin import get_asyncpg_engine
from ..groups import api as groups_service
from ..products.models import Product
from ..security import security_service
from . import _login_service
from .constants import MSG_UNKNOWN_EMAIL
from .errors import WrongPasswordError


class UserInfoDict(TypedDict):
    id: int
    name: str
    email: str
    role: str
    status: str
    first_name: str | None
    last_name: str | None
    phone: str | None


async def get_user_or_none(
    app: web.Application, *, email: str | None = None, user_id: int | None = None
) -> UserInfoDict | None:
    if email is None and user_id is None:
        msg = "Either email or user_id must be provided"
        raise ValueError(msg)

    asyncpg_engine = get_asyncpg_engine(app)
    repo = UsersRepo(asyncpg_engine)

    if email is not None:
        user_row = await repo.get_user_by_email_or_none(email=email.lower())
    else:
        assert user_id is not None
        user_row = await repo.get_user_by_id_or_none(user_id=user_id)

    if user_row is None:
        return None

    return UserInfoDict(
        id=user_row.id,
        name=user_row.name,
        email=user_row.email,
        role=user_row.role.value,
        status=user_row.status.value,
        first_name=user_row.first_name,
        last_name=user_row.last_name,
        phone=user_row.phone,
    )


async def create_user(
    app: web.Application,
    *,
    email: str,
    password: str,
    status_upon_creation: UserStatus,
    expires_at: datetime | None,
) -> UserInfoDict:

    asyncpg_engine = get_asyncpg_engine(app)
    repo = UsersRepo(asyncpg_engine)
    async with transaction_context(asyncpg_engine) as conn:
        user_row = await repo.new_user(
            conn,
            email=email,
            password_hash=security_service.encrypt_password(password),
            status=status_upon_creation,
            expires_at=expires_at,
        )
        await repo.link_and_update_user_from_pre_registration(
            conn,
            new_user_id=user_row.id,
            new_user_email=user_row.email,
            # FIXME: must fit product_name!!
        )
    return UserInfoDict(
        id=user_row.id,
        name=user_row.name,
        email=user_row.email,
        role=user_row.role.value,
        status=user_row.status.value,
        first_name=user_row.first_name,
        last_name=user_row.last_name,
        phone=user_row.phone,
    )


def check_not_null_user(user: UserInfoDict | None) -> UserInfoDict:
    if not user:
        raise web.HTTPUnauthorized(
            text=MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
        )
    return user


async def check_authorized_user_credentials(
    app: web.Application,
    user: UserInfoDict | None,
    *,
    password: str,
    product: Product,
) -> UserInfoDict:
    """

    Raises:
        WrongPasswordError: when password is invalid
        web.HTTPUnauthorized: 401

    Returns:
        user info dict
    """

    user = check_not_null_user(user)

    _login_service.validate_user_status(
        user_status=user["status"],
        user_role=user["role"],
        support_email=product.support_email,
    )

    repo = UsersRepo(get_asyncpg_engine(app))

    if not security_service.check_password(
        password, password_hash=await repo.get_password_hash(user_id=user["id"])
    ):
        raise WrongPasswordError(user_id=user["id"], product_name=product.name)
    return user


async def check_authorized_user_in_product(
    app: web.Application,
    *,
    user_email: str,
    product: Product,
) -> None:
    """Checks whether user is registered in this product


    Raises:
        web.HTTPUnauthorized: 401
    """

    product_group_id = product.group_id
    assert product_group_id is not None  # nosec

    if (
        product_group_id is not None
        and not await groups_service.is_user_by_email_in_group(
            app, user_email=user_email, group_id=product_group_id
        )
    ):
        raise web.HTTPUnauthorized(text=MSG_UNKNOWN_EMAIL)


async def update_user_password(
    app: web.Application,
    *,
    user_id: int,
    current_password: str,
    new_password: str,
    verify_current_password: bool = True,
) -> None:
    """Updates user password after verifying current password

    Keyword Arguments:
        verify_current_password -- whether to check current_password is valid (default: {True})

    Raises:
        WrongPasswordError: when current password is invalid
    """

    repo = UsersRepo(get_asyncpg_engine(app))

    if verify_current_password:
        # Get current password hash
        current_password_hash = await repo.get_password_hash(user_id=user_id)

        # Verify current password
        if not security_service.check_password(current_password, current_password_hash):
            raise WrongPasswordError(user_id=user_id)

    # Encrypt new password and update
    new_password_hash = security_service.encrypt_password(new_password)
    await repo.update_user_password_hash(
        user_id=user_id, password_hash=new_password_hash
    )

"""Aggregation service (login domain).

Glues the login, groups and products domains to create a ready-to-use user
account in a single operation. Used e.g. by the CLI to bootstrap the first
privileged user in an empty deployment.
"""

from aiohttp import web
from common_library.users_enums import UserRole
from models_library.products import ProductName
from simcore_postgres_database.models.users import UserStatus

from ..groups.groups_service import (
    auto_add_user_to_groups,
    auto_add_user_to_product_group,
)
from . import _auth_service
from .errors import UserAlreadyRegisteredError


async def create_account(
    app: web.Application,
    *,
    email: str,
    password: str,
    role: UserRole,
    product_name: ProductName,
    status_upon_creation: UserStatus = UserStatus.ACTIVE,
) -> _auth_service.UserInfoDict:
    """Creates a user account and wires its group and product memberships.

    Raises:
        UserAlreadyRegisteredError: if a user with this email already exists
    """
    if await _auth_service.get_user_or_none(app, email=email) is not None:
        raise UserAlreadyRegisteredError(email=email)

    user = await _auth_service.create_user(
        app,
        email=email,
        password=password,
        status_upon_creation=status_upon_creation,
        expires_at=None,
        role=role,
    )

    await auto_add_user_to_groups(app, user_id=user["id"])
    await auto_add_user_to_product_group(app, user_id=user["id"], product_name=product_name)

    return user

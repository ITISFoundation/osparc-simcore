import logging
from typing import NamedTuple

from aiohttp import web
from models_library.emails import LowerCaseEmailStr
from models_library.users import UserID
from pydantic import EmailStr, PositiveInt, parse_obj_as
from simcore_postgres_database.models.users import (
    FullNameTuple,
    UserNameConverter,
    UserStatus,
)

from ..db.plugin import get_database_engine
from ..email.utils import send_email_from_template
from ..products.api import get_current_product, get_product_template_path
from ._db import get_user_or_raise
from ._db import list_user_permissions as db_list_of_permissions
from ._db import update_user_status
from .schemas import Permission

_logger = logging.getLogger(__name__)


async def list_user_permissions(
    app: web.Application, user_id: UserID, product_name: str
) -> list[Permission]:
    permissions: list[Permission] = await db_list_of_permissions(
        app, user_id=user_id, product_name=product_name
    )
    return permissions


class UserCredintialsTuple(NamedTuple):
    email: LowerCaseEmailStr
    password_hash: str
    full_name: FullNameTuple


async def get_user_credentials(
    app: web.Application, *, user_id: UserID
) -> UserCredintialsTuple:
    row = await get_user_or_raise(
        get_database_engine(app),
        user_id=user_id,
        return_column_names=["name", "email", "password_hash"],
    )

    return UserCredintialsTuple(
        email=parse_obj_as(LowerCaseEmailStr, row.email),
        password_hash=row.password_hash,
        full_name=UserNameConverter.get_full_name(row.name),
    )


async def set_user_as_deleted(app: web.Application, user_id: UserID) -> None:
    await update_user_status(
        get_database_engine(app), user_id=user_id, new_status=UserStatus.DELETED
    )


async def send_close_account_email(
    request: web.Request,
    user_email: EmailStr,
    user_name: str,
    retention_days: PositiveInt = 30,
):
    template_name = "close_account.jinja2"
    email_template_path = await get_product_template_path(request, template_name)
    product = get_current_product(request)

    try:
        await send_email_from_template(
            request,
            from_=product.support_email,
            to=user_email,
            template=email_template_path,
            context={
                "host": request.host,
                "name": user_name.capitalize(),
                "support_email": product.support_email,
                "retention_days": retention_days,
            },
        )
    except Exception:  # pylint: disable=broad-except
        _logger.exception(
            "Failed while sending '%s' email to %s",
            template_name,
            f"{user_email=}",
        )

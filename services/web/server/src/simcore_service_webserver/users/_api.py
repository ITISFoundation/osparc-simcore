import logging
from typing import NamedTuple

import pycountry
from aiohttp import web
from models_library.emails import LowerCaseEmailStr
from models_library.payments import UserInvoiceAddress
from models_library.users import UserBillingDetails, UserID
from pydantic import TypeAdapter
from simcore_postgres_database.models.users import UserStatus

from ..db.plugin import get_database_engine
from . import _db, _schemas
from ._db import get_user_or_raise
from ._db import list_user_permissions as db_list_of_permissions
from ._db import update_user_status
from .exceptions import AlreadyPreRegisteredError
from .schemas import Permission

_logger = logging.getLogger(__name__)


async def list_user_permissions(
    app: web.Application, user_id: UserID, product_name: str
) -> list[Permission]:
    permissions: list[Permission] = await db_list_of_permissions(
        app, user_id=user_id, product_name=product_name
    )
    return permissions


class UserCredentialsTuple(NamedTuple):
    email: LowerCaseEmailStr
    password_hash: str
    display_name: str


async def get_user_credentials(
    app: web.Application, *, user_id: UserID
) -> UserCredentialsTuple:
    row = await get_user_or_raise(
        get_database_engine(app),
        user_id=user_id,
        return_column_names=[
            "name",
            "first_name",
            "email",
            "password_hash",
        ],
    )

    return UserCredentialsTuple(
        email=TypeAdapter(LowerCaseEmailStr).validate_python(row.email),
        password_hash=row.password_hash,
        display_name=row.first_name or row.name.capitalize(),
    )


async def set_user_as_deleted(app: web.Application, user_id: UserID) -> None:
    await update_user_status(
        get_database_engine(app), user_id=user_id, new_status=UserStatus.DELETED
    )


def _glob_to_sql_like(glob_pattern: str) -> str:
    # Escape SQL LIKE special characters in the glob pattern
    sql_like_pattern = glob_pattern.replace("%", r"\%").replace("_", r"\_")
    # Convert glob wildcards to SQL LIKE wildcards
    return sql_like_pattern.replace("*", "%").replace("?", "_")


async def search_users(
    app: web.Application, email_glob: str, *, include_products: bool = False
) -> list[_schemas.UserProfile]:
    # NOTE: this search is deploy-wide i.e. independent of the product!
    rows = await _db.search_users_and_get_profile(
        get_database_engine(app), email_like=_glob_to_sql_like(email_glob)
    )

    async def _list_products_or_none(user_id):
        if user_id is not None and include_products:
            products = await _db.get_user_products(
                get_database_engine(app), user_id=user_id
            )
            return [_.product_name for _ in products]
        return None

    return [
        _schemas.UserProfile(
            first_name=r.first_name or r.pre_first_name,
            last_name=r.last_name or r.pre_last_name,
            email=r.email or r.pre_email,
            institution=r.institution,
            phone=r.phone or r.pre_phone,
            address=r.address,
            city=r.city,
            state=r.state,
            postal_code=r.postal_code,
            country=r.country,
            extras=r.extras or {},
            invited_by=r.invited_by,
            products=await _list_products_or_none(r.user_id),
            # NOTE: old users will not have extra details
            registered=r.user_id is not None if r.pre_email else r.status is not None,
            status=r.status,
        )
        for r in rows
    ]


async def pre_register_user(
    app: web.Application, profile: _schemas.PreUserProfile, creator_user_id: UserID
) -> _schemas.UserProfile:

    found = await search_users(app, email_glob=profile.email, include_products=False)
    if found:
        raise AlreadyPreRegisteredError(num_found=len(found), email=profile.email)

    details = profile.model_dump(
        include={
            "first_name",
            "last_name",
            "phone",
            "institution",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "extras",
        },
        exclude_none=True,
    )

    for key in ("first_name", "last_name", "phone"):
        if key in details:
            details[f"pre_{key}"] = details.pop(key)

    await _db.new_user_details(
        get_database_engine(app),
        email=profile.email,
        created_by=creator_user_id,
        **details,
    )

    found = await search_users(app, email_glob=profile.email, include_products=False)

    assert len(found) == 1  # nosec
    return found[0]


async def get_user_invoice_address(
    app: web.Application, user_id: UserID
) -> UserInvoiceAddress:
    user_billing_details: UserBillingDetails = await _db.get_user_billing_details(
        get_database_engine(app), user_id=user_id
    )
    _user_billing_country = pycountry.countries.lookup(user_billing_details.country)
    _user_billing_country_alpha_2_format = _user_billing_country.alpha_2
    return UserInvoiceAddress(
        line1=user_billing_details.address,
        state=user_billing_details.state,
        postal_code=user_billing_details.postal_code,
        city=user_billing_details.city,
        country=_user_billing_country_alpha_2_format,
    )

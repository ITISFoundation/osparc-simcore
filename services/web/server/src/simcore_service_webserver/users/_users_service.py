import logging
from typing import Any

import pycountry
from aiohttp import web
from models_library.api_schemas_webserver.users import MyProfilePatch
from models_library.api_schemas_webserver.users_preferences import AggregatedPreferences
from models_library.basic_types import IDStr
from models_library.emails import LowerCaseEmailStr
from models_library.groups import GroupID
from models_library.payments import UserInvoiceAddress
from models_library.products import ProductName
from models_library.users import MyProfile, UserBillingDetails, UserID, UserPermission
from pydantic import TypeAdapter
from simcore_postgres_database.models.users import UserStatus
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesNotFoundError,
)

from ..db.plugin import get_asyncpg_engine
from ..security import security_service
from ..user_preferences import user_preferences_service
from . import _users_repository
from ._models import (
    FullNameDict,
    UserCredentialsTuple,
    UserDisplayAndIdNamesTuple,
    UserIdNamesTuple,
    UserModelAdapter,
)
from .exceptions import (
    MissingGroupExtraPropertiesForProductError,
)

_logger = logging.getLogger(__name__)

#
# GET USERS
#


async def get_public_user(app: web.Application, *, caller_id: UserID, user_id: UserID):
    return await _users_repository.get_public_user(
        get_asyncpg_engine(app),
        caller_id=caller_id,
        user_id=user_id,
    )


async def search_public_users(
    app: web.Application, *, caller_id: UserID, match_: str, limit: int
) -> list:
    return await _users_repository.search_public_user(
        get_asyncpg_engine(app),
        caller_id=caller_id,
        search_pattern=match_,
        limit=limit,
    )


async def get_user(app: web.Application, user_id: UserID) -> dict[str, Any]:
    """
    :raises UserNotFoundError: if missing but NOT if marked for deletion!
    """
    return await _users_repository.get_user_or_raise(
        engine=get_asyncpg_engine(app), user_id=user_id
    )


async def get_user_email_legacy(app: web.Application, user_id: UserID | None) -> str:
    """
    :raises UserNotFoundError: if missing but NOT if marked for deletion!
    """
    return await _users_repository.get_user_email_legacy(
        engine=get_asyncpg_engine(app), user_id=user_id
    )


async def get_user_primary_group_id(app: web.Application, user_id: UserID) -> GroupID:
    return await _users_repository.get_user_primary_group_id(
        engine=get_asyncpg_engine(app), user_id=user_id
    )


async def get_user_id_from_gid(app: web.Application, primary_gid: GroupID) -> UserID:
    return await _users_repository.get_user_id_from_pgid(app, primary_gid=primary_gid)


async def get_users_in_group(app: web.Application, *, gid: GroupID) -> set[UserID]:
    return await _users_repository.get_users_ids_in_group(
        get_asyncpg_engine(app), group_id=gid
    )


get_guest_user_ids_and_names = _users_repository.get_guest_user_ids_and_names


async def is_user_in_product(
    app: web.Application, *, user_id: UserID, product_name: ProductName
) -> bool:
    return await _users_repository.is_user_in_product_name(
        get_asyncpg_engine(app), user_id=user_id, product_name=product_name
    )


#
# GET USER PROPERTIES
#


async def get_user_fullname(app: web.Application, *, user_id: UserID) -> FullNameDict:
    """
    :raises UserNotFoundError:
    """
    return await _users_repository.get_user_fullname(app, user_id=user_id)


async def get_user_name_and_email(
    app: web.Application, *, user_id: UserID
) -> UserIdNamesTuple:
    """
    Raises:
        UserNotFoundError

    Returns:
        (user, email)
    """
    row = await _users_repository.get_user_or_raise(
        get_asyncpg_engine(app),
        user_id=user_id,
        return_column_names=["name", "email"],
    )
    return UserIdNamesTuple(name=row["name"], email=row["email"])


async def get_user_display_and_id_names(
    app: web.Application, *, user_id: UserID
) -> UserDisplayAndIdNamesTuple:
    """
    Raises:
        UserNotFoundError
    """
    row = await _users_repository.get_user_or_raise(
        get_asyncpg_engine(app),
        user_id=user_id,
        return_column_names=["name", "email", "first_name", "last_name"],
    )
    return UserDisplayAndIdNamesTuple(
        name=row["name"],
        email=row["email"],
        first_name=row["first_name"] or row["name"].capitalize(),
        last_name=IDStr(row["last_name"] or ""),
    )


get_user_role = _users_repository.get_user_role


async def get_user_credentials(
    app: web.Application, *, user_id: UserID
) -> UserCredentialsTuple:
    row = await _users_repository.get_user_or_raise(
        get_asyncpg_engine(app),
        user_id=user_id,
        return_column_names=[
            "name",
            "first_name",
            "email",
            "password_hash",
        ],
    )

    return UserCredentialsTuple(
        email=TypeAdapter(LowerCaseEmailStr).validate_python(row["email"]),
        password_hash=row["password_hash"],
        display_name=row["first_name"] or row["name"].capitalize(),
    )


async def list_user_permissions(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
) -> list[UserPermission]:
    permissions: list[UserPermission] = await _users_repository.list_user_permissions(
        app, user_id=user_id, product_name=product_name
    )
    return permissions


async def get_user_invoice_address(
    app: web.Application, *, user_id: UserID
) -> UserInvoiceAddress:
    user_billing_details: UserBillingDetails = (
        await _users_repository.get_user_billing_details(
            get_asyncpg_engine(app), user_id=user_id
        )
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


#
# DELETE USER
#


async def delete_user_without_projects(app: web.Application, user_id: UserID) -> None:
    """Deletes a user from the database if the user exists"""
    # WARNING: user cannot be deleted without deleting first all ist project
    # otherwise this function will raise asyncpg.exceptions.ForeignKeyViolationError
    # Consider "marking" users as deleted and havning a background job that
    # cleans it up
    is_deleted = await _users_repository.delete_user_by_id(
        engine=get_asyncpg_engine(app), user_id=user_id
    )
    if not is_deleted:
        _logger.warning(
            "User with id '%s' could not be deleted because it does not exist", user_id
        )
        return

    # This user might be cached in the auth. If so, any request
    # with this user-id will get thru producing unexpected side-effects
    await security_service.clean_auth_policy_cache(app)


async def set_user_as_deleted(app: web.Application, *, user_id: UserID) -> None:
    await _users_repository.update_user_status(
        get_asyncpg_engine(app), user_id=user_id, new_status=UserStatus.DELETED
    )


async def update_expired_users(app: web.Application) -> list[UserID]:
    return await _users_repository.do_update_expired_users(get_asyncpg_engine(app))


#
# MY USER PROFILE
#


async def get_my_profile(
    app: web.Application, *, user_id: UserID, product_name: ProductName
) -> tuple[MyProfile, AggregatedPreferences]:
    """Caller and target user is the same. Privacy settings do not apply here

    :raises UserNotFoundError:
    :raises MissingGroupExtraPropertiesForProductError: when product is not properly configured
    """
    my_profile = await _users_repository.get_my_profile(app, user_id=user_id)

    try:
        preferences = (
            await user_preferences_service.get_frontend_user_preferences_aggregation(
                app, user_id=user_id, product_name=product_name
            )
        )
    except GroupExtraPropertiesNotFoundError as err:
        raise MissingGroupExtraPropertiesForProductError(
            user_id=user_id,
            product_name=product_name,
        ) from err

    return my_profile, preferences


async def update_my_profile(
    app: web.Application,
    *,
    user_id: UserID,
    update: MyProfilePatch,
) -> None:

    await _users_repository.update_user_profile(
        app,
        user_id=user_id,
        updated_values=UserModelAdapter.from_schema(update).to_db(),
    )

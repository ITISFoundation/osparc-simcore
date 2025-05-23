import logging
from typing import Any

import pycountry
from aiohttp import web
from common_library.users_enums import AccountRequestStatus
from models_library.api_schemas_webserver.users import MyProfilePatch, UserAccountGet
from models_library.basic_types import IDStr
from models_library.emails import LowerCaseEmailStr
from models_library.groups import GroupID
from models_library.payments import UserInvoiceAddress
from models_library.products import ProductName
from models_library.users import UserBillingDetails, UserID, UserPermission
from pydantic import TypeAdapter
from simcore_postgres_database.models.users import UserStatus
from simcore_postgres_database.utils_groups_extra_properties import (
    GroupExtraPropertiesNotFoundError,
)

from ..db.plugin import get_asyncpg_engine
from ..security.api import clean_auth_policy_cache
from . import _preferences_service, _users_repository
from ._common.models import (
    FullNameDict,
    ToUserUpdateDB,
    UserCredentialsTuple,
    UserDisplayAndIdNamesTuple,
    UserIdNamesTuple,
)
from ._common.schemas import PreRegisteredUserGet
from .exceptions import (
    AlreadyPreRegisteredError,
    MissingGroupExtraPropertiesForProductError,
    PendingPreRegistrationNotFoundError,
)

_logger = logging.getLogger(__name__)

#
# PRE-REGISTRATION
#


async def pre_register_user(
    app: web.Application,
    *,
    profile: PreRegisteredUserGet,
    creator_user_id: UserID,
    product_name: ProductName,
) -> UserAccountGet:

    found = await search_users_accounts(
        app, email_glob=profile.email, product_name=product_name, include_products=False
    )
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

    await _users_repository.create_user_pre_registration(
        get_asyncpg_engine(app),
        email=profile.email,
        created_by=creator_user_id,
        product_name=product_name,
        **details,
    )

    found = await search_users_accounts(
        app, email_glob=profile.email, product_name=product_name, include_products=False
    )

    assert len(found) == 1  # nosec
    return found[0]


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
    await clean_auth_policy_cache(app)


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
):
    """Caller and target user is the same. Privacy settings do not apply here

    :raises UserNotFoundError:
    :raises MissingGroupExtraPropertiesForProductError: when product is not properly configured
    """
    my_profile = await _users_repository.get_my_profile(app, user_id=user_id)

    try:
        preferences = (
            await _preferences_service.get_frontend_user_preferences_aggregation(
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
        update=ToUserUpdateDB.from_api(update),
    )


#
# USER ACCOUNTS
#


async def list_user_accounts(
    app: web.Application,
    *,
    product_name: ProductName,
    filter_any_account_request_status: list[AccountRequestStatus] | None = None,
    pagination_limit: int = 50,
    pagination_offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """
    Get a paginated list of users for admin view with filtering options.

    Args:
        app: The web application instance
        filter_approved: If set, filters users by their approval status
        pagination_limit: Maximum number of users to return
        pagination_offset: Number of users to skip for pagination

    Returns:
        A tuple containing (list of user dictionaries, total count of users)
    """
    engine = get_asyncpg_engine(app)

    # Get user data with pagination
    users_data, total_count = (
        await _users_repository.list_merged_pre_and_registered_users(
            engine,
            product_name=product_name,
            filter_any_account_request_status=filter_any_account_request_status,
            pagination_limit=pagination_limit,
            pagination_offset=pagination_offset,
        )
    )

    # For each user, append additional information if needed
    result = []
    for user in users_data:
        # Add any additional processing needed for admin view
        user_dict = dict(user)

        # Add products information if needed
        user_id = user.get("user_id")
        if user_id:
            products = await _users_repository.get_user_products(
                engine, user_id=user_id
            )
            user_dict["products"] = [p.product_name for p in products]

        user_dict["registered"] = (
            user_id is not None
            if user.get("pre_email")
            else user.get("status") is not None
        )

        result.append(user_dict)

    return result, total_count


async def search_users_accounts(
    app: web.Application,
    *,
    email_glob: str,
    product_name: ProductName | None = None,
    include_products: bool = False,
) -> list[UserAccountGet]:
    """
    WARNING: this information is reserved for admin users. Note that the returned model include UserForAdminGet

    NOTE: Functions in the service layer typically validate the caller's access rights
    using parameters like product_name and user_id. However, this function skips
    such checks as it is designed for scenarios (e.g., background tasks) where
    no caller or context is available.
    """

    def _glob_to_sql_like(glob_pattern: str) -> str:
        # Escape SQL LIKE special characters in the glob pattern
        sql_like_pattern = glob_pattern.replace("%", r"\%").replace("_", r"\_")
        # Convert glob wildcards to SQL LIKE wildcards
        return sql_like_pattern.replace("*", "%").replace("?", "_")

    rows = await _users_repository.search_merged_pre_and_registered_users(
        get_asyncpg_engine(app),
        email_like=_glob_to_sql_like(email_glob),
        product_name=product_name,
    )

    async def _list_products_or_none(user_id):
        if user_id is not None and include_products:
            products = await _users_repository.get_user_products(
                get_asyncpg_engine(app), user_id=user_id
            )
            return [_.product_name for _ in products]
        return None

    return [
        UserAccountGet(
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
            pre_registration_id=r.id,
            account_request_status=r.account_request_status,
            account_request_reviewed_by=r.account_request_reviewed_by,
            account_request_reviewed_at=r.account_request_reviewed_at,
            products=await _list_products_or_none(r.user_id),
            # NOTE: old users will not have extra details
            registered=r.user_id is not None if r.pre_email else r.status is not None,
            status=r.status,
        )
        for r in rows
    ]


async def approve_user_account(
    app: web.Application,
    *,
    pre_registration_email: LowerCaseEmailStr,
    product_name: ProductName,
    reviewer_id: UserID,
) -> int:
    """Approve a user account based on their pre-registration email.

    Args:
        app: The web application instance
        pre_registration_email: Email of the pre-registered user to approve
        product_name: Product name for which the user is being approved
        reviewer_id: ID of the user approving the account

    Returns:
        int: The ID of the approved pre-registration record

    Raises:
        PendingPreRegistrationNotFoundError: If no pre-registration is found for the email/product
    """
    engine = get_asyncpg_engine(app)

    # First, find the pre-registration entry matching the email and product
    pre_registrations, _ = await _users_repository.list_user_pre_registrations(
        engine,
        filter_by_pre_email=pre_registration_email,
        filter_by_product_name=product_name,
        filter_by_account_request_status=AccountRequestStatus.PENDING,
    )

    if not pre_registrations:
        raise PendingPreRegistrationNotFoundError(
            email=pre_registration_email, product_name=product_name
        )

    # There should be only one registration matching these criteria
    pre_registration = pre_registrations[0]
    pre_registration_id: int = pre_registration["id"]

    # Update the pre-registration status to APPROVED using the reviewer's ID
    await _users_repository.review_user_pre_registration(
        engine,
        pre_registration_id=pre_registration_id,
        reviewed_by=reviewer_id,
        new_status=AccountRequestStatus.APPROVED,
    )

    return pre_registration_id


async def reject_user_account(
    app: web.Application,
    *,
    pre_registration_email: LowerCaseEmailStr,
    product_name: ProductName,
    reviewer_id: UserID,
) -> int:
    """Reject a user account based on their pre-registration email.

    Args:
        app: The web application instance
        pre_registration_email: Email of the pre-registered user to reject
        product_name: Product name for which the user is being rejected
        reviewer_id: ID of the user rejecting the account

    Returns:
        int: The ID of the rejected pre-registration record

    Raises:
        PendingPreRegistrationNotFoundError: If no pre-registration is found for the email/product
    """
    engine = get_asyncpg_engine(app)

    # First, find the pre-registration entry matching the email and product
    pre_registrations, _ = await _users_repository.list_user_pre_registrations(
        engine,
        filter_by_pre_email=pre_registration_email,
        filter_by_product_name=product_name,
        filter_by_account_request_status=AccountRequestStatus.PENDING,
    )

    if not pre_registrations:
        raise PendingPreRegistrationNotFoundError(
            email=pre_registration_email, product_name=product_name
        )

    # There should be only one registration matching these criteria
    pre_registration = pre_registrations[0]
    pre_registration_id: int = pre_registration["id"]

    # Update the pre-registration status to REJECTED using the reviewer's ID
    await _users_repository.review_user_pre_registration(
        engine,
        pre_registration_id=pre_registration_id,
        reviewed_by=reviewer_id,
        new_status=AccountRequestStatus.REJECTED,
    )

    return pre_registration_id

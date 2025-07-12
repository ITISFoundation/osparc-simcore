import logging
from typing import Any

from aiohttp import web
from common_library.users_enums import AccountRequestStatus
from models_library.api_schemas_webserver.users import UserAccountGet
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import HttpUrl
from settings_library.email import SMTPSettings
from simcore_service_webserver.products._service import get_product

from ..db.plugin import get_asyncpg_engine
from . import _accounts_repository, _users_repository
from .exceptions import (
    AlreadyPreRegisteredError,
    PendingPreRegistrationNotFoundError,
)
from .schemas import PreRegisteredUserGet

_logger = logging.getLogger(__name__)

#
# PRE-REGISTRATION
#


async def pre_register_user(
    app: web.Application,
    *,
    profile: PreRegisteredUserGet,
    creator_user_id: UserID | None,
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

    await _accounts_repository.create_user_pre_registration(
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
        filter_any_account_request_status: List of *any* account request statuses to filter by
        pagination_limit: Maximum number of users to return
        pagination_offset: Number of users to skip for pagination

    Returns:
        A tuple containing (list of user dictionaries, total count of users)
    """
    engine = get_asyncpg_engine(app)

    # Get user data with pagination
    users_data, total_count = (
        await _accounts_repository.list_merged_pre_and_registered_users(
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

    rows = await _accounts_repository.search_merged_pre_and_registered_users(
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
            pre_registration_created=r.created,
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
    invitation_extras: dict[str, Any] | None = None,
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
    pre_registrations, _ = await _accounts_repository.list_user_pre_registrations(
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
    await _accounts_repository.review_user_pre_registration(
        engine,
        pre_registration_id=pre_registration_id,
        reviewed_by=reviewer_id,
        new_status=AccountRequestStatus.APPROVED,
        invitation_extras=invitation_extras,
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
    pre_registrations, _ = await _accounts_repository.list_user_pre_registrations(
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
    await _accounts_repository.review_user_pre_registration(
        engine,
        pre_registration_id=pre_registration_id,
        reviewed_by=reviewer_id,
        new_status=AccountRequestStatus.REJECTED,
    )

    return pre_registration_id


def _create_product_and_user_data(
    app: web.Application,
    *,
    product_name: ProductName,
    user_email: LowerCaseEmailStr,
    first_name: str,
    last_name: str,
):
    """Create ProductData and UserData objects for email rendering."""
    from notifications_library._models import ProductData, ProductUIData, UserData

    # Get product data from the app
    product = get_product(app, product_name=product_name)

    # Extract vendor information
    vendor_display_inline = (
        str(product.vendor.get("name"))
        if product.vendor and product.vendor.get("name") is not None
        else "IT'IS Foundation"
    )

    # Extract UI information
    ui_data = ProductUIData(
        project_alias=(
            product.vendor.get("ui", {}).get("project_alias") or "study"
            if product.vendor
            else "study"
        ),
        logo_url=(
            product.vendor.get("ui", {}).get("logo_url") if product.vendor else None
        ),
        strong_color=(
            product.vendor.get("ui", {}).get("strong_color") if product.vendor else None
        ),
    )

    # Extract homepage URL
    homepage_url = product.vendor.get("url") if product.vendor else None

    product_data = ProductData(
        product_name=product_name,
        display_name=product.display_name,
        vendor_display_inline=vendor_display_inline,
        support_email=product.support_email,
        homepage_url=homepage_url,
        ui=ui_data,
    )

    # Create user data
    user_data = UserData(
        user_name=f"{first_name} {last_name}".strip(),
        email=user_email,
        first_name=first_name,
        last_name=last_name,
    )

    return product_data, user_data


async def send_approval_email_to_user(
    app: web.Application,
    *,
    product_name: ProductName,
    invitation_link: HttpUrl,
    user_email: LowerCaseEmailStr,
    first_name: str,
    last_name: str,
) -> None:
    from notifications_library._email import compose_email, create_email_session
    from notifications_library._email_render import (
        get_support_address,
        get_user_address,
        render_email_parts,
    )
    from notifications_library._render import (
        create_render_environment_from_notifications_library,
    )

    # Create product and user data
    product_data, user_data = _create_product_and_user_data(
        app,
        product_name=product_name,
        user_email=user_email,
        first_name=first_name,
        last_name=last_name,
    )

    # Prepare event data
    event_extra_data = {
        "host": str(invitation_link).split("?")[0],
        "link": str(invitation_link),
    }

    # Render email parts
    parts = render_email_parts(
        env=create_render_environment_from_notifications_library(),
        event_name="on_account_approved",
        user=user_data,
        product=product_data,
        **event_extra_data,
    )

    # Compose email
    msg = compose_email(
        from_=get_support_address(product_data),
        to=get_user_address(user_data),
        subject=parts.subject,
        content_text=parts.text_content,
        content_html=parts.html_content,
    )

    # Send email
    async with create_email_session(settings=SMTPSettings.create_from_envs()) as smtp:
        await smtp.send_message(msg)


async def send_rejection_email_to_user(
    app: web.Application,
    *,
    product_name: ProductName,
    user_email: LowerCaseEmailStr,
    first_name: str,
    last_name: str,
    host: str,
) -> None:
    from notifications_library._email import compose_email, create_email_session
    from notifications_library._email_render import (
        get_support_address,
        get_user_address,
        render_email_parts,
    )
    from notifications_library._render import (
        create_render_environment_from_notifications_library,
    )

    # Create product and user data
    product_data, user_data = _create_product_and_user_data(
        app,
        product_name=product_name,
        user_email=user_email,
        first_name=first_name,
        last_name=last_name,
    )

    # Prepare event data (based on test_email_events.py)
    event_extra_data = {
        "host": host,
    }

    # Render email parts
    parts = render_email_parts(
        env=create_render_environment_from_notifications_library(),
        event_name="on_account_rejected",
        user=user_data,
        product=product_data,
        **event_extra_data,
    )

    # Compose email
    msg = compose_email(
        from_=get_support_address(product_data),
        to=get_user_address(user_data),
        subject=parts.subject,
        content_text=parts.text_content,
        content_html=parts.html_content,
    )

    # Send email
    async with create_email_session(settings=SMTPSettings.create_from_envs()) as smtp:
        await smtp.send_message(msg)

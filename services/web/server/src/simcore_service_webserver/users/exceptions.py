from typing import Any

from ..errors import WebServerBaseError


class UsersBaseError(WebServerBaseError): ...


class UserNotFoundError(UsersBaseError):
    def __init__(
        self, *, user_id: int | None = None, email: str | None = None, **ctx: Any
    ):
        super().__init__(
            msg_template=(
                "User id {user_id} not found"
                if user_id
                else f"User with email {email} not found"
            ),
            **ctx,
        )
        self.user_id = user_id
        self.email = email


class UserNameDuplicateError(UsersBaseError):
    msg_template = "username is a unique ID and cannot create a new as '{user_name}' since it already exists "


class TokenNotFoundError(UsersBaseError):
    msg_template = "Token for service {service_id} not found"

    def __init__(self, *, service_id: str, **ctx: Any) -> None:
        super().__init__(**ctx)
        self.service_id = service_id


class UserDefaultWalletNotFoundError(UsersBaseError):
    msg_template = "Default wallet for user {uid} not found"

    def __init__(self, uid: int | None = None, **ctx: Any):
        super().__init__(**ctx)
        self.uid = uid


class FrontendUserPreferenceIsNotDefinedError(UsersBaseError):
    msg_template = "Provided {frontend_preference_name} not found"

    def __init__(self, frontend_preference_name: str, **ctx: Any):
        super().__init__(**ctx)
        self.frontend_preference_name = frontend_preference_name


class AlreadyPreRegisteredError(UsersBaseError):
    msg_template = (
        "Found {num_found} matches for '{email}'. Cannot pre-register existing user"
    )


class BillingDetailsNotFoundError(UsersBaseError):
    # NOTE: this is for internal log and should not be transmitted to the final user
    msg_template = "Billing details are missing for user_id={user_id}. TIP: Check whether this user is pre-registered"


class MissingGroupExtraPropertiesForProductError(UsersBaseError):
    msg_template = "Missing group_extra_property for product_name={product_name}"
    tip = "Add a new row in group_extra_property table and assign it to this product"


class PendingPreRegistrationNotFoundError(UsersBaseError):
    msg_template = (
        "No pending pre-registration found for email {email} in product {product_name}"
    )

    def __init__(self, *, email: str, product_name: str, **ctx: Any):
        super().__init__(**ctx)
        self.email = email
        self.product_name = product_name

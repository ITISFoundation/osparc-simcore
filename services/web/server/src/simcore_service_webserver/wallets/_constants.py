from typing import Final

from common_library.user_messages import user_message

MSG_PRICE_NOT_DEFINED_ERROR: Final[str] = user_message(
    "Payments are not currently available for this product as pricing has not been configured.",
    _version=1,
)

MSG_BILLING_DETAILS_NOT_DEFINED_ERROR: Final[str] = user_message(
    "Unable to process payment because required billing information (such as country for tax purposes) is missing from your account. "
    "Please contact support to complete your billing setup.",
    _version=1,
)

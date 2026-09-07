from typing import Final

from common_library.user_messages import user_message

MSG_PRICE_NOT_DEFINED_ERROR: Final[str] = user_message(
    "Payments are not currently available for this product as pricing has not been configured.",
    _version=1,
)

MSG_BILLING_DETAILS_NOT_DEFINED_ERROR: Final[str] = user_message(
    "Unable to process payment because required billing information (such as country for tax purposes) is missing "
    "from your account. "
    "Please contact support to complete your billing setup.",
    _version=1,
)

MSG_BELOW_MINIMUM_PAYMENT_ERROR: Final[str] = user_message(
    "The payment amount is below the minimum required. Please increase the amount and try again.",
    _version=1,
)

MSG_PAYMENT_CONFLICT_ERROR: Final[str] = user_message(
    "This payment operation can't be completed at this time due to its current status. Please try again later.",
    _version=1,
)

MSG_WALLET_ACCESS_FORBIDDEN_ERROR: Final[str] = user_message(
    "You don't have permission to access this wallet. Contact support if you think this is a mistake.",
    _version=1,
)

MSG_WALLET_NOT_ENOUGH_CREDITS_ERROR: Final[str] = user_message(
    "This wallet doesn't have enough credits to complete this operation. Please add credits and try again.",
    _version=1,
)

MSG_WALLET_OR_PAYMENT_NOT_FOUND_ERROR: Final[str] = user_message(
    "The wallet or payment you're looking for isn't available. Please check the reference and try again, "
    "or contact support.",
    _version=1,
)

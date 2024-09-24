from typing import Final

MSG_PRICE_NOT_DEFINED_ERROR: Final[
    str
] = "No payments are accepted until this product has a price"

MSG_BILLING_DETAILS_NOT_DEFINED_ERROR: Final[str] = (
    "Payments cannot be processed: Required billing details (e.g. country for tax) are missing from your account."
    "Please contact support to resolve this configuration issue."
)

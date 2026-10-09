# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pydantic import TypeAdapter
from simcore_postgres_database.utils_products_prices import StripePriceID, StripeTaxRateID


def test_stripe_id_aliases_validate_as_plain_str() -> None:
    # PEP 695 `type` aliases are not runtime-callable (unlike `TypeAlias`
    # assignments): go through a TypeAdapter to exercise them at runtime.
    assert TypeAdapter(StripePriceID).validate_python("price_123") == "price_123"
    assert TypeAdapter(StripeTaxRateID).validate_python("txr_456") == "txr_456"

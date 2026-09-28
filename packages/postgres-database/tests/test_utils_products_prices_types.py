# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from simcore_postgres_database.utils_products_prices import StripePriceID, StripeTaxRateID


def test_stripe_id_aliases_are_callable_as_constructors():
    # NOTE: these aliases are called as constructors (e.g. in
    # pytest_simcore.faker_products_data fixtures), so they must keep the
    # `TypeAlias` form: a PEP 695 `type` alias is not callable at runtime
    # (raises TypeError: 'typing.TypeAliasType' object is not callable).
    assert StripePriceID("price_123") == "price_123"
    assert StripeTaxRateID("txr_456") == "txr_456"

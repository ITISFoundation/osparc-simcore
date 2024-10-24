import logging

import pytest
from models_library.rest_filters import Filters, FiltersQueryParameters
from pydantic import Extra, ValidationError


# 1. create filter model
class CustomFilter(Filters):
    is_trashed: bool | None = None
    is_hidden: bool | None = None


class CustomFilterStrict(CustomFilter):
    class Config(CustomFilter.Config):
        extra = Extra.forbid


def test_custom_filter_query_parameters():

    # 2. use generic as query parameters
    logging.info(
        "json schema is for the query \n %s",
        FiltersQueryParameters[CustomFilter].schema_json(indent=1),
    )

    # lets filter only is_trashed and unset is_hidden
    custom_filter = CustomFilter(is_trashed=True)
    assert custom_filter.json() == '{"is_trashed": true, "is_hidden": null}'

    # default to None (optional)
    query_param = FiltersQueryParameters[CustomFilter]()
    assert query_param.filters is None


@pytest.mark.parametrize(
    "url_query_value,expects",
    [
        ('{"is_trashed": true, "is_hidden": null}', CustomFilter(is_trashed=True)),
        ('{"is_trashed": true}', CustomFilter(is_trashed=True)),
        (None, None),
    ],
)
def test_valid_filter_queries(
    url_query_value: str | None, expects: CustomFilter | None
):
    query_param = FiltersQueryParameters[CustomFilter](filters=url_query_value)
    assert query_param.filters == expects


def test_invalid_filter_query_is_ignored():
    # NOTE: invalid filter get ignored!
    url_query_value = '{"undefined_filter": true, "is_hidden": true}'

    query_param = FiltersQueryParameters[CustomFilter](filters=url_query_value)
    assert query_param.filters == CustomFilter(is_hidden=True)


@pytest.mark.xfail
def test_invalid_filter_query_fails():
    # NOTE: this should fail according to pydantic manual but it does not
    url_query_value = '{"undefined_filter": true, "is_hidden": true}'

    with pytest.raises(ValidationError):
        FiltersQueryParameters[CustomFilterStrict](filters=url_query_value)

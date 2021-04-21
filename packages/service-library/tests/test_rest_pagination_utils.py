from copy import deepcopy

import pytest
from servicelib.rest_pagination_utils import (
    PageLinks,
    PageMetaInfoLimitOffset,
    PageResponseLimitOffset,
)
from yarl import URL


def test_page_response_limit_offset_model():
    examples = PageResponseLimitOffset.Config.schema_extra["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = PageResponseLimitOffset(**example)
        assert model_instance


def test_empty_data_is_converted_to_list():
    example = deepcopy(PageResponseLimitOffset.Config.schema_extra["examples"][0])
    example["data"] = None

    model_instance = PageResponseLimitOffset(**example)
    assert model_instance
    assert model_instance.data == []


def test_more_data_than_limit_raises():
    example = deepcopy(PageResponseLimitOffset.Config.schema_extra["examples"][0])
    example["_meta"]["limit"] = len(example["data"]) - 1

    with pytest.raises(ValueError):
        PageResponseLimitOffset(**example)


def test_paginating_data():
    # create random data
    total_number_of_data = 29
    limit = 9
    offset = 0
    partial_data = [range(7)]
    request_url = URL("http://some/random/url.com?some=1&random=4&query=true")

    # first "call"
    model_instance: PageResponseLimitOffset = PageResponseLimitOffset.paginate_data(
        partial_data, request_url, total_number_of_data, limit, offset
    )

    assert model_instance
    assert model_instance.meta == PageMetaInfoLimitOffset(
        total=total_number_of_data, count=len(partial_data), limit=limit, offset=offset
    )
    assert model_instance.links == PageLinks(
        self=f"http://some/random/url.com?some=1&random=4&query=true&offset={offset}&limit={limit}",
        first=f"http://some/random/url.com?some=1&random=4&query=true&offset=0&limit={limit}",
        prev=None,
        next=f"http://some/random/url.com?some=1&random=4&query=true&offset=1&limit={limit}",
        last=f"http://some/random/url.com?some=1&random=4&query=true&offset=3&limit={limit}",
    )

    # next "call"s
    for i in [1, 2]:
        model_instance: PageResponseLimitOffset = PageResponseLimitOffset.paginate_data(
            partial_data,
            URL(model_instance.links.next),
            total_number_of_data,
            limit,
            offset + i,
        )

        assert model_instance
        assert model_instance.meta == PageMetaInfoLimitOffset(
            total=total_number_of_data,
            count=len(partial_data),
            limit=limit,
            offset=offset + i,
        )
        assert model_instance.links == PageLinks(
            self=f"http://some/random/url.com?some=1&random=4&query=true&offset={offset+i}&limit={limit}",
            first=f"http://some/random/url.com?some=1&random=4&query=true&offset=0&limit={limit}",
            prev=f"http://some/random/url.com?some=1&random=4&query=true&offset={i-1}&limit={limit}",
            next=f"http://some/random/url.com?some=1&random=4&query=true&offset={i+1}&limit={limit}",
            last=f"http://some/random/url.com?some=1&random=4&query=true&offset=3&limit={limit}",
        )

    # last "call"
    model_instance: PageResponseLimitOffset = PageResponseLimitOffset.paginate_data(
        partial_data,
        URL(model_instance.links.next),
        total_number_of_data,
        limit,
        offset + 3,
    )

    assert model_instance
    assert model_instance.meta == PageMetaInfoLimitOffset(
        total=total_number_of_data,
        count=len(partial_data),
        limit=limit,
        offset=offset + 3,
    )
    assert model_instance.links == PageLinks(
        self=f"http://some/random/url.com?some=1&random=4&query=true&offset={offset+3}&limit={limit}",
        first=f"http://some/random/url.com?some=1&random=4&query=true&offset=0&limit={limit}",
        prev=f"http://some/random/url.com?some=1&random=4&query=true&offset=2&limit={limit}",
        next=None,
        last=f"http://some/random/url.com?some=1&random=4&query=true&offset=3&limit={limit}",
    )

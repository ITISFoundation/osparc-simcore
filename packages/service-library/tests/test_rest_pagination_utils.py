from copy import deepcopy

import pytest
from pydantic.main import BaseModel
from servicelib.rest_pagination_utils import (
    PageLinks,
    PageMetaInfoLimitOffset,
    PageResponseLimitOffset,
)
from yarl import URL


@pytest.mark.parametrize(
    "cls_model", [PageResponseLimitOffset, PageMetaInfoLimitOffset]
)
def test_page_response_limit_offset_models(cls_model: BaseModel):
    examples = cls_model.Config.schema_extra["examples"]

    for index, example in enumerate(examples):
        print(f"{index:-^10}:\n", example)

        model_instance = cls_model(**example)
        assert model_instance


def test_invalid_offset():
    with pytest.raises(ValueError):
        PageMetaInfoLimitOffset(limit=6, total=5, offset=5, count=2)


@pytest.mark.parametrize(
    "count, offset",
    [
        pytest.param(7, 0, id="count bigger than limit"),
        pytest.param(6, 0, id="count bigger than total"),
        pytest.param(5, 1, id="count + offset bigger than total"),
    ],
)
def test_invalid_count(count: int, offset: int):
    with pytest.raises(ValueError):
        PageMetaInfoLimitOffset(limit=6, total=5, offset=offset, count=count)


def test_data_size_does_not_fit_count():
    example = deepcopy(PageResponseLimitOffset.Config.schema_extra["examples"][0])
    example["_meta"]["count"] = len(example["data"]) - 1
    with pytest.raises(ValueError):
        PageResponseLimitOffset(**example)


def test_empty_data_is_converted_to_list():
    example = deepcopy(PageResponseLimitOffset.Config.schema_extra["examples"][0])
    example["data"] = None
    example["_meta"]["count"] = 0
    model_instance = PageResponseLimitOffset(**example)
    assert model_instance
    assert model_instance.data == []


@pytest.mark.parametrize(
    "base_url",
    [
        "http://site.com",
        "http://site.com/",
        "http://some/random/url.com",
        "http://some/random/url.com/",
        "http://s.s.s.s.subsite.site.com",
        "http://s.s.s.s.subsite.site.com/",
        "http://10.0.0.1.nip.io/",
        "http://10.0.0.1.nip.io:8091/",
        "http://10.0.0.1.nip.io",
        "http://10.0.0.1.nip.io:8091",
    ],
)
def test_paginating_data(base_url):
    # create random data
    total_number_of_data = 29
    limit = 9
    offset = 0
    partial_data = [range(9)]
    request_url = URL(f"{base_url}?some=1&random=4&query=true")

    # first "call"
    model_instance: PageResponseLimitOffset = PageResponseLimitOffset.paginate_data(
        partial_data, request_url, total_number_of_data, limit, offset
    )

    assert model_instance
    assert model_instance.meta == PageMetaInfoLimitOffset(
        total=total_number_of_data, count=len(partial_data), limit=limit, offset=offset
    )
    assert model_instance.links == PageLinks(
        self=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset={offset}&limit={limit}"
            )
        ),
        first=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset=0&limit={limit}"
            )
        ),
        prev=None,
        next=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset=9&limit={limit}"
            )
        ),
        last=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset=27&limit={limit}"
            )
        ),
    )

    # next "call"s
    for i in [1, 2]:
        model_instance: PageResponseLimitOffset = PageResponseLimitOffset.paginate_data(
            partial_data,
            URL(model_instance.links.next),
            total_number_of_data,
            limit,
            offset + i * limit,
        )

        assert model_instance
        assert model_instance.meta == PageMetaInfoLimitOffset(
            total=total_number_of_data,
            count=len(partial_data),
            limit=limit,
            offset=offset + i * limit,
        )
        assert model_instance.links == PageLinks(
            self=str(
                URL(base_url).with_query(
                    f"some=1&random=4&query=true&offset={offset + i*limit}&limit={limit}"
                )
            ),
            first=str(
                URL(base_url).with_query(
                    f"some=1&random=4&query=true&offset=0&limit={limit}"
                )
            ),
            prev=str(
                URL(base_url).with_query(
                    f"some=1&random=4&query=true&offset={offset + i*limit-limit}&limit={limit}"
                )
            ),
            next=str(
                URL(base_url).with_query(
                    f"some=1&random=4&query=true&offset={offset + i*limit+limit}&limit={limit}"
                )
            ),
            last=str(
                URL(base_url).with_query(
                    f"some=1&random=4&query=true&offset=27&limit={limit}"
                )
            ),
        )

    # last "call"
    model_instance: PageResponseLimitOffset = PageResponseLimitOffset.paginate_data(
        partial_data,
        URL(model_instance.links.next),
        total_number_of_data,
        limit,
        offset + 3 * limit,
    )

    assert model_instance
    assert model_instance.meta == PageMetaInfoLimitOffset(
        total=total_number_of_data,
        count=len(partial_data),
        limit=limit,
        offset=offset + 3 * limit,
    )
    assert model_instance.links == PageLinks(
        self=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset={offset+3*limit}&limit={limit}"
            )
        ),
        first=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset=0&limit={limit}"
            )
        ),
        prev=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset=18&limit={limit}"
            )
        ),
        next=None,
        last=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset=27&limit={limit}"
            )
        ),
    )

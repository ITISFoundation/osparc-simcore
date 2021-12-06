import pytest
from models_library.rest_pagination import Page, PageLinks, PageMetaInfoLimitOffset
from servicelib.rest_pagination_utils import PageDict, paginate_data
from yarl import URL


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
    partial_data = list(range(9))
    request_url = URL(f"{base_url}?some=1&random=4&query=true")

    # first "call"
    data_obj: PageDict = paginate_data(
        partial_data, request_url, total_number_of_data, limit, offset
    )
    assert data_obj

    model_instance = Page[int].parse_obj(data_obj)
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
    for i in (1, 2):
        assert model_instance.links.next is not None

        data_obj: PageDict = paginate_data(
            partial_data,
            URL(model_instance.links.next),
            total_number_of_data,
            limit,
            offset + i * limit,
        )

        model_instance = Page[int].parse_obj(data_obj)
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
    assert model_instance.links.next is not None
    data_obj: PageDict = paginate_data(
        partial_data,
        URL(model_instance.links.next),
        total_number_of_data,
        limit,
        offset + 3 * limit,
    )
    assert data_obj

    model_instance = Page[int].parse_obj(data_obj)
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

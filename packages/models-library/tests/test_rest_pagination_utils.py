import pytest
from models_library.rest_pagination import Page, PageLinks, PageMetaInfoLimitOffset
from models_library.rest_pagination_utils import PageDict, paginate_data
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
    total_number_of_items = 29
    limit = 9
    data_chunk = list(range(limit))
    request_url = URL(f"{base_url}?some=1&random=4&query=true")

    number_of_chunks = total_number_of_items // limit + 1
    last_chunk_size = total_number_of_items % limit
    last_chunk_offset = (number_of_chunks - 1) * len(data_chunk)

    # first "call"
    offset = 0
    data_obj: PageDict = paginate_data(
        data_chunk,
        total=total_number_of_items,
        limit=limit,
        offset=offset,
        request_url=request_url,
    )
    assert data_obj

    model_instance = Page[int].model_validate(data_obj)
    assert model_instance
    assert model_instance.meta == PageMetaInfoLimitOffset(
        total=total_number_of_items, count=len(data_chunk), limit=limit, offset=offset
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
                f"some=1&random=4&query=true&offset={offset+limit}&limit={limit}"
            )
        ),
        last=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset={last_chunk_offset}&limit={limit}"
            )
        ),
    )

    # next "call"s
    for _ in range(1, number_of_chunks - 1):
        offset += len(data_chunk)
        assert model_instance.links.next is not None

        data_obj: PageDict = paginate_data(  # type: ignore[no-redef]
            data_chunk,
            request_url=URL(model_instance.links.next),
            total=total_number_of_items,
            limit=limit,
            offset=offset,
        )

        model_instance = Page[int].model_validate(data_obj)
        assert model_instance
        assert model_instance.meta == PageMetaInfoLimitOffset(
            total=total_number_of_items,
            count=len(data_chunk),
            limit=limit,
            offset=offset,
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
            prev=str(
                URL(base_url).with_query(
                    f"some=1&random=4&query=true&offset={offset-limit}&limit={limit}"
                )
            ),
            next=str(
                URL(base_url).with_query(
                    f"some=1&random=4&query=true&offset={offset+limit}&limit={limit}"
                )
            ),
            last=str(
                URL(base_url).with_query(
                    f"some=1&random=4&query=true&offset={last_chunk_offset}&limit={limit}"
                )
            ),
        )

    # last "call"
    #
    offset += len(data_chunk)
    data_chunk = data_chunk[:last_chunk_size]

    assert offset == last_chunk_offset

    assert model_instance.links.next is not None
    data_obj: PageDict = paginate_data(  # type: ignore[no-redef]
        data_chunk,
        request_url=URL(model_instance.links.next),
        total=total_number_of_items,
        limit=limit,
        offset=offset,
    )
    assert data_obj

    model_instance = Page[int].model_validate(data_obj)
    assert model_instance

    assert model_instance.meta == PageMetaInfoLimitOffset(
        total=total_number_of_items,
        count=len(data_chunk),
        limit=limit,
        offset=offset,
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
        prev=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset={last_chunk_offset - limit}&limit={limit}"
            )
        ),
        next=None,
        last=str(
            URL(base_url).with_query(
                f"some=1&random=4&query=true&offset={last_chunk_offset}&limit={limit}"
            )
        ),
    )

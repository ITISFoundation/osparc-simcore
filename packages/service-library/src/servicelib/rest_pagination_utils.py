from math import ceil
from typing import Any, Dict, List, Protocol, TypedDict, Union

from models_library.rest_pagination import PageLinks, PageMetaInfoLimitOffset
from yarl import URL


class _StarletteURL(Protocol):
    # Convenience protocol to avoid including starlette in requirements
    #
    # SEE starlette.data_structures.URL
    #  in https://github.com/encode/starlette/blob/master/starlette/datastructures.py#L130
    #

    def replace_query_params(self, **kwargs: Any) -> "_StarletteURL":
        ...


URLType = Union[URL, _StarletteURL]


def _replace_query(url: URLType, query: Dict[str, Any]):
    """In this repo we use two type of URL-like data structures:
        - from yarl (aiohttp-style) and
        - from starlette (fastapi-style).

    This helper function ensures query replacement works with both
    """
    if isinstance(url, URL):
        # yarl URL
        new_url = url.update_query(query)
    else:
        new_url = url.replace_query_params(**query)
    return f"{new_url}"


class PageDict(TypedDict):
    _meta: Any
    _links: Any
    data: List[Any]


def paginate_data(
    data: List[Any],
    request_url: URLType,
    total: int,
    limit: int,
    offset: int,
) -> PageDict:
    """Helper to build page-like objects to feed to Page[X] pydantic model class"""
    last_page = ceil(total / limit) - 1

    return PageDict(
        _meta=PageMetaInfoLimitOffset(
            total=total, count=len(data), limit=limit, offset=offset
        ),
        _links=PageLinks(
            self=_replace_query(request_url, {"offset": offset, "limit": limit}),
            first=_replace_query(request_url, {"offset": 0, "limit": limit}),
            prev=_replace_query(
                request_url, {"offset": max(offset - limit, 0), "limit": limit}
            )
            if offset > 0
            else None,
            next=_replace_query(
                request_url,
                {"offset": min(offset + limit, last_page * limit), "limit": limit},
            )
            if offset < (last_page * limit)
            else None,
            last=_replace_query(
                request_url, {"offset": last_page * limit, "limit": limit}
            ),
        ),
        data=data,
    )

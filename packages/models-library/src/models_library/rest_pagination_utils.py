from math import ceil
from typing import Any, Protocol, runtime_checkable

from pydantic import AnyHttpUrl, TypeAdapter
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

from .rest_pagination import PageLinks, PageMetaInfoLimitOffset

# NOTE: In this repo we use two type of URL-like data structures:
#  - from yarl (aiohttp-style) and
#  - from starlette (fastapi-style)
#
# Here define protocol to avoid including starlette  or yarl in this librarie's requirements
# and a helper function below that can handle both protocols at runtime
#


@runtime_checkable
class _YarlURL(Protocol):
    def update_query(self, query) -> "_YarlURL":
        ...


class _StarletteURL(Protocol):
    # SEE starlette.data_structures.URL
    #  in https://github.com/encode/starlette/blob/master/starlette/datastructures.py#L130

    def replace_query_params(self, **kwargs: Any) -> "_StarletteURL":
        ...


_URLType = _YarlURL | _StarletteURL


def _replace_query(url: _URLType, query: dict[str, Any]) -> str:
    """This helper function ensures query replacement works with both"""
    new_url: _URLType | _StarletteURL
    if isinstance(url, _YarlURL):
        new_url = url.update_query(query)
    else:
        new_url = url.replace_query_params(**query)

    new_url_str = f"{new_url}"
    return f"{TypeAdapter(AnyHttpUrl).validate_python(new_url_str)}"


class PageDict(TypedDict):
    _meta: Any
    _links: Any
    data: list[Any]


def paginate_data(
    chunk: list[Any],
    *,
    request_url: _URLType,
    total: int,
    limit: int,
    offset: int,
) -> PageDict:
    """Builds page-like objects to feed to Page[ItemT] pydantic model class

    Usage:

        obj: PageDict = paginate_data( ... )
        model = Page[MyModelItem].model_validate(obj)

    raises ValidationError
    """
    last_page = ceil(total / limit) - 1

    data = [
        item.model_dump() if hasattr(item, "model_dump") else item for item in chunk
    ]

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

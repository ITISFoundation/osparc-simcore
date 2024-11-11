from typing import Final

PAGE_EXAMPLES: Final[list[dict]] = [
    # first page Page[str]
    {
        "_meta": {"total": 7, "count": 4, "limit": 4, "offset": 0},
        "_links": {
            "self": "https://osparc.io/v2/listing?offset=0&limit=4",
            "first": "https://osparc.io/v2/listing?offset=0&limit=4",
            "prev": None,
            "next": "https://osparc.io/v2/listing?offset=1&limit=4",
            "last": "https://osparc.io/v2/listing?offset=1&limit=4",
        },
        "data": ["data 1", "data 2", "data 3", "data 4"],
    },
    # second and last page
    {
        "_meta": {"total": 7, "count": 3, "limit": 4, "offset": 1},
        "_links": {
            "self": "https://osparc.io/v2/listing?offset=1&limit=4",
            "first": "https://osparc.io/v2/listing?offset=0&limit=4",
            "prev": "https://osparc.io/v2/listing?offset=0&limit=4",
            "next": None,
            "last": "https://osparc.io/v2/listing?offset=1&limit=4",
        },
        "data": ["data 5", "data 6", "data 7"],
    },
]

RPC_PAGE_EXAMPLES: Final[list[dict]] = [
    # first page Page[str]
    {
        "_meta": {"total": 7, "count": 4, "limit": 4, "offset": 0},
        "_links": {
            "self": {"offset": 0, "limit": 4},
            "first": {"offset": 0, "limit": 4},
            "prev": None,
            "next": {"offset": 1, "limit": 4},
            "last": {"offset": 1, "limit": 4},
        },
        "data": ["data 1", "data 2", "data 3", "data 4"],
    },
    # second and last page
    {
        "_meta": {"total": 7, "count": 3, "limit": 4, "offset": 1},
        "_links": {
            "self": {"offset": 1, "limit": 4},
            "first": {"offset": 0, "limit": 4},
            "prev": {"offset": 0, "limit": 4},
            "next": None,
            "last": {"offset": 1, "limit": 4},
        },
        "data": ["data 5", "data 6", "data 7"],
    },
]

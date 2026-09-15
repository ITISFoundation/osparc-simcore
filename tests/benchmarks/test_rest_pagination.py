"""Benchmarks for the paginated REST envelopes and the generic dict/sequence helpers

Every list-like endpoint of the platform wraps its payload in a
`Page[ItemT]` envelope, so validating and dumping it is on the hot path of the
API responses.
"""

from typing import Any

import pytest
from common_library.dict_tools import copy_from_dict, remap_keys, update_dict
from common_library.pagination_tools import iter_pagination_params
from common_library.sequence_tools import interleave_by_key
from models_library.rest_pagination import Page

_PAGE_LIMIT = 50
_TOTAL = 1000


@pytest.fixture(scope="module")
def page_payload() -> dict[str, Any]:
    return {
        "_meta": {"total": _TOTAL, "count": _PAGE_LIMIT, "limit": _PAGE_LIMIT, "offset": 0},
        "_links": {
            "self": f"http://osparc.io/v0/projects?offset=0&limit={_PAGE_LIMIT}",
            "first": f"http://osparc.io/v0/projects?offset=0&limit={_PAGE_LIMIT}",
            "prev": None,
            "next": f"http://osparc.io/v0/projects?offset={_PAGE_LIMIT}&limit={_PAGE_LIMIT}",
            "last": f"http://osparc.io/v0/projects?offset={_TOTAL - _PAGE_LIMIT}&limit={_PAGE_LIMIT}",
        },
        "data": [
            {
                "uuid": f"2b6b1e2a-0000-4000-8000-{i:012d}",
                "name": f"study-{i}",
                "description": "a study",
                "owner": f"user-{i % 7}@osparc.io",
            }
            for i in range(_PAGE_LIMIT)
        ],
    }


@pytest.fixture(scope="module")
def emails() -> list[str]:
    domains = ["gmail.com", "yahoo.com", "osparc.io", "uni.edu"]
    return [f"user-{i}@{domains[i % len(domains)]}" for i in range(500)]


def test_page_model_validate(benchmark, page_payload: dict[str, Any]):
    page = benchmark(Page[dict[str, Any]].model_validate, page_payload)
    assert page.meta.count == _PAGE_LIMIT


def test_page_model_dump_json(benchmark, page_payload: dict[str, Any]):
    page = Page[dict[str, Any]].model_validate(page_payload)
    result = benchmark(lambda: page.model_dump_json(by_alias=True))
    assert result


def test_iter_pagination_params(benchmark):
    def _iterate() -> int:
        count = 0
        for page_params in iter_pagination_params(limit=_PAGE_LIMIT, offset=0, total_number_of_items=_TOTAL):
            count += page_params.limit
        return count

    assert benchmark(_iterate) == _TOTAL


def test_interleave_by_key(benchmark, emails: list[str]):
    result = benchmark(lambda: interleave_by_key(emails, key=lambda e: e.split("@")[1]))
    assert len(result) == len(emails)


def test_dict_tools_remap_and_copy(benchmark, page_payload: dict[str, Any]):
    items = page_payload["data"]
    rename = {"uuid": "id", "name": "label", "owner": "prj_owner"}

    def _transform() -> int:
        total = 0
        for item in items:
            renamed = remap_keys(item, rename)
            subset = copy_from_dict(renamed, include={"id", "label"})
            total += len(update_dict(subset, label=lambda v: v.upper()))
        return total

    assert benchmark(_transform) == 2 * _PAGE_LIMIT

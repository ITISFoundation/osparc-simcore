"""Benchmarks for `common_library.json_serialization`

This module is used everywhere in the platform to serialize/deserialize payloads
(REST responses, RabbitMQ messages, database json columns, ...) so it sits on
many hot paths.
"""

import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from common_library.json_serialization import (
    json_dumps,
    json_loads,
    pydantic_encoder,
    representation_encoder,
)
from pydantic import BaseModel, SecretStr

_NUM_ITEMS = 200


class _Item(BaseModel):
    id: UUID
    name: str
    price: Decimal
    tags: list[str]
    created_at: datetime.datetime
    path: Path
    secret: SecretStr


@pytest.fixture(scope="module")
def plain_payload() -> dict[str, Any]:
    return {
        "items": [
            {
                "id": f"2b6b1e2a-0000-4000-8000-{i:012d}",
                "name": f"item-{i}",
                "price": i * 1.5,
                "tags": [f"tag-{i}", f"tag-{i + 1}"],
                "nested": {"a": i, "b": [i, i + 1, i + 2], "c": {"d": None, "e": True}},
            }
            for i in range(_NUM_ITEMS)
        ],
        "total": _NUM_ITEMS,
    }


@pytest.fixture(scope="module")
def plain_payload_as_text(plain_payload: dict[str, Any]) -> str:
    return json_dumps(plain_payload)


@pytest.fixture(scope="module")
def rich_payload() -> dict[str, Any]:
    """Payload with types that require the custom `pydantic_encoder`"""
    return {
        "items": [
            _Item(
                id=UUID(f"2b6b1e2a-0000-4000-8000-{i:012d}"),
                name=f"item-{i}",
                price=Decimal(f"{i}.99"),
                tags=[f"tag-{i}"],
                created_at=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC) + datetime.timedelta(seconds=i),
                path=Path(f"/data/item-{i}.txt"),
                secret=SecretStr(f"secret-{i}"),
            )
            for i in range(_NUM_ITEMS)
        ],
        "generated_at": datetime.datetime(2024, 6, 1, tzinfo=datetime.UTC),
        "duration": datetime.timedelta(seconds=42),
    }


@pytest.fixture(scope="module")
def payload_with_tuple_keys() -> dict[str, Any]:
    return {"matrix": {(i, i + 1): [i, i * 2] for i in range(_NUM_ITEMS)}}


def test_json_dumps_plain(benchmark, plain_payload: dict[str, Any]):
    result = benchmark(json_dumps, plain_payload)
    assert result


def test_json_dumps_plain_sorted_and_indented(benchmark, plain_payload: dict[str, Any]):
    result = benchmark(lambda: json_dumps(plain_payload, sort_keys=True, indent=2))
    assert result


def test_json_dumps_with_pydantic_encoder(benchmark, rich_payload: dict[str, Any]):
    result = benchmark(json_dumps, rich_payload)
    assert result


def test_json_dumps_with_representation_encoder(benchmark, rich_payload: dict[str, Any]):
    result = benchmark(lambda: json_dumps(rich_payload, default=representation_encoder))
    assert result


def test_json_dumps_with_key_sanitization(benchmark, payload_with_tuple_keys: dict[str, Any]):
    result = benchmark(lambda: json_dumps(payload_with_tuple_keys, sanitize_keys=True))
    assert result


def test_json_loads(benchmark, plain_payload_as_text: str):
    result = benchmark(json_loads, plain_payload_as_text)
    assert result["total"] == _NUM_ITEMS


def test_pydantic_encoder_on_models(benchmark, rich_payload: dict[str, Any]):
    items = rich_payload["items"]

    def _encode_all() -> int:
        return sum(len(pydantic_encoder(item)) for item in items)

    assert benchmark(_encode_all) == _NUM_ITEMS * len(_Item.model_fields)

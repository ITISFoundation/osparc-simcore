"""Benchmarks for service metadata models and the json-schema utilities

Service metadata is validated every time the catalog reads a service from the
docker registry, and the input/output content-schemas of a service are validated
for every port value set in a project.
"""

from typing import Any

import pytest
from models_library.services_metadata_published import ServiceMetaDataPublished
from models_library.utils.json_schema import (
    jsonschema_validate_data,
    jsonschema_validate_schema,
)

_NUM_PORT_VALUES = 50


@pytest.fixture(scope="module")
def service_metadata_examples() -> list[dict[str, Any]]:
    examples = ServiceMetaDataPublished.model_json_schema(by_alias=True)["examples"]
    assert examples
    return examples


@pytest.fixture(scope="module")
def content_schema() -> dict[str, Any]:
    return {
        "title": "Complex parameters",
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 64},
            "count": {"type": "integer", "minimum": 0, "maximum": 1000, "default": 1},
            "ratio": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
            "enabled": {"type": "boolean", "default": False},
            "mode": {"enum": ["fast", "accurate", "debug"]},
            "coordinates": {
                "type": "array",
                "minItems": 3,
                "items": {"type": "number"},
            },
            "metadata": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["name", "ratio", "coordinates"],
    }


@pytest.fixture(scope="module")
def content_schema_instances(content_schema: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": f"run-{i}",
            "count": i,
            "ratio": (i % 100 + 1) / 100,
            "enabled": bool(i % 2),
            "mode": "fast",
            "coordinates": [float(i), float(i + 1), float(i + 2)],
            "metadata": {"run": f"{i}", "owner": "benchmark"},
        }
        for i in range(_NUM_PORT_VALUES)
    ]


def test_service_metadata_validate(benchmark, service_metadata_examples: list[dict[str, Any]]):
    def _validate_all() -> list[ServiceMetaDataPublished]:
        return [ServiceMetaDataPublished.model_validate(example) for example in service_metadata_examples]

    assert len(benchmark(_validate_all)) == len(service_metadata_examples)


def test_service_metadata_dump(benchmark, service_metadata_examples: list[dict[str, Any]]):
    models = [ServiceMetaDataPublished.model_validate(example) for example in service_metadata_examples]

    def _dump_all() -> int:
        return sum(len(model.model_dump(by_alias=True, exclude_unset=True)) for model in models)

    assert benchmark(_dump_all) > 0


def test_service_metadata_json_schema_generation(benchmark):
    schema = benchmark(lambda: ServiceMetaDataPublished.model_json_schema(by_alias=True))
    assert schema["title"]


def test_jsonschema_validate_schema(benchmark, content_schema: dict[str, Any]):
    result = benchmark(jsonschema_validate_schema, content_schema)
    assert result is content_schema


def test_jsonschema_validate_port_values(
    benchmark,
    content_schema: dict[str, Any],
    content_schema_instances: list[dict[str, Any]],
):
    def _validate_all() -> list[Any]:
        return [jsonschema_validate_data(instance, content_schema) for instance in content_schema_instances]

    assert len(benchmark(_validate_all)) == _NUM_PORT_VALUES


def test_jsonschema_validate_port_values_with_defaults(
    benchmark,
    content_schema: dict[str, Any],
    content_schema_instances: list[dict[str, Any]],
):
    def _validate_all() -> list[Any]:
        return [
            jsonschema_validate_data(instance, content_schema, return_with_default=True)
            for instance in content_schema_instances
        ]

    assert len(benchmark(_validate_all)) == _NUM_PORT_VALUES

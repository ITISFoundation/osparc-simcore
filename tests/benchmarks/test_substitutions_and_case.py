"""Benchmarks for the templating/substitution utilities of `models_library.utils`

`SpecsSubstitutionsResolver` is used to resolve osparc variables in service specs
(docker compose specs) before starting a dynamic service, and `change_case` is
used by the alias generators of most API models.
"""

from typing import Any

import pytest
from models_library.utils.change_case import (
    camel_to_snake,
    snake_to_camel,
    snake_to_upper_camel,
)
from models_library.utils.specs_substitution import SpecsSubstitutionsResolver
from models_library.utils.string_substitution import (
    substitute_all_legacy_identifiers,
    upgrade_identifier,
)

_NUM_SERVICES = 20


@pytest.fixture(scope="module")
def service_specs() -> dict[str, Any]:
    return {
        "services": {
            f"service-{i}": {
                "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/service:${SERVICE_VERSION}",
                "environment": [
                    "DY_SIDECAR_PATH_INPUTS=${DY_SIDECAR_PATH_INPUTS}",
                    "DY_SIDECAR_PATH_OUTPUTS=${DY_SIDECAR_PATH_OUTPUTS}",
                    "OSPARC_VARIABLE_PRODUCT_NAME=${OSPARC_VARIABLE_PRODUCT_NAME}",
                    "OSPARC_VARIABLE_USER_ID=${OSPARC_VARIABLE_USER_ID}",
                    "OSPARC_VARIABLE_API_KEY=${OSPARC_VARIABLE_API_KEY:-none}",
                ],
                "deploy": {
                    "resources": {
                        "limits": {"cpus": "${CPU_LIMIT}", "memory": "${RAM_LIMIT}"},
                        "reservations": {"cpus": "0.1", "memory": "100M"},
                    }
                },
            }
            for i in range(_NUM_SERVICES)
        }
    }


@pytest.fixture(scope="module")
def legacy_service_specs() -> str:
    return "\n".join(
        f"service-{i}: image %%simcore-registry%%/dyn:%%service.version%%, user %%user-id%%"
        for i in range(_NUM_SERVICES)
    )


@pytest.fixture(scope="module")
def substitutions() -> dict[str, str]:
    return {
        "SIMCORE_REGISTRY": "registry.osparc.io",
        "SERVICE_VERSION": "1.2.3",
        "DY_SIDECAR_PATH_INPUTS": "/inputs",
        "DY_SIDECAR_PATH_OUTPUTS": "/outputs",
        "OSPARC_VARIABLE_PRODUCT_NAME": "osparc",
        "OSPARC_VARIABLE_USER_ID": "42",
        "CPU_LIMIT": "2.0",
        "RAM_LIMIT": "2147483648",
    }


@pytest.fixture(scope="module")
def snake_keys() -> list[str]:
    return [f"some_rather_long_field_name_{i}" for i in range(200)]


@pytest.fixture(scope="module")
def camel_keys(snake_keys: list[str]) -> list[str]:
    return [snake_to_camel(key) for key in snake_keys]


def test_specs_substitution_resolve(benchmark, service_specs: dict[str, Any], substitutions: dict[str, str]):
    def _resolve() -> dict[str, Any]:
        resolver = SpecsSubstitutionsResolver(service_specs, upgrade=False)
        resolver.set_substitutions(mappings=substitutions)
        return resolver.run()

    result = benchmark(_resolve)
    assert result["services"]["service-0"]["image"] == "registry.osparc.io/simcore/services/dynamic/service:1.2.3"


def test_specs_substitution_get_identifiers(benchmark, service_specs: dict[str, Any]):
    resolver = SpecsSubstitutionsResolver(service_specs, upgrade=False)
    result = benchmark(resolver.get_identifiers)
    assert result


def test_substitute_all_legacy_identifiers(benchmark, legacy_service_specs: str):
    result = benchmark(substitute_all_legacy_identifiers, legacy_service_specs)
    assert "OSPARC_VARIABLE_USER_ID" in result


def test_upgrade_identifier(benchmark):
    identifiers = [f"%%some.legacy-identifier-{i}%%" for i in range(200)]

    def _upgrade_all() -> int:
        return sum(len(upgrade_identifier(identifier)) for identifier in identifiers)

    assert benchmark(_upgrade_all) > 0


def test_snake_to_camel(benchmark, snake_keys: list[str]):
    def _convert_all() -> int:
        return sum(len(snake_to_camel(key)) for key in snake_keys)

    assert benchmark(_convert_all) > 0


def test_snake_to_upper_camel(benchmark, snake_keys: list[str]):
    def _convert_all() -> int:
        return sum(len(snake_to_upper_camel(key)) for key in snake_keys)

    assert benchmark(_convert_all) > 0


def test_camel_to_snake(benchmark, camel_keys: list[str]):
    def _convert_all() -> int:
        return sum(len(camel_to_snake(key)) for key in camel_keys)

    assert benchmark(_convert_all) > 0

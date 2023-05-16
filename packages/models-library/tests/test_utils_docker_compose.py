# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
from typing import Any

import pytest
import yaml
from models_library.utils.docker_compose import (
    MATCH_SERVICE_VERSION,
    MATCH_SIMCORE_REGISTRY,
    replace_env_vars_in_compose_spec,
)
from models_library.utils.string_substitution import (
    SubstitutionsDict,
    TextTemplate,
    substitute_all_legacy_identifiers,
)


@pytest.fixture()
def docker_compose_spec() -> "ComposeSpecLabel":
    return {
        "version": "2.3",
        "services": {
            "rt-web": {
                "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/sim4life:${SERVICE_VERSION}",
                "init": True,
                "depends_on": ["s4l-core"],
            },
            "s4l-core": {
                "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/s4l-core:${SERVICE_VERSION}",
                "runtime": "nvidia",
                "init": True,
                "environment": ["DISPLAY=${DISPLAY}"],
                "volumes": ["/tmp/.X11-unix:/tmp/.X11-unix"],  # nosec
            },
        },
    }


@pytest.fixture()
def simcore_registry() -> str:
    return "mock_reg"


@pytest.fixture()
def service_version() -> str:
    return "1.2.3"


def test_replace_env_vars_in_compose_spec(
    docker_compose_spec: "ComposeSpecLabel", simcore_registry: str, service_version: str
) -> None:
    stringified_service_spec: str = replace_env_vars_in_compose_spec(
        docker_compose_spec,
        replace_simcore_registry=simcore_registry,
        replace_service_version=service_version,
    )

    test_replaced_spec = (
        yaml.safe_dump(docker_compose_spec)
        .replace(MATCH_SERVICE_VERSION, service_version)
        .replace(MATCH_SIMCORE_REGISTRY, simcore_registry)
    )

    assert stringified_service_spec == test_replaced_spec


@pytest.fixture()
def vendor_environs_for_this_service() -> dict[str, str | int]:
    return {
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_HOST": "product_a-server",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_PRIMARY_PORT": 1,
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_SERVER_SECONDARY_PORT": 2,
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_IP": "1.1.1.1",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_DNS_RESOLVER_PORT": "21",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE": "license.txt",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE_PRODUCT1": "license-p1.txt",
        "OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE_PRODUCT2": "license-p2.txt",
        "OSPARC_ENVIRONMENT_VENDOR_LIST": "[1, 2, 3]",
    }


def _create_text_template(compose_service_spec: dict[str, Any]) -> TextTemplate:
    # convert
    service_spec_str: str = yaml.safe_dump(compose_service_spec)

    # legacy
    service_spec_str = substitute_all_legacy_identifiers(service_spec_str)

    # template
    template = TextTemplate(service_spec_str)
    assert template.is_valid()

    return template


@pytest.mark.testit
@pytest.mark.parametrize(
    "service_name,service_spec,expected_service_spec",
    [
        (
            "other_service",
            {
                "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/other_service:${SERVICE_VERSION}",
                "init": True,
                "depends_on": ["this_service"],
            },
            {
                "depends_on": ["this_service"],
                "image": "mock_reg/simcore/services/dynamic/other_service:1.2.3",
                "init": True,
            },
        ),
        (
            "this_service",
            {
                "image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/this_service:${SERVICE_VERSION}",
                "runtime": "nvidia",
                "init": True,
                "environment": [
                    "DISPLAY=${DISPLAY}",
                    "SOME_LIST=$OSPARC_ENVIRONMENT_VENDOR_LIST",
                    "MY_LICENSE=$OSPARC_ENVIRONMENT_VENDOR_LICENSE_FILE",
                ],
                "volumes": ["/tmp/.X11-unix:/tmp/.X11-unix"],
            },
            {
                "environment": [
                    "DISPLAY=True",
                    "SOME_LIST=[1, 2, 3]",
                    "MY_LICENSE=license.txt",
                ],
                "image": "mock_reg/simcore/services/dynamic/this_service:1.2.3",
                "init": True,
                "runtime": "nvidia",
                "volumes": ["/tmp/.X11-unix:/tmp/.X11-unix"],
            },
        ),
    ],
)
def test_substitutions_in_compose_spec(
    vendor_environs_for_this_service: dict[str, str | int],
    simcore_registry: str,
    service_version: str,
    service_name: str,
    service_spec: dict[str, Any],
    expected_service_spec: dict[str, Any],
):
    template = _create_text_template(service_spec)

    identifiers_requested = template.get_identifiers()

    # pick from available oenvs only those requested
    available_osparc_environments = {
        **vendor_environs_for_this_service,
        "SIMCORE_REGISTRY": simcore_registry,
        "SERVICE_VERSION": service_version,
        "DISPLAY": "True",
    }
    substitutions = SubstitutionsDict(
        {
            identifier: available_osparc_environments[identifier]
            for identifier in identifiers_requested
            if identifier in available_osparc_environments
        }
    )

    assert set(identifiers_requested) == set(substitutions.keys())

    new_service_spec_str = template.safe_substitute(substitutions)

    assert not substitutions.unused
    assert substitutions.used == set(identifiers_requested)

    assert (
        "$" not in new_service_spec_str
    ), f"All should be replaced in '{service_name}': {substitutions.used}"

    # can de/serialize
    new_service_spec: dict = yaml.safe_load(new_service_spec_str)
    print(json.dumps(new_service_spec, indent=1))

    assert new_service_spec == expected_service_spec

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Any

import pytest
import yaml
from models_library.utils.specs_substitution import (
    SpecsSubstitutionsResolver,
    SubstitutionValue,
)
from pydantic import parse_obj_as


@pytest.fixture()
def simcore_registry() -> str:
    return "mock_registry_basename"


@pytest.fixture()
def service_version() -> str:
    return "1.2.3"


@pytest.fixture()
def available_osparc_variables(
    simcore_registry: str,
    service_version: str,
) -> dict[str, SubstitutionValue]:
    osparc_vendor_variables = {
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_SERVER_HOST": "product_a-server",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_SERVER_PRIMARY_PORT": 1,
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_SERVER_SECONDARY_PORT": 2,
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_DNS_RESOLVER_IP": "1.1.1.1",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_DNS_RESOLVER_PORT": "21",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_FILE": "license.txt",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_FILE_PRODUCT1": "license-p1.txt",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_FILE_PRODUCT2": "license-p2.txt",
        "OSPARC_VARIABLE_VENDOR_SECRET_LIST": "[1, 2, 3]",
    }

    environs = {
        **osparc_vendor_variables,
        "SIMCORE_REGISTRY": simcore_registry,
        "SERVICE_VERSION": service_version,
        "DISPLAY": "True",
    }
    return parse_obj_as(dict[str, SubstitutionValue], environs)


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
                "image": "mock_registry_basename/simcore/services/dynamic/other_service:1.2.3",
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
                    "SOME_LIST=$OSPARC_VARIABLE_VENDOR_SECRET_LIST",
                    "MY_LICENSE=$OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_FILE",
                ],
                "volumes": ["/tmp/.X11-unix:/tmp/.X11-unix"],
            },
            {
                "environment": [
                    "DISPLAY=True",
                    "SOME_LIST=[1, 2, 3]",
                    "MY_LICENSE=license.txt",
                ],
                "image": "mock_registry_basename/simcore/services/dynamic/this_service:1.2.3",
                "init": True,
                "runtime": "nvidia",
                "volumes": ["/tmp/.X11-unix:/tmp/.X11-unix"],
            },
        ),
    ],
)
def test_substitutions_in_compose_spec(
    available_osparc_variables: dict[str, SubstitutionValue],
    service_name: str,
    service_spec: dict[str, Any],
    expected_service_spec: dict[str, Any],
):
    specs_resolver = SpecsSubstitutionsResolver(service_spec, upgrade=True)

    identifiers_requested = specs_resolver.get_identifiers()

    substitutions = specs_resolver.set_substitutions(available_osparc_variables)
    assert substitutions is specs_resolver.substitutions

    assert set(identifiers_requested) == set(substitutions.keys())

    new_service_spec = specs_resolver.run()

    assert not substitutions.unused
    assert substitutions.used == set(identifiers_requested)

    new_service_spec_text = yaml.safe_dump(new_service_spec)

    assert (
        "$" not in new_service_spec_text
    ), f"All should be replaced in '{service_name}': {substitutions.used}"

    assert new_service_spec == expected_service_spec


def test_nothing_to_substitute():

    original_spec = {"x": 33, "y": {"z": True}}

    specs_resolver = SpecsSubstitutionsResolver(original_spec, upgrade=False)

    # no substitutions
    assert specs_resolver.run() == original_spec


def test_no_identifier_present(
    available_osparc_variables: dict[str, SubstitutionValue]
):

    original_spec = {"x": 33, "y": {"z": True}, "foo": "$UNREGISTERED_ID"}

    specs_resolver = SpecsSubstitutionsResolver(original_spec, upgrade=False)

    assert specs_resolver.get_identifiers() == ["UNREGISTERED_ID"]
    assert specs_resolver.set_substitutions(available_osparc_variables) == {}

    # no substitutions
    assert specs_resolver.run() == original_spec

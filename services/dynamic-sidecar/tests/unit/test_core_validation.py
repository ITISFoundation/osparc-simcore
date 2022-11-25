# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from inspect import signature

import pytest
from simcore_service_dynamic_sidecar.core.validation import (
    _DEFAULT_USER_SERVICES_NETWORK_NAME,
    _connect_user_services,
    parse_compose_spec,
)


@pytest.fixture
def incoming_iseg_compose_file_content() -> str:
    return """
networks:
  dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8:
    driver: overlay
    external:
      name: dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8
services:
  iseg-app:
    image: registry.osparc.org/simcore/services/dynamic/iseg-app:1.0.7
  iseg-web:
    image: registry.osparc.org/simcore/services/dynamic/iseg-web:1.0.7
    networks:
      dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8:
version: \'3.7\'
    """


@pytest.fixture
def incoming_iseg_compose_file_content_missing_network() -> str:
    return """
networks:
services:
  iseg-app:
    image: registry.osparc.org/simcore/services/dynamic/iseg-app:1.0.7
  iseg-web:
    image: registry.osparc.org/simcore/services/dynamic/iseg-web:1.0.7
    networks:
      dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8:
version: \'3.7\'
    """


@pytest.fixture
def incoming_iseg_compose_file_content_missing_network_list() -> str:
    return """
networks:
services:
  iseg-app:
    image: registry.osparc.org/simcore/services/dynamic/iseg-app:1.0.7
  iseg-web:
    image: registry.osparc.org/simcore/services/dynamic/iseg-web:1.0.7
    networks:
      - dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8
version: \'3.7\'
    """


@pytest.fixture
def incoming_iseg_compose_file_content_no_networks() -> str:
    return """
services:
  iseg-app:
    image: registry.osparc.org/simcore/services/dynamic/iseg-app:1.0.7
  iseg-web:
    image: registry.osparc.org/simcore/services/dynamic/iseg-web:1.0.7
version: \'3.7\'
    """


@pytest.fixture(
    params=[
        "incoming_iseg_compose_file_content",
        "incoming_iseg_compose_file_content_missing_network",
        "incoming_iseg_compose_file_content_missing_network_list",
        "incoming_iseg_compose_file_content_no_networks",
    ]
)
def incoming_compose_file(
    request,
    incoming_iseg_compose_file_content: str,
    incoming_iseg_compose_file_content_missing_network: str,
    incoming_iseg_compose_file_content_missing_network_list: str,
    incoming_iseg_compose_file_content_no_networks: str,
) -> str:
    # check that fixture_name is present in this function's parameters
    fixture_name = request.param
    sig = signature(incoming_compose_file)
    assert fixture_name in sig.parameters, (
        f"Provided fixture name {fixture_name} was not found "
        f"as a parameter in the signature {sig}"
    )

    # returns the parameter by name from the ones declared in the signature
    result: str = locals()[fixture_name]
    return result


def test_inject_backend_networking(incoming_compose_file: str):
    """
    NOTE: this goes with issue [https://github.com/ITISFoundation/osparc-simcore/issues/3261]
    """
    parsed_compose_spec = parse_compose_spec(incoming_compose_file)
    _connect_user_services(parsed_compose_spec)
    assert _DEFAULT_USER_SERVICES_NETWORK_NAME in parsed_compose_spec["networks"]
    assert (
        _DEFAULT_USER_SERVICES_NETWORK_NAME
        in parsed_compose_spec["services"]["iseg-app"]["networks"]
    )
    assert (
        _DEFAULT_USER_SERVICES_NETWORK_NAME
        in parsed_compose_spec["services"]["iseg-web"]["networks"]
    )

# pylint: disable=redefined-outer-name

import pytest
import yaml
from models_library.utils.docker_compose import (
    MATCH_SERVICE_VERSION,
    MATCH_SIMCORE_REGISTRY,
    replace_env_vars_in_compose_spec,
)


@pytest.fixture()
def service_spec() -> "ComposeSpecLabel":
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
    return "mock_reg"


def test_replace_env_vars_in_compose_spec(
    service_spec: "ComposeSpecLabel", simcore_registry: str, service_version: str
) -> None:
    stringified_service_spec: str = replace_env_vars_in_compose_spec(
        service_spec,
        replace_simcore_registry=simcore_registry,
        replace_service_version=service_version,
    )

    test_replaced_spec = (
        yaml.safe_dump(service_spec)
        .replace(MATCH_SERVICE_VERSION, service_version)
        .replace(MATCH_SIMCORE_REGISTRY, simcore_registry)
    )

    assert stringified_service_spec == test_replaced_spec

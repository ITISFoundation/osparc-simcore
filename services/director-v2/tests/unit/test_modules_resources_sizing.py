# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""Pure unit tests for the sizing functions of `modules.resources_sizing`.

The expected CPU/RAM values are HAND-COMPUTED literals from the fixed EC2 specs
of `pytest_simcore.helpers.project_nodes_pricing` (see the drift guard below).
"""

from collections.abc import Callable
from copy import deepcopy
from typing import Any, Final

import pytest
from models_library.resource_tracker import HardwareInfo
from models_library.services_resources import ServiceResourcesDict
from pydantic import TypeAdapter
from pytest_simcore.helpers.project_nodes_pricing import (
    R5_4XLARGE_NAME,
    T3_MEDIUM_NAME,
    fake_compute_node_resources_for_hardware,
    get_fixed_ec2_instance_types,
    single_container_required_resources,
)
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    MultiContainerOverrideNotSupportedRPCError,
)
from simcore_service_director_v2.modules import resources_sizing

pytest_simcore_core_services_selection: Final[list[str]] = []

_RESOURCES_ADAPTER: Final[TypeAdapter[ServiceResourcesDict]] = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict)

_COMP_KEY: Final[str] = "simcore/services/comp/itis/sleeper"
_DYNAMIC_KEY: Final[str] = "simcore/services/dynamic/jupyter-mock"
_VERSION: Final[str] = "1.0.0"


def _single_container_payload() -> dict[str, Any]:
    return single_container_required_resources("library/nginx:latest")


def _multi_container_resources() -> dict[str, Any]:
    # sub-service names differ from DEFAULT_SINGLE_SERVICE_NAME ("container"),
    # which is what marks the payload as a multi-container service
    main = single_container_required_resources("library/nginx:latest", cpu=0.1, ram_bytes=2 * 1024**3)["container"]
    sidecar = single_container_required_resources("library/nginx:latest", cpu=0.1, ram_bytes=1536 * 1024**2)[
        "container"
    ]
    return {"main": main, "sidecar": sidecar}


_SIZING_CASES: Final[list[tuple[str, Callable[..., ServiceResourcesDict], Callable[[], dict[str, Any]]]]] = [
    (_COMP_KEY, resources_sizing.resize_computational_node_resources, _single_container_payload),
    (_COMP_KEY, resources_sizing.resize_computational_node_resources, _multi_container_resources),
    (_DYNAMIC_KEY, resources_sizing.resize_dynamic_node_resources, _single_container_payload),
    (_DYNAMIC_KEY, resources_sizing.resize_dynamic_node_resources, _multi_container_resources),
]

_SIZING_CASE_IDS: Final[list[str]] = [
    f"{key.split('/')[2]}-{'multi' if factory is _multi_container_resources else 'single'}"
    for key, _, factory in _SIZING_CASES
]


@pytest.mark.parametrize("machine", [T3_MEDIUM_NAME, R5_4XLARGE_NAME])
@pytest.mark.parametrize(
    "service_key,resize_implementation,resources_payload",
    _SIZING_CASES,
    ids=_SIZING_CASE_IDS,
)
async def test_sizing_test_double_does_not_drift_from_the_implementation(
    machine: str,
    service_key: str,
    resize_implementation: Callable[..., ServiceResourcesDict],
    resources_payload: Callable[[], dict[str, Any]],
):
    # the fake in pytest_simcore stands in for director-v2 in ALL web-server tests;
    # this fails when the real sizing changes without updating the fake in lockstep
    ec2_instance_type = get_fixed_ec2_instance_types({machine})[0]

    # each side must get its OWN deep copy of the input: resizing mutates the
    # nested ResourceValue objects in place, so a shared payload would let both
    # results mirror the same mutations and compare equal regardless of the math
    resources = _RESOURCES_ADAPTER.validate_python(resources_payload())

    # an outcome is either the resized resources or the error type both sides must raise
    expected: ServiceResourcesDict | type[Exception]
    try:
        expected = resize_implementation(deepcopy(resources), ec2_instance_type=ec2_instance_type)
    except MultiContainerOverrideNotSupportedRPCError:
        expected = MultiContainerOverrideNotSupportedRPCError

    actual: ServiceResourcesDict | type[Exception]
    try:
        actual = await fake_compute_node_resources_for_hardware(
            None,
            service_key=service_key,
            service_version=_VERSION,
            resources=deepcopy(resources),
            hardware_info=HardwareInfo(aws_ec2_instances=[machine]),
        )
    except MultiContainerOverrideNotSupportedRPCError:
        actual = MultiContainerOverrideNotSupportedRPCError

    if isinstance(expected, type):
        assert actual is expected, f"fake must raise {expected.__name__} where the implementation raises it"
    else:
        assert actual == expected

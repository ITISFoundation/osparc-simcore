# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument

"""Tests for the director-v2 sizing RPC `compute_node_resources_for_hardware`.

The expected CPU/RAM values are HAND-COMPUTED literals (never computed by calling
the implementation) from the fixed EC2 specs of
`pytest_simcore.helpers.project_nodes_pricing`:

=====================  =========================  ==========================
EC2 type               dask (cpu, ram bytes)      dynamic (cpu, ram bytes)
=====================  =========================  ==========================
``t3.medium``          1.9,  3865470566           0.6,  2791728742
``r5.4xlarge``         15.9, 123695058124         14.6, 122621316300
=====================  =========================  ==========================
"""

from collections.abc import Callable
from typing import Any, Final
from unittest import mock

import pytest
from models_library.resource_tracker import HardwareInfo
from models_library.services_resources import ServiceResourcesDict
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.project_nodes_pricing import (
    R5_4XLARGE_NAME,
    T3_MEDIUM_NAME,
    fake_compute_node_resources_for_hardware,
    get_fixed_ec2_instance_types,
    single_container_required_resources,
)
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.clusters_keeper.errors import InvalidEC2InstanceTypesRPCError
from servicelib.rabbitmq.rpc_interfaces.director_v2 import resources as rpc_resources
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    ClustersKeeperNotAvailableRPCError,
    EC2InstanceTypeNotFoundRPCError,
    MultiContainerOverrideNotSupportedRPCError,
    UnsupportedNodeClassRPCError,
)
from simcore_service_director_v2.modules import resources_sizing

pytest_simcore_core_services_selection = ["postgres", "rabbit", "redis"]

_RESOURCES_ADAPTER: Final[TypeAdapter[ServiceResourcesDict]] = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict)


_COMP_KEY: Final[str] = "simcore/services/comp/itis/sleeper"
_DYNAMIC_KEY: Final[str] = "simcore/services/dynamic/jupyter-mock"
_FRONTEND_KEY: Final[str] = "simcore/services/frontend/file-picker"
_VERSION: Final[str] = "1.0.0"


@pytest.fixture
def mocked_clusters_keeper(mocker: MockerFixture) -> mock.AsyncMock:
    """clusters-keeper answers with the FIXED machine types of the pytest helper"""

    async def _get_instance_type_details(client, *, instance_type_names: set[str]):
        return get_fixed_ec2_instance_types(set(instance_type_names))

    mocked = mocker.patch(
        "simcore_service_director_v2.modules.resources_sizing.get_instance_type_details",
        autospec=True,
    )
    mocked.side_effect = _get_instance_type_details
    return mocked


async def _request_sizing(
    rpc_client: RabbitMQRPCClient,
    *,
    service_key: str,
    resources: ServiceResourcesDict,
    machine: str,
) -> ServiceResourcesDict:
    return await rpc_resources.compute_node_resources_for_hardware(
        rpc_client,
        service_key=service_key,
        service_version=_VERSION,
        resources=resources,
        hardware_info=HardwareInfo(aws_ec2_instances=[machine]),
    )


async def test_sizing_rpc_sizes_computational_node_with_dask_worker_formula(
    rpc_client: RabbitMQRPCClient,
    mocked_clusters_keeper: mock.AsyncMock,
):
    resources = _RESOURCES_ADAPTER.validate_python(single_container_required_resources("library/nginx:latest"))
    resized = await _request_sizing(rpc_client, service_key=_COMP_KEY, resources=resources, machine=R5_4XLARGE_NAME)
    container = resized["container"].resources
    assert container["CPU"].limit == pytest.approx(15.9)
    assert container["RAM"].limit == 123695058124
    # the whole machine's reservation follows the limit
    assert container["CPU"].reservation == pytest.approx(15.9)
    assert container["RAM"].reservation == 123695058124


async def test_sizing_rpc_sizes_dynamic_node_with_dynamic_sidecar_formula(
    rpc_client: RabbitMQRPCClient,
    mocked_clusters_keeper: mock.AsyncMock,
):
    resources = _RESOURCES_ADAPTER.validate_python(single_container_required_resources("library/nginx:latest"))
    resized = await _request_sizing(rpc_client, service_key=_DYNAMIC_KEY, resources=resources, machine=R5_4XLARGE_NAME)
    container = resized["container"].resources
    assert container["CPU"].limit == pytest.approx(14.6)
    assert container["RAM"].limit == 122621316300


def _multi_container_resources() -> dict[str, Any]:
    # NOTE: sub-service names must differ from DEFAULT_SINGLE_SERVICE_NAME ("container"),
    # otherwise the dict is treated as a single-container service.
    # NOTE: RAM values below 1e9 are interpreted as MB (not bytes) by the resource
    # Quantity, so all RAM amounts here stay above that threshold.
    main = single_container_required_resources("library/nginx:latest", cpu=0.1, ram_bytes=2 * 1024**3)["container"]
    sidecar = single_container_required_resources("library/nginx:latest", cpu=0.1, ram_bytes=1536 * 1024**2)[
        "container"
    ]
    return {"main": main, "sidecar": sidecar}


async def test_sizing_rpc_scales_largest_sub_service_of_multi_container_dynamic_node(
    rpc_client: RabbitMQRPCClient,
    mocked_clusters_keeper: mock.AsyncMock,
):
    # t3.medium: base cpu 0.6 / ram 2791728742. the largest sub-service ("main",
    # 2 GiB) absorbs what the other one ("sidecar": 0.1 CPU / 1.5 GiB) does not use:
    #   cpu = max(0.6 - 0.1, 0.5) = 0.5
    #   ram = 2791728742 - 1610612736 = 1181116006
    resources = _RESOURCES_ADAPTER.validate_python(_multi_container_resources())
    resized = await _request_sizing(rpc_client, service_key=_DYNAMIC_KEY, resources=resources, machine=T3_MEDIUM_NAME)
    assert resized["main"].resources["CPU"].limit == pytest.approx(0.5)
    assert resized["main"].resources["RAM"].limit == 1181116006
    # the small sub-service keeps its original (requested) resources
    assert resized["sidecar"].resources["CPU"].limit == pytest.approx(0.1)
    assert resized["sidecar"].resources["RAM"].limit == 1536 * 1024**2


async def test_sizing_rpc_rejects_multi_container_computational_node(
    rpc_client: RabbitMQRPCClient,
    mocked_clusters_keeper: mock.AsyncMock,
):
    # per-sub-service sizing of a multi-container service is not implemented: the
    # call fails with a dedicated error (reraised here through the real RPC) and
    # the resources are never silently left unsized
    resources = _RESOURCES_ADAPTER.validate_python(_multi_container_resources())
    with pytest.raises(MultiContainerOverrideNotSupportedRPCError) as exc_info:
        await _request_sizing(rpc_client, service_key=_COMP_KEY, resources=resources, machine=R5_4XLARGE_NAME)
    assert exc_info.value.error_context()["sub_service_names"] == {"main", "sidecar"}


async def test_sizing_rpc_returns_resources_unchanged_without_ec2_machine(
    rpc_client: RabbitMQRPCClient,
    mocked_clusters_keeper: mock.AsyncMock,
):
    resources = _RESOURCES_ADAPTER.validate_python(single_container_required_resources("library/nginx:latest"))
    resized = await rpc_resources.compute_node_resources_for_hardware(
        rpc_client,
        service_key=_COMP_KEY,
        service_version=_VERSION,
        resources=resources,
        hardware_info=HardwareInfo(aws_ec2_instances=[]),
    )
    assert resized == resources
    mocked_clusters_keeper.assert_not_called()


async def test_sizing_rpc_rejects_frontend_nodes(
    rpc_client: RabbitMQRPCClient,
    mocked_clusters_keeper: mock.AsyncMock,
):
    # a frontend node is rejected even though clusters-keeper would answer: its
    # resources do not depend on an EC2 machine
    resources = _RESOURCES_ADAPTER.validate_python(single_container_required_resources("library/nginx:latest"))
    with pytest.raises(UnsupportedNodeClassRPCError):
        await _request_sizing(rpc_client, service_key=_FRONTEND_KEY, resources=resources, machine=R5_4XLARGE_NAME)
    mocked_clusters_keeper.assert_not_called()


async def test_sizing_rpc_fails_on_ec2_type_unknown_to_clusters_keeper(
    rpc_client: RabbitMQRPCClient,
    mocker: MockerFixture,
):
    # clusters-keeper answers (successfully) but WITHOUT the requested machine type
    async def _other_machine(client, *, instance_type_names: set[str]):
        assert "not-a-known-type" in instance_type_names
        return get_fixed_ec2_instance_types({T3_MEDIUM_NAME})

    mocked = mocker.patch(
        "simcore_service_director_v2.modules.resources_sizing.get_instance_type_details",
        autospec=True,
    )
    mocked.side_effect = _other_machine

    resources = _RESOURCES_ADAPTER.validate_python(single_container_required_resources("library/nginx:latest"))
    with pytest.raises(EC2InstanceTypeNotFoundRPCError):
        await _request_sizing(rpc_client, service_key=_COMP_KEY, resources=resources, machine="not-a-known-type")


async def test_sizing_rpc_maps_clusters_keeper_unavailability(
    rpc_client: RabbitMQRPCClient,
    mocker: MockerFixture,
):
    mocked = mocker.patch(
        "simcore_service_director_v2.modules.resources_sizing.get_instance_type_details",
        autospec=True,
    )
    mocked.side_effect = TimeoutError()

    resources = _RESOURCES_ADAPTER.validate_python(single_container_required_resources("library/nginx:latest"))
    with pytest.raises(ClustersKeeperNotAvailableRPCError):
        await _request_sizing(rpc_client, service_key=_COMP_KEY, resources=resources, machine=T3_MEDIUM_NAME)


async def test_sizing_rpc_maps_clusters_keeper_invalid_type_rejection(
    rpc_client: RabbitMQRPCClient,
    mocker: MockerFixture,
):
    # this is how the real clusters-keeper fails on an invalid machine type: it
    # rejects the request with InvalidEC2InstanceTypesRPCError (a RPCServerError
    # subclass), which must NOT be classified as an outage
    mocked = mocker.patch(
        "simcore_service_director_v2.modules.resources_sizing.get_instance_type_details",
        autospec=True,
    )
    mocked.side_effect = InvalidEC2InstanceTypesRPCError(ec2_types={"not-a-known-type"})

    resources = _RESOURCES_ADAPTER.validate_python(single_container_required_resources("library/nginx:latest"))
    with pytest.raises(EC2InstanceTypeNotFoundRPCError):
        await _request_sizing(rpc_client, service_key=_COMP_KEY, resources=resources, machine="not-a-known-type")


def _single_container_payload() -> dict[str, Any]:
    return single_container_required_resources("library/nginx:latest")


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
    resources = _RESOURCES_ADAPTER.validate_python(resources_payload())
    ec2_instance_type = get_fixed_ec2_instance_types({machine})[0]

    # an outcome is either the resized resources or the error type both sides must raise
    expected: ServiceResourcesDict | type[Exception]
    try:
        expected = resize_implementation(resources, ec2_instance_type=ec2_instance_type)
    except MultiContainerOverrideNotSupportedRPCError:
        expected = MultiContainerOverrideNotSupportedRPCError

    actual: ServiceResourcesDict | type[Exception]
    try:
        actual = await fake_compute_node_resources_for_hardware(
            None,
            service_key=service_key,
            service_version=_VERSION,
            resources=resources,
            hardware_info=HardwareInfo(aws_ec2_instances=[machine]),
        )
    except MultiContainerOverrideNotSupportedRPCError:
        actual = MultiContainerOverrideNotSupportedRPCError

    if isinstance(expected, type):
        assert actual is expected, f"fake must raise {expected.__name__} where the implementation raises it"
    else:
        assert actual == expected

"""Unit tests for the service-calling phase of the task creation

These are the calls that used to run **inside** the transaction that updated
`projects_nodes`, i.e. while holding its row locks:
https://github.com/ITISFoundation/private-issues/issues/669

`generate_tasks_list_from_project` must
- take no database connection at all,
- perform every external call only once per distinct argument,
- return the `projects_nodes` writes it computed instead of applying them.
"""

# ruff: noqa: SLF001
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import inspect
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_resource_usage_tracker.pricing_plans import RutPricingUnitGet
from models_library.projects import NodesDict
from models_library.projects_nodes import Node
from models_library.resource_tracker import HardwareInfo
from models_library.services import ServiceKeyVersion
from models_library.services_resources import (
    DEFAULT_SINGLE_SERVICE_NAME,
    BootMode,
    ServiceResourcesDict,
)
from models_library.wallets import WalletInfo
from pydantic import TypeAdapter
from servicelib.rabbitmq import RPCServerError
from simcore_service_director_v2.modules.db.repositories.comp_tasks import _utils
from simcore_service_director_v2.modules.db.repositories.comp_tasks._utils import (
    ProjectNodesSnapshot,
)

_PRODUCT_NAME = "sim4life.io"
_CPU_SERVICE_KEY = "simcore/services/comp/is4cpu"
_GPU_SERVICE_KEY = "simcore/services/comp/is4gpu"
_SERVICE_VERSION = "1.0.0"
_EC2_INSTANCE_TYPE = "c5.xlarge"
_8_CPUS = 8.0
_16_GIB = 16 * 1024 * 1024 * 1024


def _resources(cpu: float = 2, ram_gib: int = 4) -> dict[str, Any]:
    """resources of a single-container service, as stored in `projects_nodes`"""
    return TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).dump_python(
        TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(
            {
                DEFAULT_SINGLE_SERVICE_NAME: {
                    "image": f"{_CPU_SERVICE_KEY}:{_SERVICE_VERSION}",
                    "resources": {
                        "CPU": {"limit": cpu, "reservation": 0.1},
                        "RAM": {"limit": ram_gib * 1024 * 1024 * 1024, "reservation": 268435456},
                    },
                    "boot_modes": [BootMode.CPU],
                }
            }
        ),
        mode="json",
    )


def _pricing_unit_get(*, pricing_unit_id: int) -> RutPricingUnitGet:
    return RutPricingUnitGet(
        pricing_unit_id=pricing_unit_id,
        unit_name="SMALL",
        unit_extra_info={"CPU": 2, "RAM": "4GiB", "VRAM": "0"},
        current_cost_per_unit=Decimal(pricing_unit_id),
        current_cost_per_unit_id=pricing_unit_id,
        default=True,
        specific_info=HardwareInfo(aws_ec2_instances=[_EC2_INSTANCE_TYPE]),
    )


def _wallet() -> WalletInfo:
    return WalletInfo(wallet_id=1, wallet_name="w", wallet_credit_amount=Decimal(100))


def _project_nodes(node_ids: list[UUID], service_key: str = _CPU_SERVICE_KEY) -> NodesDict:
    return {
        f"{node_id}": Node.model_validate({"key": service_key, "version": _SERVICE_VERSION, "label": "node"})
        for node_id in node_ids
    }


@pytest.fixture
def calls() -> SimpleNamespace:
    return SimpleNamespace(node_infos=[], default_pricing=[], pricing_units=[], ec2_lookups=[])


@pytest.fixture
def ec2_instance_type() -> EC2InstanceTypeGet:
    return EC2InstanceTypeGet(name=_EC2_INSTANCE_TYPE, cpus=_8_CPUS, ram=_16_GIB)


@pytest.fixture
def fake_rut_client(calls: SimpleNamespace) -> SimpleNamespace:
    """only the two calls made to the resource-usage-tracker"""

    async def get_default_pricing_and_hardware_info(
        product_name: str, service_key: str, service_version: str
    ) -> tuple[int, int, int, Decimal]:
        calls.default_pricing.append(ServiceKeyVersion(key=service_key, version=service_version))
        return (1, 2, 1, Decimal(1))

    async def get_pricing_unit(product_name: str, pricing_plan_id: int, pricing_unit_id: int) -> RutPricingUnitGet:
        calls.pricing_units.append((pricing_plan_id, pricing_unit_id))
        return _pricing_unit_get(pricing_unit_id=pricing_unit_id)

    return SimpleNamespace(
        get_default_pricing_and_hardware_info=get_default_pricing_and_hardware_info,
        get_pricing_unit=get_pricing_unit,
    )


@pytest.fixture
def patched_backends(
    monkeypatch: pytest.MonkeyPatch,
    calls: SimpleNamespace,
    ec2_instance_type: EC2InstanceTypeGet,
) -> None:
    async def fake_get_node_infos(_client, _user_id, _product_name, key_version):
        calls.node_infos.append(key_version)
        node_details = SimpleNamespace(model_dump=lambda **_kwargs: {"inputs": {}, "outputs": {}})
        return node_details, None, None

    async def fake_get_instance_type_details(_rpc_client, *, instance_type_names):
        calls.ec2_lookups.append(frozenset(instance_type_names))
        # NOTE: like production, only the known machine types are returned
        return [ec2_instance_type] if ec2_instance_type.name in instance_type_names else []

    async def fake_generate_task_image(**kwargs: Any):
        return _utils.Image(name=kwargs["node"].key, tag=kwargs["node"].version)

    monkeypatch.setattr(_utils, "_get_node_infos", fake_get_node_infos)
    monkeypatch.setattr(_utils, "_generate_task_image", fake_generate_task_image)
    # NOTE: same patch point as the comp_scheduler integration tests use
    monkeypatch.setattr(_utils, "get_instance_type_details", fake_get_instance_type_details)


async def _generate(
    *,
    project_nodes: NodesDict,
    snapshot: ProjectNodesSnapshot,
    wallet_info: WalletInfo | None,
    rut_client: SimpleNamespace,
):
    return await _utils.generate_tasks_list_from_project(
        project=SimpleNamespace(uuid=uuid4(), prj_owner=1),
        project_nodes=project_nodes,
        catalog_client=SimpleNamespace(),
        published_nodes=[],
        user_id=1,
        product_name=_PRODUCT_NAME,
        rut_client=rut_client,
        wallet_info=wallet_info,
        rabbitmq_rpc_client=SimpleNamespace(),
        snapshot=snapshot,
    )


def test_generate_tasks_list_from_project_takes_no_database_connection():
    """the whole point of the restructure: no row can be locked any more"""
    parameters = inspect.signature(_utils.generate_tasks_list_from_project).parameters
    assert "connection" not in parameters
    assert "snapshot" in parameters


async def test_external_calls_are_done_once_per_distinct_argument(
    patched_backends: None,
    calls: SimpleNamespace,
    fake_rut_client: SimpleNamespace,
) -> None:
    node_ids = [uuid4() for _ in range(3)]
    project_nodes: NodesDict = {
        **_project_nodes(node_ids[:1], _CPU_SERVICE_KEY),
        **_project_nodes(node_ids[1:2], _GPU_SERVICE_KEY),
        **_project_nodes(node_ids[2:]),
    }
    snapshot = ProjectNodesSnapshot(
        required_resources={node_id: _resources() for node_id in node_ids},
        pricing_unit_ids=dict.fromkeys(node_ids, (1, 2)),
    )

    tasks, insufficient_credits, pending = await _generate(
        project_nodes=project_nodes,
        snapshot=snapshot,
        wallet_info=_wallet(),
        rut_client=fake_rut_client,
    )

    assert len(tasks) == 3
    assert not insufficient_credits
    # one catalog lookup per distinct service, not per node
    assert sorted(key_version.key for key_version in calls.node_infos) == [_CPU_SERVICE_KEY, _GPU_SERVICE_KEY]
    # every node already has a pricing unit connected: no default lookup at all
    assert calls.default_pricing == []
    # one pricing-unit fetch per distinct (plan, unit), although all 3 nodes share it
    assert calls.pricing_units == [(1, 2)]
    # clusters-keeper is asked ONCE for the whole project
    assert calls.ec2_lookups == [frozenset({_EC2_INSTANCE_TYPE})]
    # the pricing unit was already connected to every node
    assert pending.pricing_unit_ids == {}
    # the resources of the 3 nodes are returned to be written by the caller
    assert set(pending.required_resources) == set(node_ids)


async def test_ec2_resources_are_computed_but_not_written(
    patched_backends: None,
    calls: SimpleNamespace,
    fake_rut_client: SimpleNamespace,
) -> None:
    node_ids = [uuid4(), uuid4()]
    snapshot = ProjectNodesSnapshot(
        required_resources={node_id: _resources() for node_id in node_ids},
        pricing_unit_ids=dict.fromkeys(node_ids, (1, 2)),
    )

    tasks, _, pending = await _generate(
        project_nodes=_project_nodes(node_ids),
        snapshot=snapshot,
        wallet_info=_wallet(),
        rut_client=fake_rut_client,
    )

    assert len(tasks) == 2
    assert calls.ec2_lookups == [frozenset({_EC2_INSTANCE_TYPE})]
    # the 8-cpus machine must have replaced the 2-cpus request of both nodes
    assert set(pending.required_resources) == set(node_ids)
    for dumped in pending.required_resources.values():
        resources = TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(dumped)
        image_resources = resources[DEFAULT_SINGLE_SERVICE_NAME]
        assert 0 < image_resources.resources["CPU"].limit < _8_CPUS
        assert 0 < image_resources.resources["RAM"].limit < _16_GIB


async def test_required_resources_not_written_when_already_up_to_date(
    patched_backends: None,
    fake_rut_client: SimpleNamespace,
    ec2_instance_type: EC2InstanceTypeGet,
) -> None:
    """writing the same value again would take a row lock for nothing"""
    node_id = uuid4()
    adjusted = _utils._compute_hardware_adjusted_resources(
        project_id=uuid4(),
        node_id=node_id,
        node_resources=TypeAdapter[ServiceResourcesDict](ServiceResourcesDict).validate_python(_resources()),
        hardware_info=HardwareInfo(aws_ec2_instances=[_EC2_INSTANCE_TYPE]),
        ec2_instance_types={_EC2_INSTANCE_TYPE: ec2_instance_type},
    )
    assert adjusted is not None
    dumped, _ = adjusted

    _, _, pending = await _generate(
        project_nodes=_project_nodes([node_id]),
        snapshot=ProjectNodesSnapshot(required_resources={node_id: dumped}, pricing_unit_ids={node_id: (1, 2)}),
        wallet_info=_wallet(),
        rut_client=fake_rut_client,
    )
    assert pending.required_resources == {}


async def test_pricing_unit_missing_from_the_project_is_returned_as_pending(
    patched_backends: None,
    calls: SimpleNamespace,
    fake_rut_client: SimpleNamespace,
) -> None:
    node_ids = [uuid4(), uuid4()]
    snapshot = ProjectNodesSnapshot(
        required_resources={node_id: _resources() for node_id in node_ids},
        pricing_unit_ids={},
    )

    _, _, pending = await _generate(
        project_nodes=_project_nodes(node_ids),
        snapshot=snapshot,
        wallet_info=_wallet(),
        rut_client=fake_rut_client,
    )

    # the default pricing unit is looked up once for the service, not once per node
    assert calls.default_pricing == [ServiceKeyVersion(key=_CPU_SERVICE_KEY, version=_SERVICE_VERSION)]
    # and returned to be attached by the caller, in its write transaction
    assert set(pending.pricing_unit_ids) == set(node_ids)


async def test_clusters_keeper_failure_raises_before_returning_any_write(
    monkeypatch: pytest.MonkeyPatch,
    patched_backends: None,
    fake_rut_client: SimpleNamespace,
) -> None:
    async def raising(_rpc_client, *, instance_type_names):
        raise RPCServerError(message="clusters-keeper is down", routing_key="clusters-keeper")

    monkeypatch.setattr(_utils, "get_instance_type_details", raising)

    with pytest.raises(_utils.ClustersKeeperNotAvailableError):
        await _generate(
            project_nodes=_project_nodes([uuid4()]),
            snapshot=ProjectNodesSnapshot(required_resources={}, pricing_unit_ids={uuid4(): (1, 2)}),
            wallet_info=_wallet(),
            rut_client=fake_rut_client,
        )


async def test_unknown_ec2_instance_type_raises(
    monkeypatch: pytest.MonkeyPatch,
    patched_backends: None,
    fake_rut_client: SimpleNamespace,
) -> None:
    async def returns_nothing(_rpc_client, *, instance_type_names):
        return []

    monkeypatch.setattr(_utils, "get_instance_type_details", returns_nothing)

    with pytest.raises(_utils.EC2InstanceTypeNotFoundError):
        await _generate(
            project_nodes=_project_nodes([uuid4()]),
            snapshot=ProjectNodesSnapshot(required_resources={}, pricing_unit_ids={}),
            wallet_info=_wallet(),
            rut_client=fake_rut_client,
        )


async def test_no_pricing_call_without_a_wallet(
    patched_backends: None,
    calls: SimpleNamespace,
    fake_rut_client: SimpleNamespace,
) -> None:
    """a project without wallet must not reach the resource-usage-tracker nor clusters-keeper"""
    tasks, _, pending = await _generate(
        project_nodes=_project_nodes([uuid4()]),
        snapshot=ProjectNodesSnapshot(required_resources={}, pricing_unit_ids={}),
        wallet_info=None,
        rut_client=fake_rut_client,
    )

    assert len(tasks) == 1
    assert calls.default_pricing == []
    assert calls.pricing_units == []
    assert calls.ec2_lookups == []
    assert pending.required_resources == {}
    assert pending.pricing_unit_ids == {}


async def test_gather_helpers_are_no_ops_without_anything_to_fetch() -> None:
    assert (
        await _utils._gather_default_pricing_unit_ids(SimpleNamespace(), product_name=_PRODUCT_NAME, missing=[]) == {}
    )
    assert await _utils._gather_pricing_units(SimpleNamespace(), product_name=_PRODUCT_NAME, pricing_unit_ids=[]) == {}
    assert await _utils._gather_ec2_instance_types(None, instance_type_names=set()) == {}

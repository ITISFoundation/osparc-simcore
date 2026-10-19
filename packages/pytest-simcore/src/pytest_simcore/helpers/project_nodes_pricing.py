"""Helpers to characterize the pricing/resources state of project nodes in the DB.

These helpers are shared by the web-server and director-v2 tests that pin the
*state of the tables* (not the code that produces it):

- ``projects_nodes.required_resources``
- ``projects_node_to_pricing_unit``

All expected CPU/RAM values used with these helpers are HAND-COMPUTED (written as
literals in the tests) from the fixed EC2 instance types below, using:

- dask worker formula (``dask_task_models_library.resource_constraints``):
  ``cpu = max(0.1, cpus - 0.1)``, ``ram = int(ram * 0.9)``
- dynamic-sidecar formula (``servicelib.docker_utils``):
  ``cpu = max(0.5, cpus - 1.4)``, ``ram = int(ram - 0.1 * ram - 1 GiB)``

For the two fixed EC2 types this gives:

=====================  =========================  ==========================
EC2 type               dask (cpu, ram bytes)      dynamic (cpu, ram bytes)
=====================  =========================  ==========================
``t3.medium``          1.9,  3865470566           0.6,  2791728742
``r5.4xlarge``         15.9, 123695058124         14.6, 122621316300
=====================  =========================  ==========================
"""

import re
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.api_schemas_resource_usage_tracker.pricing_plans import (
    RutPricingUnitGet,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.resource_tracker import HardwareInfo
from pydantic import ByteSize
from simcore_postgres_database.models.projects_node_to_pricing_unit import (
    projects_node_to_pricing_unit,
)
from simcore_postgres_database.models.projects_nodes import projects_nodes
from sqlalchemy.ext.asyncio import AsyncEngine

# ---------------------------------------------------------------------------
# Fixed EC2 instance types (never random: expected values are literals)
# ---------------------------------------------------------------------------

T3_MEDIUM_NAME: str = "t3.medium"  # used as the DEFAULT pricing unit machine
T3_MEDIUM_CPUS: float = 2.0
T3_MEDIUM_RAM_BYTES: int = 4 * 1024**3  # 4 GiB

R5_4XLARGE_NAME: str = "r5.4xlarge"  # used as a NON-DEFAULT pricing unit machine
R5_4XLARGE_CPUS: float = 16.0
R5_4XLARGE_RAM_BYTES: int = 128 * 1024**3  # 128 GiB

_EC2_REGISTRY: dict[str, EC2InstanceTypeGet] = {
    T3_MEDIUM_NAME: EC2InstanceTypeGet(name=T3_MEDIUM_NAME, cpus=T3_MEDIUM_CPUS, ram=ByteSize(T3_MEDIUM_RAM_BYTES)),
    R5_4XLARGE_NAME: EC2InstanceTypeGet(name=R5_4XLARGE_NAME, cpus=R5_4XLARGE_CPUS, ram=ByteSize(R5_4XLARGE_RAM_BYTES)),
}


def get_fixed_ec2_instance_types(instance_type_names: set[str]) -> list[EC2InstanceTypeGet]:
    """Stand-in for clusters-keeper ``get_instance_type_details`` with fixed specs."""
    missing = instance_type_names - _EC2_REGISTRY.keys()
    assert not missing, f"unknown EC2 types in test: {missing}"
    return [_EC2_REGISTRY[name] for name in sorted(instance_type_names)]


def make_pricing_unit(*, pricing_unit_id: int, default: bool, aws_ec2_instance: str) -> RutPricingUnitGet:
    """A pricing unit whose hardware is exactly one of the fixed EC2 types."""
    assert aws_ec2_instance in _EC2_REGISTRY
    base = RutPricingUnitGet.model_validate(
        RutPricingUnitGet.model_config["json_schema_extra"]["examples"][0]  # type: ignore[literal-required]
    )
    return base.model_copy(
        update={
            "pricing_unit_id": pricing_unit_id,
            "default": default,
            "specific_info": HardwareInfo(aws_ec2_instances=[aws_ec2_instance]),
        }
    )


def ec2_type_name_in_pricing_unit_payload(pricing_unit: RutPricingUnitGet) -> str:
    return pricing_unit.specific_info.aws_ec2_instances[0]


def regex_for_rut_pricing_unit(base_url: str, pricing_plan_id: int, pricing_unit_id: int) -> re.Pattern:
    return re.compile(
        rf"^{re.escape(base_url)}/pricing-plans/{pricing_plan_id}/pricing-units/{pricing_unit_id}([?/].*)?$"
    )


# ---------------------------------------------------------------------------
# Hand-computed expected resources, as they appear in required_resources
# ---------------------------------------------------------------------------


def single_container_required_resources(
    image: str, *, cpu: float = 0.1, ram_bytes: int = 2 * 1024**3
) -> dict[str, Any]:
    """A valid single-container ``required_resources`` payload, used to make the
    sizing outcome of a test fully deterministic (independent of whatever the
    mocked catalog returns as service default resources).
    """
    return {
        "container": {
            "image": image,
            "resources": {
                "CPU": {"limit": cpu, "reservation": cpu},
                "RAM": {"limit": ram_bytes, "reservation": ram_bytes},
            },
            "boot_modes": ["CPU"],
        }
    }


def resources_limits(cpu: float, ram_bytes: int) -> dict[str, Any]:
    """The `resources` mapping (limits and reservations) that both the dask-worker
    and the dynamic-sidecar sizing write into `required_resources[service_name]`,
    for a machine of `cpu`/`ram_bytes`.

    The two formulas DIFFER in the numbers they compute from the EC2 specs, not in
    this shape — pass the hand-computed numbers, never the raw EC2 specs.
    """
    return {
        "CPU": {"limit": cpu, "reservation": cpu},
        "RAM": {"limit": ram_bytes, "reservation": ram_bytes},
    }


# ---------------------------------------------------------------------------
# DB state readers / writers (used to SET UP a scenario and to ASSERT its outcome)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodePricingState:
    """The persisted pricing state of a single project node."""

    pricing_plan_id: int | None
    pricing_unit_id: int | None
    required_resources: dict[str, Any] | None


async def get_node_pricing_state(engine: AsyncEngine, project_uuid: ProjectID | str) -> dict[NodeID, NodePricingState]:
    """Reads, per node, the `projects_node_to_pricing_unit` link (if any) and
    `projects_nodes.required_resources`."""
    stmt = (
        sa.select(
            projects_nodes.c.node_id,
            projects_node_to_pricing_unit.c.pricing_plan_id,
            projects_node_to_pricing_unit.c.pricing_unit_id,
            projects_nodes.c.required_resources,
        )
        .select_from(
            projects_nodes.outerjoin(
                projects_node_to_pricing_unit,
                projects_nodes.c.project_node_id == projects_node_to_pricing_unit.c.project_node_id,
            )
        )
        .where(projects_nodes.c.project_uuid == f"{project_uuid}")
    )
    async with engine.connect() as conn:
        result = await conn.execute(stmt)
        return {
            NodeID(row.node_id): NodePricingState(
                pricing_plan_id=row.pricing_plan_id,
                pricing_unit_id=row.pricing_unit_id,
                required_resources=row.required_resources,
            )
            for row in result
        }


async def set_node_pricing_link(
    engine: AsyncEngine,
    project_uuid: ProjectID | str,
    node_id: NodeID | str,
    *,
    pricing_plan_id: int,
    pricing_unit_id: int,
) -> None:
    """Directly creates a `projects_node_to_pricing_unit` link for a node.

    Used to set up scenarios that the endpoints cannot (yet) produce, e.g. a
    computational node linked to a non-default pricing unit WITHOUT resizing.
    """
    async with engine.begin() as conn:
        node_row_id = (
            await conn.execute(
                sa.select(projects_nodes.c.project_node_id)
                .where(projects_nodes.c.project_uuid == f"{project_uuid}")
                .where(projects_nodes.c.node_id == f"{node_id}")
            )
        ).scalar_one()
        await conn.execute(
            sa.insert(projects_node_to_pricing_unit).values(
                project_node_id=node_row_id,
                pricing_plan_id=pricing_plan_id,
                pricing_unit_id=pricing_unit_id,
            )
        )


async def set_node_required_resources(
    engine: AsyncEngine,
    project_uuid: ProjectID | str,
    node_id: NodeID | str,
    required_resources: dict[str, Any],
) -> None:
    """Directly overwrites `projects_nodes.required_resources` for a node."""
    async with engine.begin() as conn:
        result = await conn.execute(
            sa.update(projects_nodes)
            .where(projects_nodes.c.project_uuid == f"{project_uuid}")
            .where(projects_nodes.c.node_id == f"{node_id}")
            .values(required_resources=required_resources)
        )
        assert result.rowcount == 1, f"node {node_id} not found in project {project_uuid}"

"""Shared command-level helpers to reduce duplication across CLI commands."""

from . import analysis, ec2
from .models import (
    AppState,
    ComputationalCluster,
    DynamicInstance,
)


def collect_services(
    instances: list[DynamicInstance],
) -> list[tuple[int, str, str]]:
    """Collect (user_id, project_id, node_id) for all running services."""
    return [(svc.user_id, svc.project_id, svc.node_id) for inst in instances for svc in inst.running_services]


async def load_dynamic_instances(
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
    instance_id: str | None,
) -> list[DynamicInstance]:
    """List EC2 dynamic instances and parse/analyze them in one step."""
    instances = await ec2.list_dynamic_instances_from_ec2(
        state,
        filter_by_user_id=user_id,
        filter_by_wallet_id=wallet_id,
        filter_by_instance_id=instance_id,
    )
    return await analysis.parse_dynamic_instances(state, instances, state.ssh_key_path, user_id, wallet_id)


async def load_computational_clusters(
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
) -> list[ComputationalCluster]:
    """List EC2 computational instances and parse/analyze them in one step."""
    instances = await ec2.list_computational_instances_from_ec2(state, user_id, wallet_id)
    return await analysis.parse_computational_clusters(state, instances, state.ssh_key_path, user_id, wallet_id)

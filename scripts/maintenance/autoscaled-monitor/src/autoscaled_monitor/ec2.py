from datetime import timedelta
from typing import Any, Final

import boto3
import orjson
import rich
from aiocache import cached
from mypy_boto3_ec2 import EC2ServiceResource
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from mypy_boto3_ec2.type_defs import FilterTypeDef
from pydantic import TypeAdapter

from .models import AppState
from .utils import get_instance_name, to_async


@to_async
def _list_running_ec2_instances(
    ec2_resource: EC2ServiceResource,
    key_name: str,
    custom_tags: dict[str, str],
    user_id: int | None,
    wallet_id: int | None,
    instance_id: str | None,
) -> ServiceResourceInstancesCollection:
    # get all the running instances

    ec2_filters: list[FilterTypeDef] = [
        {"Name": "instance-state-name", "Values": ["running", "pending"]},
        {"Name": "key-name", "Values": [key_name]},
    ]
    if custom_tags:
        ec2_filters.extend([{"Name": f"tag:{key}", "Values": [f"{value}"]} for key, value in custom_tags.items()])

    if user_id:
        ec2_filters.append({"Name": "tag:user_id", "Values": [f"{user_id}"]})
    if wallet_id:
        ec2_filters.append({"Name": "tag:wallet_id", "Values": [f"{wallet_id}"]})
    if instance_id:
        ec2_filters.append({"Name": "instance-id", "Values": [f"{instance_id}"]})
    return ec2_resource.instances.filter(Filters=ec2_filters)


async def list_computational_instances_from_ec2(
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
) -> ServiceResourceInstancesCollection:
    assert state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"]
    assert state.environment["WORKERS_EC2_INSTANCES_KEY_NAME"]
    assert state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"] == state.environment["WORKERS_EC2_INSTANCES_KEY_NAME"], (
        "key name is different on primary and workers. TIP: adjust this code now"
    )
    custom_tags = {}
    if state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"]:
        assert (
            state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"]
            == state.environment["WORKERS_EC2_INSTANCES_CUSTOM_TAGS"]
        ), "custom tags are different on primary and workers. TIP: adjust this code now"
        custom_tags = orjson.loads(state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"])
    assert state.ec2_resource_clusters_keeper
    return await _list_running_ec2_instances(
        state.ec2_resource_clusters_keeper,
        state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"],
        custom_tags,
        user_id,
        wallet_id,
        None,
    )


async def list_dynamic_instances_from_ec2(
    state: AppState,
    *,
    filter_by_user_id: int | None,
    filter_by_wallet_id: int | None,
    filter_by_instance_id: str | None,
) -> ServiceResourceInstancesCollection:
    assert state.environment["EC2_INSTANCES_KEY_NAME"]
    custom_tags = {}
    if state.environment["EC2_INSTANCES_CUSTOM_TAGS"]:
        custom_tags = orjson.loads(state.environment["EC2_INSTANCES_CUSTOM_TAGS"])
    assert state.ec2_resource_autoscaling
    return await _list_running_ec2_instances(
        state.ec2_resource_autoscaling,
        state.environment["EC2_INSTANCES_KEY_NAME"],
        custom_tags,
        filter_by_user_id,
        filter_by_wallet_id,
        filter_by_instance_id,
    )


_DEFAULT_BASTION_NAME: Final[str] = "bastion-host"


async def _get_bastion_instance(
    ec2_resource: EC2ServiceResource,
    key_name: str,
) -> Instance:
    instances = await _list_running_ec2_instances(
        ec2_resource,
        key_name,
        {},
        None,
        None,
        None,
    )
    possible_bastions = list(filter(lambda i: _DEFAULT_BASTION_NAME in get_instance_name(i), instances))
    assert len(possible_bastions) == 1
    return possible_bastions[0]


@cached()
async def get_computational_bastion_instance(state: AppState) -> Instance:
    assert state.ec2_resource_clusters_keeper  # nosec
    assert state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"]  # nosec
    return await _get_bastion_instance(
        state.ec2_resource_clusters_keeper,
        state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"],
    )


@cached()
async def get_dynamic_bastion_instance(state: AppState) -> Instance:
    assert state.ec2_resource_autoscaling  # nosec
    assert state.environment["EC2_INSTANCES_KEY_NAME"]  # nosec
    return await _get_bastion_instance(
        state.ec2_resource_autoscaling,
        state.environment["EC2_INSTANCES_KEY_NAME"],
    )


def cluster_keeper_region(state: AppState) -> str:
    assert state.environment["CLUSTERS_KEEPER_EC2_REGION_NAME"]  # nosec
    return state.environment["CLUSTERS_KEEPER_EC2_REGION_NAME"]


def autoscaling_region(state: AppState) -> str:
    assert state.environment["AUTOSCALING_EC2_REGION_NAME"]  # nosec
    return state.environment["AUTOSCALING_EC2_REGION_NAME"]


async def get_bastion_instance_from_remote_instance(state: AppState, remote_instance: Instance) -> Instance:
    availability_zone = remote_instance.placement["AvailabilityZone"]
    if cluster_keeper_region(state) in availability_zone:
        return await get_computational_bastion_instance(state)
    if autoscaling_region(state) in availability_zone:
        return await get_dynamic_bastion_instance(state)
    msg = "no corresponding bastion instance!"
    raise RuntimeError(msg)


def cluster_keeper_ec2_client(state: AppState) -> EC2ServiceResource:
    return boto3.resource(
        "ec2",
        region_name=cluster_keeper_region(state),
        aws_access_key_id=state.environment["CLUSTERS_KEEPER_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=state.environment["CLUSTERS_KEEPER_EC2_SECRET_ACCESS_KEY"],
    )


def autoscaling_ec2_client(state: AppState) -> EC2ServiceResource:
    return boto3.resource(
        "ec2",
        region_name=autoscaling_region(state),
        aws_access_key_id=state.environment["AUTOSCALING_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=state.environment["AUTOSCALING_EC2_SECRET_ACCESS_KEY"],
    )


# Cache per instance type string to avoid repeated API calls
_instance_type_cache: dict[str, dict[str, Any]] = {}


@cached()
@to_async
def _describe_instance_type(ec2_resource: EC2ServiceResource, instance_type: str) -> dict[str, Any]:
    if instance_type in _instance_type_cache:
        return _instance_type_cache[instance_type]
    client = ec2_resource.meta.client
    response = client.describe_instance_types(InstanceTypes=[instance_type])
    info: dict[str, Any] = {}
    if response["InstanceTypes"]:
        it = response["InstanceTypes"][0]
        info["vcpus"] = it.get("VCpuInfo", {}).get("DefaultVCpus", 0)
        info["ram_mib"] = it.get("MemoryInfo", {}).get("SizeInMiB", 0)
        gpu_info = it.get("GpuInfo", {})
        gpus = gpu_info.get("Gpus", [])
        info["gpu_count"] = sum(g.get("Count", 0) for g in gpus)
        info["gpu_vram_mib"] = sum(g.get("MemoryInfo", {}).get("SizeInMiB", 0) * g.get("Count", 1) for g in gpus)
    _instance_type_cache[instance_type] = info
    return info


async def get_instance_type_info(ec2_resource: EC2ServiceResource, instance_type: str) -> dict[str, Any]:
    return await _describe_instance_type(ec2_resource, instance_type)


def get_clusters_keeper_task_interval(state: AppState) -> timedelta:
    """Parse CLUSTERS_KEEPER_TASK_INTERVAL from environment and return as timedelta."""
    task_interval_str = state.environment.get("CLUSTERS_KEEPER_TASK_INTERVAL", "30")
    return TypeAdapter(timedelta).validate_python(task_interval_str)


@to_async
def _check_cluster_instances_exist(
    ec2_resource: EC2ServiceResource,
    key_name: str,
    custom_tags: dict[str, str],
    user_id: int,
    wallet_id: int | None,
    original_primary_id: str,
    original_worker_ids: set[str],
) -> bool:
    """
    Check if the original cluster instances still exist in EC2.

    Returns True if any of the original instances are still in running/pending state.
    """
    ec2_filters: list[FilterTypeDef] = [
        {"Name": "instance-state-name", "Values": ["running", "pending"]},
        {"Name": "key-name", "Values": [key_name]},
    ]
    if custom_tags:
        ec2_filters.extend([{"Name": f"tag:{key}", "Values": [f"{value}"]} for key, value in custom_tags.items()])
    ec2_filters.append({"Name": "tag:user_id", "Values": [f"{user_id}"]})
    if wallet_id:
        ec2_filters.append({"Name": "tag:wallet_id", "Values": [f"{wallet_id}"]})

    instances = ec2_resource.instances.filter(Filters=ec2_filters)
    running_ids = {inst.id for inst in instances}

    # Check if original primary or any workers are still running
    return original_primary_id in running_ids or bool(original_worker_ids & running_ids)


async def cluster_is_running(
    state: AppState,
    user_id: int,
    wallet_id: int | None,
    original_primary_instance_id: str,
    original_worker_instance_ids: set[str],
) -> bool:
    """Check if the original cluster instances still exist in EC2."""
    assert state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"]
    custom_tags = {}
    if state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"]:
        custom_tags = orjson.loads(state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"])
    assert state.ec2_resource_clusters_keeper

    return await _check_cluster_instances_exist(
        state.ec2_resource_clusters_keeper,
        state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"],
        custom_tags,
        user_id,
        wallet_id,
        original_primary_instance_id,
        original_worker_instance_ids,
    )


@to_async
def _terminate_instances_by_ids(ec2_resource: EC2ServiceResource, instance_ids: list[str]) -> None:
    instances_by_id = {inst.id: inst for inst in ec2_resource.instances.filter(InstanceIds=instance_ids)}
    if not instances_by_id:
        rich.print("[yellow]No matching instances found in EC2 for forceful termination.[/yellow]")
        return

    terminateable_ids: list[str] = []
    for instance_id in instance_ids:
        instance = instances_by_id.get(instance_id)
        if instance is None:
            rich.print(f"[yellow]Instance {instance_id} not found, skipping[/yellow]")
            continue

        state_name = instance.state["Name"]
        if state_name in ("running", "pending", "stopping", "stopped"):
            rich.print(f"Terminating instance {instance.id} ({get_instance_name(instance)})")
            terminateable_ids.append(instance.id)
        else:
            rich.print(f"Instance {instance.id} already {state_name}, skipping")

    if not terminateable_ids:
        rich.print("[yellow]No instances in a terminateable state.[/yellow]")
        return

    ec2_resource.meta.client.terminate_instances(InstanceIds=terminateable_ids)


async def terminate_cluster_instances_forcefully(
    ec2_resource: EC2ServiceResource,
    primary_instance_id: str,
    worker_instance_ids: set[str],
) -> None:
    rich.print("\n[bold yellow]Initiating direct EC2 termination as fallback...[/bold yellow]")
    instance_ids = [primary_instance_id, *sorted(worker_instance_ids)]
    await _terminate_instances_by_ids(ec2_resource, instance_ids)
    rich.print("[green]Direct EC2 termination initiated.[/green]")

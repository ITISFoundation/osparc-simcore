#! /usr/bin/env python3

import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import arrow
import boto3
import parse
import typer
from dotenv import dotenv_values
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from rich import print
from rich.table import Column, Table

app = typer.Typer()


@dataclass(frozen=True, slots=True, kw_only=True)
class AutoscaledInstance:
    name: str
    ec2_instance: Instance


class InstanceRole(str, Enum):
    manager = "manager"
    worker = "worker"


@dataclass(frozen=True, slots=True, kw_only=True)
class ComputationalInstance(AutoscaledInstance):
    role: InstanceRole
    user_id: int
    wallet_id: int
    last_heartbeat: datetime.datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class DynamicInstance(AutoscaledInstance):
    ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ComputationalCluster:
    primary: ComputationalInstance
    workers: list[ComputationalInstance]


def _get_instance_name(instance) -> str:
    for tag in instance.tags:
        if tag["Key"] == "Name":
            return tag["Value"]
    return "unknown"


def _get_last_heartbeat(instance) -> datetime.datetime | None:
    for tag in instance.tags:
        if tag["Key"] == "last_heartbeat":
            return arrow.get(tag["Value"]).datetime
    return None


def _timedelta_formatting(time_diff: datetime.timedelta) -> str:
    formatted_time_diff = f"{time_diff.days} days, " if time_diff.days else ""
    formatted_time_diff += f"{time_diff.seconds // 3600:02}:{(time_diff.seconds // 60) % 60:02}:{time_diff.seconds % 60:02}"
    return formatted_time_diff


computational_parser = parse.compile(
    "osparc-computational-cluster-{role}-{swarm_stack_name}-user_id:{user_id:d}-wallet_id:{wallet_id:d}"
)


def _parse_computational(instance: Instance) -> ComputationalInstance | None:
    name = _get_instance_name(instance)
    if result := computational_parser.search(name):
        assert isinstance(result, parse.Result)
        last_heartbeat = _get_last_heartbeat(instance)
        return ComputationalInstance(
            role=InstanceRole(result["role"]),
            user_id=result["user_id"],
            wallet_id=result["wallet_id"],
            name=name,
            last_heartbeat=last_heartbeat,
            ec2_instance=instance,
        )

    return None


dynamic_parser = parse.compile("osparc-dynamic-autoscaled-worker-{key_name}")


def _parse_dynamic(instance: Instance) -> DynamicInstance | None:
    name = _get_instance_name(instance)
    if result := dynamic_parser.search(name):
        assert isinstance(result, parse.Result)
        return DynamicInstance(name=name, ec2_instance=instance)
    return None


def _print_dynamic_instances(instances: list[DynamicInstance]) -> None:
    time_now = arrow.utcnow()
    table = Table(
        "Instance",
        Column("Type", justify="right"),
        Column("publicIP", justify="right"),
        Column("privateIP", justify="right"),
        "Name",
        Column("Created since", justify="right"),
        "State",
        title="dynamic autoscaled instances",
    )
    for instance in instances:
        instance_state = (
            f"[green]{instance.ec2_instance.state['Name']}[/green]"
            if instance.ec2_instance.state["Name"] == "running"
            else f"[yellow]{instance.ec2_instance.state['Name']}[/yellow]"
        )
        table.add_row(
            instance.ec2_instance.id,
            instance.ec2_instance.instance_type,
            instance.ec2_instance.public_ip_address,
            instance.ec2_instance.private_ip_address,
            instance.name,
            _timedelta_formatting(
                time_now - arrow.get(instance.ec2_instance.launch_time)
            ),
            instance_state,
        )
    print(table)


def _print_computational_clusters(clusters: list[ComputationalCluster]) -> None:
    time_now = arrow.utcnow()
    table = Table(
        "Instance",
        Column("Type", justify="right"),
        Column("publicIP", justify="right"),
        Column("privateIP", justify="right"),
        "Name",
        Column("Created since", justify="right"),
        "State",
        "UserID",
        "WalletID",
        "DaskSchedulerUI",
        "last heartbeat since",
        title="computational clusters",
    )

    for cluster in clusters:
        # first print primary machine info
        instance_state = (
            f"[green]{cluster.primary.ec2_instance.state['Name']}[/green]"
            if cluster.primary.ec2_instance.state["Name"] == "running"
            else f"[yellow]{cluster.primary.ec2_instance.state['Name']}[/yellow]"
        )
        assert cluster.primary.last_heartbeat
        table.add_row(
            cluster.primary.ec2_instance.id,
            cluster.primary.ec2_instance.instance_type,
            cluster.primary.ec2_instance.public_ip_address,
            cluster.primary.ec2_instance.private_ip_address,
            cluster.primary.name,
            _timedelta_formatting(
                time_now - arrow.get(cluster.primary.ec2_instance.launch_time)
            ),
            instance_state,
            f"{cluster.primary.user_id}",
            f"{cluster.primary.wallet_id}",
            f"http://{cluster.primary.ec2_instance.public_ip_address}:8787",
            _timedelta_formatting(time_now - arrow.get(cluster.primary.last_heartbeat)),
        )
        # now add the workers
        for worker in cluster.workers:
            instance_state = (
                f"[green]{worker.ec2_instance.state['Name']}[/green]"
                if worker.ec2_instance.state["Name"] == "running"
                else f"[yellow]{worker.ec2_instance.state['Name']}[/yellow]"
            )

            table.add_row(
                worker.ec2_instance.id,
                worker.ec2_instance.instance_type,
                worker.ec2_instance.public_ip_address,
                worker.ec2_instance.private_ip_address,
                worker.name,
                _timedelta_formatting(
                    time_now - arrow.get(worker.ec2_instance.launch_time)
                ),
                instance_state,
                "",
                "",
                "",
                "",
            )
        table.add_row(end_section=True)
    print(table)


def _detect_instances(
    instances: ServiceResourceInstancesCollection,
) -> tuple[list[DynamicInstance], list[ComputationalCluster]]:
    dynamic_instances = []
    computational_instances = []
    for instance in instances:
        if comp_instance := _parse_computational(instance):
            computational_instances.append(comp_instance)
        elif dyn_instance := _parse_dynamic(instance):
            dynamic_instances.append(dyn_instance)
    computational_clusters = [
        ComputationalCluster(primary=instance, workers=[])
        for instance in computational_instances
        if instance.role is InstanceRole.manager
    ]
    for instance in computational_instances:
        if instance.role is InstanceRole.worker:
            # assign the worker to correct cluster
            for cluster in computational_clusters:
                if (
                    cluster.primary.user_id == instance.user_id
                    and cluster.primary.wallet_id == instance.wallet_id
                ):
                    cluster.workers.append(instance)

    return dynamic_instances, computational_clusters


@app.command()
def summary(repo_file: Path) -> None:
    environment = dotenv_values(repo_file)
    assert environment
    # connect to ec2
    ec2_resource = boto3.resource(
        "ec2",
        region_name=environment["AUTOSCALING_EC2_REGION_NAME"],
        aws_access_key_id=environment["AUTOSCALING_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=environment["AUTOSCALING_EC2_SECRET_ACCESS_KEY"],
    )

    # get all the running instances
    assert environment["EC2_INSTANCES_KEY_NAME"]
    instances = ec2_resource.instances.filter(
        Filters=[
            {"Name": "instance-state-name", "Values": ["running", "pending"]},
            {"Name": "key-name", "Values": [environment["EC2_INSTANCES_KEY_NAME"]]},
        ]
    )

    dynamic_autoscaled_instances, computational_clusters = _detect_instances(instances)

    _print_dynamic_instances(dynamic_autoscaled_instances)
    _print_computational_clusters(computational_clusters)


if __name__ == "__main__":
    app()

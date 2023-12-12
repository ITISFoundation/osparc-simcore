#! /usr/bin/env python3

import asyncio
import datetime
import json
import re
from collections import defaultdict, namedtuple
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Final

import arrow
import boto3
import paramiko
import parse
import typer
from dotenv import dotenv_values
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from rich import print  # pylint: disable=redefined-builtin
from rich.progress import track
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


@dataclass
class DynamicService:
    node_id: str
    user_id: int
    project_id: str
    service_name: str
    service_version: str
    created_at: datetime.datetime
    needs_manual_intervention: bool
    containers: list[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class DynamicInstance(AutoscaledInstance):
    running_services: list[DynamicService]


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
    formatted_time_diff = f"{time_diff.days} day(s), " if time_diff.days else ""
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

        return DynamicInstance(name=name, ec2_instance=instance, running_services=[])
    return None


# NOTE: service_name and service_version are not available on dynamic-sidecar/dynamic-proxies!
_DYN_SERVICES_NAMING_CONVENTION: Final[re.Pattern] = re.compile(
    r"^dy-(proxy|sidecar)(-|_)(?P<node_id>.{8}-.{4}-.{4}-.{4}-.{12}).*\t(?P<created_at>[^\t]+)\t(?P<user_id>\d+)\t(?P<project_id>.{8}-.{4}-.{4}-.{4}-.{12})\t(?P<service_name>[^\t]*)\t(?P<service_version>.*)$"
)

DockerContainer = namedtuple(  # noqa: PYI024
    "docker_container",
    [
        "node_id",
        "user_id",
        "project_id",
        "created_at",
        "name",
        "service_name",
        "service_version",
    ],
)


def _ssh_and_list_running_dyn_services(
    instance: Instance, username: str, private_key_path: Path
) -> list[DynamicService]:
    # Establish SSH connection with key-based authentication
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            instance.public_ip_address,
            username=username,
            key_filename=f"{private_key_path}",
        )
        # Run the Docker command to list containers
        _stdin, stdout, stderr = client.exec_command(
            'docker ps --format=\'{{.Names}}\t{{.CreatedAt}}\t{{.Label "io.simcore.runtime.user-id"}}\t{{.Label "io.simcore.runtime.project-id"}}\t{{.Label "io.simcore.name"}}\t{{.Label "io.simcore.version"}}\' --filter=name=dy-',
        )
        error = stderr.read().decode()
        if error:
            print(error)
            raise typer.Abort(error)

        output = stdout.read().decode("utf-8")
        # Extract containers that follow the naming convention
        running_service: dict[str, list[DockerContainer]] = defaultdict(list)
        for container in output.splitlines():
            if match := re.match(_DYN_SERVICES_NAMING_CONVENTION, container):
                named_container = DockerContainer(
                    match["node_id"],
                    int(match["user_id"]),
                    match["project_id"],
                    arrow.get(
                        match["created_at"],
                        "YYYY-MM-DD HH:mm:ss",
                        tzinfo=datetime.timezone.utc,
                    ).datetime,
                    container,
                    json.loads(match["service_name"])["name"]
                    if match["service_name"]
                    else "",
                    json.loads(match["service_version"])["version"]
                    if match["service_version"]
                    else "",
                )
                running_service[match["node_id"]].append(named_container)

        def _needs_manual_intervention(
            running_containers: list[DockerContainer],
        ) -> bool:
            valid_prefixes = ["dy-sidecar_", "dy-proxy_", "dy-sidecar-"]
            for prefix in valid_prefixes:
                found = any(
                    container.name.startswith(prefix)
                    for container in running_containers
                )
                if not found:
                    return True
            return False

        return [
            DynamicService(
                node_id=node_id,
                user_id=containers[0].user_id,
                project_id=containers[0].project_id,
                created_at=containers[0].created_at,
                needs_manual_intervention=_needs_manual_intervention(containers),
                containers=[c.name for c in containers],
                service_name=containers[0].service_name,
                service_version=containers[0].service_version,
            )
            for node_id, containers in running_service.items()
        ]
    except (paramiko.AuthenticationException, paramiko.SSHException) as exc:
        raise typer.Abort from exc
    finally:
        # Close the SSH connection
        client.close()


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
        Column("Running services", footer="(need ssh access)"),
        title="dynamic autoscaled instances",
    )
    for instance in track(
        instances, description="Preparing dynamic autoscaled instances details..."
    ):
        instance_state = (
            f"[green]{instance.ec2_instance.state['Name']}[/green]"
            if instance.ec2_instance.state["Name"] == "running"
            else f"[yellow]{instance.ec2_instance.state['Name']}[/yellow]"
        )
        service_table = "n/a"
        if instance.running_services:
            service_table = Table(
                "UserID",
                "ProjectID",
                "NodeID",
                "ServiceName",
                "ServiceVersion",
                "Created Since",
                "Need intervention",
            )
            for service in instance.running_services:
                service_table.add_row(
                    f"{service.user_id}",
                    service.project_id,
                    service.node_id,
                    service.service_name,
                    service.service_version,
                    _timedelta_formatting(time_now - service.created_at),
                    f"{service.needs_manual_intervention}",
                )

        table.add_row(
            instance.ec2_instance.id,
            f"{instance.ec2_instance.instance_type}",
            instance.ec2_instance.public_ip_address,
            instance.ec2_instance.private_ip_address,
            instance.name,
            _timedelta_formatting(time_now - instance.ec2_instance.launch_time),
            instance_state,
            service_table,
            end_section=True,
        )
    print(table, flush=True)


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

    for cluster in track(
        clusters, "Collecting information about computational clusters..."
    ):
        # first print primary machine info
        instance_state = (
            f"[green]{cluster.primary.ec2_instance.state['Name']}[/green]"
            if cluster.primary.ec2_instance.state["Name"] == "running"
            else f"[yellow]{cluster.primary.ec2_instance.state['Name']}[/yellow]"
        )
        assert cluster.primary.last_heartbeat
        table.add_row(
            cluster.primary.ec2_instance.id,
            f"{cluster.primary.ec2_instance.instance_type}",
            cluster.primary.ec2_instance.public_ip_address,
            cluster.primary.ec2_instance.private_ip_address,
            cluster.primary.name,
            _timedelta_formatting(time_now - cluster.primary.ec2_instance.launch_time),
            instance_state,
            f"{cluster.primary.user_id}",
            f"{cluster.primary.wallet_id}",
            f"http://{cluster.primary.ec2_instance.public_ip_address}:8787",
            _timedelta_formatting(time_now - cluster.primary.last_heartbeat),
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
                f"{worker.ec2_instance.instance_type}",
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
    instances: ServiceResourceInstancesCollection, ssh_key_path: Path | None
) -> tuple[list[DynamicInstance], list[ComputationalCluster]]:
    dynamic_instances = []
    computational_instances = []

    for instance in track(instances, description="Detecting running instances..."):
        if comp_instance := _parse_computational(instance):
            computational_instances.append(comp_instance)
        elif dyn_instance := _parse_dynamic(instance):
            dynamic_instances.append(dyn_instance)

    if ssh_key_path:
        # this construction makes the retrieval much faster
        all_running_services = asyncio.get_event_loop().run_until_complete(
            asyncio.gather(
                *(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        _ssh_and_list_running_dyn_services,
                        instance.ec2_instance,
                        "ubuntu",
                        ssh_key_path,
                    )
                    for instance in dynamic_instances
                )
            )
        )

        more_detailed_instances = [
            replace(
                instance,
                running_services=running_services,
            )
            for instance, running_services in zip(
                dynamic_instances, all_running_services, strict=True
            )
        ]
        dynamic_instances = more_detailed_instances

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
def summary(repo_file: Path, ssh_key_path: Path | None = None) -> None:
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

    global dynamic_parser
    dynamic_parser = parse.compile(
        f"{environment['EC2_INSTANCES_NAME_PREFIX']}-{{key_name}}"
    )

    dynamic_autoscaled_instances, computational_clusters = _detect_instances(
        instances, ssh_key_path
    )

    _print_dynamic_instances(dynamic_autoscaled_instances)
    _print_computational_clusters(computational_clusters)


if __name__ == "__main__":
    app()

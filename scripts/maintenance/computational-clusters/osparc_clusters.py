#! /usr/bin/env python3

import asyncio
import contextlib
import datetime
import json
import re
from collections import defaultdict, namedtuple
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Final, TypeAlias

import arrow
import boto3
import distributed
import paramiko
import parse
import typer
from dotenv import dotenv_values
from mypy_boto3_ec2 import EC2ServiceResource
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from pydantic import ByteSize, TypeAdapter
from rich import print  # pylint: disable=redefined-builtin
from rich.progress import track
from rich.table import Column, Style, Table

app = typer.Typer()

_SSH_USER_NAME: Final[str] = "ubuntu"


@dataclass(slots=True, kw_only=True)
class AutoscaledInstance:
    name: str
    ec2_instance: Instance
    disk_space: ByteSize


class InstanceRole(str, Enum):
    manager = "manager"
    worker = "worker"


@dataclass(slots=True, kw_only=True)
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


@dataclass(slots=True, kw_only=True)
class DynamicInstance(AutoscaledInstance):
    running_services: list[DynamicService]


TaskId: TypeAlias = str
TaskState: TypeAlias = str

MINUTE: Final[int] = 60
HOUR: Final[int] = 60 * MINUTE

COMPUTATIONAL_INSTANCE_NAME_PARSER: Final[parse.Parser] = parse.compile(
    r"osparc-computational-cluster-{role}-{swarm_stack_name}-user_id:{user_id:d}-wallet_id:{wallet_id:d}"
)

DEPLOY_SSH_KEY_PARSER: Final[parse.Parser] = parse.compile(r"osparc-{random_name}.pem")


@dataclass(frozen=True, slots=True, kw_only=True)
class ComputationalCluster:
    primary: ComputationalInstance
    workers: list[ComputationalInstance]

    scheduler_info: dict[str, Any]
    datasets: tuple[str, ...]
    processing_jobs: dict[str, str]
    task_states_to_tasks: dict[TaskId, list[TaskState]]


def _get_instance_name(instance) -> str:
    for tag in instance.tags:
        if tag["Key"] == "Name":
            return tag.get("Value", "unknown")
    return "unknown"


def _get_last_heartbeat(instance) -> datetime.datetime | None:
    for tag in instance.tags:
        if tag["Key"] == "last_heartbeat":
            return arrow.get(tag["Value"]).datetime
    return None


def _timedelta_formatting(
    time_diff: datetime.timedelta, *, color_code: bool = False
) -> str:
    formatted_time_diff = f"{time_diff.days} day(s), " if time_diff.days else ""
    formatted_time_diff += f"{time_diff.seconds // 3600:02}:{(time_diff.seconds // 60) % 60:02}:{time_diff.seconds % 60:02}"
    if time_diff.days and color_code:
        formatted_time_diff = f"[red]{formatted_time_diff}[/red]"
    elif time_diff.seconds > 5 * HOUR and color_code:
        formatted_time_diff = f"[orange]{formatted_time_diff}[/orange]"
    return formatted_time_diff


def _parse_computational(instance: Instance) -> ComputationalInstance | None:
    name = _get_instance_name(instance)
    if result := COMPUTATIONAL_INSTANCE_NAME_PARSER.search(name):
        assert isinstance(result, parse.Result)
        last_heartbeat = _get_last_heartbeat(instance)
        return ComputationalInstance(
            role=InstanceRole(result["role"]),
            user_id=result["user_id"],
            wallet_id=result["wallet_id"],
            name=name,
            last_heartbeat=last_heartbeat,
            ec2_instance=instance,
            disk_space=UNDEFINED_BYTESIZE,
        )

    return None


def _create_graylog_permalinks(
    environment: dict[str, str | None], instance: Instance
) -> str:
    # https://monitoring.sim4life.io/graylog/search/6552235211aee4262e7f9f21?q=source%3A%22ip-10-0-1-67%22&rangetype=relative&from=28800
    source_name = instance.private_ip_address.replace(".", "-")
    time_span = int(
        (
            arrow.utcnow().datetime - instance.launch_time + datetime.timedelta(hours=1)
        ).total_seconds()
    )
    return f"https://monitoring.{environment['MACHINE_FQDN']}/graylog/search?q=source%3A%22ip-{source_name}%22&rangetype=relative&from={time_span}"


UNDEFINED_BYTESIZE: Final[ByteSize] = ByteSize(-1)


def _parse_dynamic(instance: Instance) -> DynamicInstance | None:
    name = _get_instance_name(instance)
    if result := state["dynamic_parser"].search(name):
        assert isinstance(result, parse.Result)

        return DynamicInstance(
            name=name,
            ec2_instance=instance,
            running_services=[],
            disk_space=UNDEFINED_BYTESIZE,
        )
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


def _ssh_and_get_available_disk_space(
    instance: Instance, username: str, private_key_path: Path
) -> ByteSize:
    # Establish SSH connection with key-based authentication
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            instance.public_ip_address,
            username=username,
            key_filename=f"{private_key_path}",
            timeout=5,
        )
        # Command to get disk space for /docker partition
        disk_space_command = "df --block-size=1 /mnt/docker | awk 'NR==2{print $4}'"

        # Run the command on the remote machine
        _stdin, stdout, stderr = client.exec_command(disk_space_command)
        error = stderr.read().decode()

        if error:
            print(error)
            raise typer.Abort(error)

        # Available disk space will be captured here
        available_space = stdout.read().decode("utf-8").strip()
        return ByteSize(available_space)
    except (
        paramiko.AuthenticationException,
        paramiko.SSHException,
        TimeoutError,
    ):
        return ByteSize(0)

    finally:
        # Close the SSH connection
        client.close()


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
            timeout=5,
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
                    (
                        json.loads(match["service_name"])["name"]
                        if match["service_name"]
                        else ""
                    ),
                    (
                        json.loads(match["service_version"])["version"]
                        if match["service_version"]
                        else ""
                    ),
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
    except (
        paramiko.AuthenticationException,
        paramiko.SSHException,
        TimeoutError,
    ):
        return []

    finally:
        # Close the SSH connection
        client.close()


def _print_dynamic_instances(
    instances: list[DynamicInstance], environment: dict[str, str | None]
) -> None:
    time_now = arrow.utcnow()
    table = Table(
        Column("Instance"),
        Column("Links", overflow="fold"),
        Column(
            "Running services",
            footer="[red]Intervention detection might show false positive if in transient state, be careful and always double-check!![/red]",
        ),
        title="dynamic autoscaled instances",
        show_footer=True,
        padding=(0, 0),
        title_style=Style(color="red", encircle=True),
    )
    for instance in track(
        instances, description="Preparing dynamic autoscaled instances details..."
    ):
        service_table = "[i]n/a[/i]"
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
                    f"{'[red]' if service.needs_manual_intervention else ''}{service.needs_manual_intervention}{'[/red]' if service.needs_manual_intervention else ''}",
                )

        table.add_row(
            "\n".join(
                [
                    f"{_color_encode_with_state(instance.name, instance.ec2_instance)}",
                    f"ID: {instance.ec2_instance.instance_id}",
                    f"AMI: {instance.ec2_instance.image_id}({instance.ec2_instance.image.name})",
                    f"Type: {instance.ec2_instance.instance_type}",
                    f"Up: {_timedelta_formatting(time_now - instance.ec2_instance.launch_time, color_code=True)}",
                    f"ExtIP: {instance.ec2_instance.public_ip_address}",
                    f"IntIP: {instance.ec2_instance.private_ip_address}",
                    f"/mnt/docker(free): {_color_encode_with_threshold(instance.disk_space.human_readable(), instance.disk_space,  TypeAdapter(ByteSize).validate_python('15Gib'))}",
                ]
            ),
            f"Graylog: {_create_graylog_permalinks(environment, instance.ec2_instance)}",
            service_table,
            end_section=True,
        )
    print(table, flush=True)


def _get_worker_metrics(scheduler_info: dict[str, Any]) -> dict[str, Any]:
    worker_metrics = {}
    for worker_name, worker_data in scheduler_info.get("workers", {}).items():
        worker_metrics[worker_name] = {
            "resources": worker_data["resources"],
            "tasks": worker_data["metrics"].get("task_counts", {}),
        }
    return worker_metrics


def _color_encode_with_state(string: str, ec2_instance: Instance) -> str:
    return (
        f"[green]{string}[/green]"
        if ec2_instance.state["Name"] == "running"
        else f"[yellow]{string}[/yellow]"
    )


DANGER = "[red]{}[/red]"


def _color_encode_with_threshold(string: str, value, threshold) -> str:
    return string if value > threshold else DANGER.format(string)


def _print_computational_clusters(
    clusters: list[ComputationalCluster], environment: dict[str, str | None]
) -> None:
    time_now = arrow.utcnow()
    table = Table(
        Column("Instance", justify="left", overflow="fold"),
        Column("Links", justify="left", overflow="fold"),
        Column("Computational details"),
        title="computational clusters",
        padding=(0, 0),
        title_style=Style(color="red", encircle=True),
    )

    for cluster in track(
        clusters, "Collecting information about computational clusters..."
    ):
        # first print primary machine info
        table.add_row(
            "\n".join(
                [
                    f"[bold]{_color_encode_with_state('Primary', cluster.primary.ec2_instance)}",
                    f"Name: {cluster.primary.name}",
                    f"ID: {cluster.primary.ec2_instance.id}",
                    f"AMI: {cluster.primary.ec2_instance.image_id}({cluster.primary.ec2_instance.image.name})",
                    f"Type: {cluster.primary.ec2_instance.instance_type}",
                    f"Up: {_timedelta_formatting(time_now - cluster.primary.ec2_instance.launch_time, color_code=True)}",
                    f"ExtIP: {cluster.primary.ec2_instance.public_ip_address}",
                    f"IntIP: {cluster.primary.ec2_instance.private_ip_address}",
                    f"UserID: {cluster.primary.user_id}",
                    f"WalletID: {cluster.primary.wallet_id}",
                    f"Heartbeat: {_timedelta_formatting(time_now - cluster.primary.last_heartbeat) if cluster.primary.last_heartbeat else 'n/a'}",
                    f"/mnt/docker(free): {_color_encode_with_threshold(cluster.primary.disk_space.human_readable(), cluster.primary.disk_space,  TypeAdapter(ByteSize).validate_python('15Gib'))}",
                ]
            ),
            "\n".join(
                [
                    f"Dask Scheduler UI: http://{cluster.primary.ec2_instance.public_ip_address}:8787",
                    f"Dask Scheduler TCP: tcp://{cluster.primary.ec2_instance.public_ip_address}:8786",
                    f"Graylog: {_create_graylog_permalinks(environment, cluster.primary.ec2_instance)}",
                ]
            ),
            "\n".join(
                [
                    f"tasks: {json.dumps(cluster.task_states_to_tasks, indent=2)}",
                    f"Worker metrics: {json.dumps(_get_worker_metrics(cluster.scheduler_info), indent=2)}",
                ]
            ),
        )

        # now add the workers
        for index, worker in enumerate(cluster.workers):
            table.add_row(
                "\n".join(
                    [
                        f"[italic]{_color_encode_with_state(f'Worker {index+1}', worker.ec2_instance)}[/italic]",
                        f"Name: {worker.name}",
                        f"ID: {worker.ec2_instance.id}",
                        f"AMI: {worker.ec2_instance.image_id}({worker.ec2_instance.image.name})",
                        f"Type: {worker.ec2_instance.instance_type}",
                        f"Up: {_timedelta_formatting(time_now - worker.ec2_instance.launch_time, color_code=True)}",
                        f"ExtIP: {worker.ec2_instance.public_ip_address}",
                        f"IntIP: {worker.ec2_instance.private_ip_address}",
                        f"/mnt/docker(free): {_color_encode_with_threshold(worker.disk_space.human_readable(), worker.disk_space,  TypeAdapter(ByteSize).validate_python('15Gib'))}",
                        "",
                    ]
                ),
                "\n".join(
                    [
                        f"Graylog: {_create_graylog_permalinks(environment, worker.ec2_instance)}",
                    ]
                ),
            )
        table.add_row(end_section=True)
    print(table)


def _analyze_dynamic_instances_running_services(
    dynamic_instances: list[DynamicInstance],
    ssh_key_path: Path,
    user_id: int | None,
) -> list[DynamicInstance]:
    # this construction makes the retrieval much faster
    all_running_services = asyncio.get_event_loop().run_until_complete(
        asyncio.gather(
            *(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    _ssh_and_list_running_dyn_services,
                    instance.ec2_instance,
                    _SSH_USER_NAME,
                    ssh_key_path,
                )
                for instance in dynamic_instances
            ),
            return_exceptions=True,
        )
    )

    all_disk_spaces = asyncio.get_event_loop().run_until_complete(
        asyncio.gather(
            *(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    _ssh_and_get_available_disk_space,
                    instance.ec2_instance,
                    _SSH_USER_NAME,
                    ssh_key_path,
                )
                for instance in dynamic_instances
            ),
            return_exceptions=True,
        )
    )

    return [
        replace(instance, running_services=running_services, disk_space=disk_space)
        for instance, running_services, disk_space in zip(
            dynamic_instances, all_running_services, all_disk_spaces, strict=True
        )
        if isinstance(running_services, list)
        and isinstance(disk_space, ByteSize)
        and (user_id is None or any(s.user_id == user_id for s in running_services))
    ]


def _dask_list_tasks(dask_client: distributed.Client) -> dict[TaskState, list[TaskId]]:
    def _list_tasks(
        dask_scheduler: distributed.Scheduler,
    ) -> dict[TaskId, TaskState]:
        # NOTE: this is ok and needed: this runs on the dask scheduler, so don't remove this import

        task_state_to_tasks = {}
        for task in dask_scheduler.tasks.values():
            if task.state in task_state_to_tasks:
                task_state_to_tasks[task.state].append(task.key)
            else:
                task_state_to_tasks[task.state] = [task.key]

        return dict(task_state_to_tasks)

    try:
        list_of_tasks: dict[TaskState, list[TaskId]] = dask_client.run_on_scheduler(
            _list_tasks
        )  # type: ignore
    except TypeError:
        print(f"ERROR while recoverring unrunnable tasks using {dask_client=}")
    return list_of_tasks


def _dask_client(ip_address: str) -> distributed.Client:
    security = distributed.Security()
    dask_certificates = state["deploy_config"] / "assets" / "dask-certificates"
    if dask_certificates.exists():
        security = distributed.Security(
            tls_ca_file=f"{dask_certificates / 'dask-cert.pem'}",
            tls_client_cert=f"{dask_certificates / 'dask-cert.pem'}",
            tls_client_key=f"{dask_certificates / 'dask-key.pem'}",
            require_encryption=True,
        )
    return distributed.Client(
        f"tls://{ip_address}:8786", security=security, timeout="5"
    )


def _analyze_computational_instances(
    computational_instances: list[ComputationalInstance],
    ssh_key_path: Path | None,
) -> list[ComputationalCluster]:

    all_disk_spaces = [UNDEFINED_BYTESIZE] * len(computational_instances)
    if ssh_key_path is not None:
        all_disk_spaces = asyncio.get_event_loop().run_until_complete(
            asyncio.gather(
                *(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        _ssh_and_get_available_disk_space,
                        instance.ec2_instance,
                        _SSH_USER_NAME,
                        ssh_key_path,
                    )
                    for instance in computational_instances
                ),
                return_exceptions=True,
            )
        )

    computational_clusters = []
    for instance, disk_space in track(
        zip(computational_instances, all_disk_spaces, strict=True),
        description="Collecting computational clusters data...",
    ):
        if isinstance(disk_space, ByteSize):
            instance.disk_space = disk_space
        if instance.role is InstanceRole.manager:
            scheduler_info = {}
            datasets_on_cluster = ()
            processing_jobs = {}
            unrunnable_tasks = {}
            with contextlib.suppress(TimeoutError, OSError):
                client = _dask_client(instance.ec2_instance.public_ip_address)

                scheduler_info = client.scheduler_info()
                datasets_on_cluster = client.list_datasets()
                processing_jobs = client.processing()
                unrunnable_tasks = _dask_list_tasks(client)

            assert isinstance(datasets_on_cluster, tuple)
            assert isinstance(processing_jobs, dict)

            computational_clusters.append(
                ComputationalCluster(
                    primary=instance,
                    workers=[],
                    scheduler_info=scheduler_info,
                    datasets=datasets_on_cluster,
                    processing_jobs=processing_jobs,
                    task_states_to_tasks=unrunnable_tasks,
                )
            )

    for instance in computational_instances:
        if instance.role is InstanceRole.worker:
            # assign the worker to correct cluster
            for cluster in computational_clusters:
                if (
                    cluster.primary.user_id == instance.user_id
                    and cluster.primary.wallet_id == instance.wallet_id
                ):
                    cluster.workers.append(instance)

    return computational_clusters


def _detect_instances(
    instances: ServiceResourceInstancesCollection,
    ssh_key_path: Path | None,
    user_id: int | None,
    wallet_id: int | None,
) -> tuple[list[DynamicInstance], list[ComputationalCluster]]:
    dynamic_instances = []
    computational_instances = []
    for instance in track(instances, description="Detecting running instances..."):
        if comp_instance := _parse_computational(instance):
            if (user_id is None or comp_instance.user_id == user_id) and (
                wallet_id is None or comp_instance.wallet_id == wallet_id
            ):
                computational_instances.append(comp_instance)
        elif dyn_instance := _parse_dynamic(instance):
            dynamic_instances.append(dyn_instance)

    if dynamic_instances and ssh_key_path:
        dynamic_instances = _analyze_dynamic_instances_running_services(
            dynamic_instances, ssh_key_path, user_id
        )

    computational_clusters = _analyze_computational_instances(
        computational_instances, ssh_key_path
    )

    return dynamic_instances, computational_clusters


state = {
    "environment": {},
    "ec2_resource": None,
    "dynamic_parser": parse.compile("osparc-dynamic-autoscaled-worker-{key_name}"),
}


@app.callback()
def main(
    deploy_config: Annotated[
        Path, typer.Option(help="path to the deploy configuration")
    ]
):
    """Manages external clusters"""

    state["deploy_config"] = deploy_config.expanduser()
    assert deploy_config.is_dir()
    # get the repo.config file
    repo_config = deploy_config / "repo.config"
    assert repo_config.exists()
    environment = dotenv_values(repo_config)
    assert environment
    state["environment"] = environment
    # connect to ec2
    if environment["AUTOSCALING_EC2_ACCESS_KEY_ID"] == "":
        error_msg = (
            "Terraform is necessary in order to check into that deployment!\n"
            f"install terraform (check README.md in {state['deploy_config']} for instructions)"
            "then run make repo.config.frozen, and replace the repo.config, then re-run this code"
        )
        print(error_msg)
        raise typer.Abort(error_msg)

    state["ec2_resource"] = boto3.resource(
        "ec2",
        region_name=environment["AUTOSCALING_EC2_REGION_NAME"],
        aws_access_key_id=environment["AUTOSCALING_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=environment["AUTOSCALING_EC2_SECRET_ACCESS_KEY"],
    )

    # get all the running instances
    assert environment["EC2_INSTANCES_KEY_NAME"]

    state["dynamic_parser"] = parse.compile(
        f"{environment['EC2_INSTANCES_NAME_PREFIX']}-{{key_name}}"
    )

    # find ssh key path
    for file_path in deploy_config.glob("**/*.pem"):
        # very bad HACK
        if "sim4life.io" in f"{file_path}" and "openssh" not in f"{file_path}":
            continue

        if DEPLOY_SSH_KEY_PARSER.parse(f"{file_path.name}") is not None:
            print(f"found following ssh_key_path: {file_path}")
            state["ssh_key_path"] = file_path
            break


@app.command()
def summary(
    user_id: Annotated[int, typer.Option(help="the user ID")] = None,
    wallet_id: Annotated[int, typer.Option(help="the wallet ID")] = None,
) -> None:
    """Show a summary of the current situation of autoscaled EC2 instances.

    Gives a list of all the instances used for dynamic services, and optionally shows what runs in them.
    Gives alist of all the instances used for computational services (e.g. primary + worker(s) instances)

    Arguments:
        repo_config -- path that shall point to a repo.config type of file (see osparc-ops-deployment-configuration repository)

    """

    # get all the running instances
    environment = state["environment"]
    assert environment["EC2_INSTANCES_KEY_NAME"]
    ec2_resource: EC2ServiceResource = state["ec2_resource"]
    instances = ec2_resource.instances.filter(
        Filters=[
            {"Name": "instance-state-name", "Values": ["running", "pending"]},
            {"Name": "key-name", "Values": [environment["EC2_INSTANCES_KEY_NAME"]]},
        ]
    )

    dynamic_autoscaled_instances, computational_clusters = _detect_instances(
        instances, state["ssh_key_path"], user_id, wallet_id
    )

    _print_dynamic_instances(dynamic_autoscaled_instances, environment)
    _print_computational_clusters(computational_clusters, environment)


@app.command()
def clear_jobs(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[int, typer.Option(help="the wallet ID")],
) -> None:
    """remove any dask jobs from the cluster. Use WITH CARE!!!

    Arguments:
        user_id -- the user ID
        wallet_id -- the wallet ID
    """
    environment = state["environment"]
    ec2_resource: EC2ServiceResource = state["ec2_resource"]
    # Here we can filter like so since computational clusters have these as tags on the machines
    instances = ec2_resource.instances.filter(
        Filters=[
            {"Name": "instance-state-name", "Values": ["running", "pending"]},
            {"Name": "key-name", "Values": [environment["EC2_INSTANCES_KEY_NAME"]]},
            {"Name": "tag:user_id", "Values": [f"{user_id}"]},
            {"Name": "tag:wallet_id", "Values": [f"{wallet_id}"]},
        ]
    )
    dynamic_autoscaled_instances, computational_clusters = _detect_instances(
        instances, state["ssh_key_path"], None, None
    )
    assert not dynamic_autoscaled_instances
    assert computational_clusters
    assert (
        len(computational_clusters) == 1
    ), "too many clusters found! TIP: fix this code"

    _print_computational_clusters(computational_clusters, environment)

    if typer.confirm("Are you sure you want to erase all the jobs from that cluster?"):
        print("proceeding with reseting jobs from cluster...")
        the_cluster = computational_clusters[0]
        with _dask_client(the_cluster.primary.ec2_instance.public_ip_address) as client:
            client.datasets.clear()
        print("proceeding with reseting jobs from cluster done.")
        print("Refreshing...")
        dynamic_autoscaled_instances, computational_clusters = _detect_instances(
            instances, state["ssh_key_path"], None, None
        )
        _print_computational_clusters(computational_clusters, environment)
    else:
        print("not deleting anything")


if __name__ == "__main__":
    app()

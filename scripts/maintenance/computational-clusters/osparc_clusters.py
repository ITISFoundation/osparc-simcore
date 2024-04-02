#! /usr/bin/env python3

import asyncio
import contextlib
import datetime
import json
import re
import uuid
from collections import defaultdict, namedtuple
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Final, TypeAlias

import arrow
import boto3
import distributed
import paramiko
import parse
import sqlalchemy as sa
import typer
from dotenv import dotenv_values
from mypy_boto3_ec2 import EC2ServiceResource
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from mypy_boto3_ec2.type_defs import FilterTypeDef, TagTypeDef
from pydantic import (
    BaseModel,
    ByteSize,
    PostgresDsn,
    TypeAdapter,
    ValidationError,
    field_validator,
)
from rich import print  # pylint: disable=redefined-builtin
from rich.progress import track
from rich.style import Style
from rich.table import Column, Table
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

app = typer.Typer()


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
    dask_ip: str


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


@dataclass(slots=True, kw_only=True, frozen=True)
class ComputationalTask:
    project_id: uuid.UUID
    node_id: uuid.UUID
    job_id: TaskId | None
    service_name: str
    service_version: str
    state: str


@dataclass(slots=True, kw_only=True, frozen=True)
class DaskTask:
    job_id: TaskId
    state: TaskState


@dataclass(frozen=True, slots=True, kw_only=True)
class ComputationalCluster:
    primary: ComputationalInstance
    workers: list[ComputationalInstance]

    scheduler_info: dict[str, Any]
    datasets: tuple[str, ...]
    processing_jobs: dict[str, str]
    task_states_to_tasks: dict[str, list[TaskState]]


MINUTE: Final[int] = 60
HOUR: Final[int] = 60 * MINUTE

DEFAULT_COMPUTATIONAL_EC2_FORMAT: Final[
    str
] = r"osparc-computational-cluster-{role}-{swarm_stack_name}-user_id:{user_id:d}-wallet_id:{wallet_id:d}"
DEFAULT_DYNAMIC_EC2_FORMAT: Final[str] = r"osparc-dynamic-autoscaled-worker-{key_name}"

DEPLOY_SSH_KEY_PARSER: Final[parse.Parser] = parse.compile(r"osparc-{random_name}.pem")
SSH_USER_NAME: Final[str] = "ubuntu"
UNDEFINED_BYTESIZE: Final[ByteSize] = ByteSize(-1)
TASK_CANCEL_EVENT_NAME_TEMPLATE: Final[str] = "cancel_event_{}"

# NOTE: service_name and service_version are not available on dynamic-sidecar/dynamic-proxies!
DYN_SERVICES_NAMING_CONVENTION: Final[re.Pattern] = re.compile(
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


@dataclass(kw_only=True)
class AppState:
    environment: dict[str, str | None] = field(default_factory=dict)
    ec2_resource_autoscaling: EC2ServiceResource | None = None
    ec2_resource_clusters_keeper: EC2ServiceResource | None = None
    dynamic_parser: parse.Parser
    computational_parser: parse.Parser
    deploy_config: Path | None = None
    ssh_key_path: Path | None = None


state: AppState = AppState(
    dynamic_parser=parse.compile(DEFAULT_DYNAMIC_EC2_FORMAT),
    computational_parser=parse.compile(DEFAULT_COMPUTATIONAL_EC2_FORMAT),
)


class PostgresDB(BaseModel):
    dsn: PostgresDsn

    @classmethod
    @field_validator("db")
    def check_db_name(cls, v):
        assert v.path and len(v.path) > 1, "database must be provided"  # noqa: PT018
        return v


@contextlib.asynccontextmanager
async def db_engine() -> AsyncGenerator[AsyncEngine, Any]:
    engine = None
    try:
        for env in [
            "POSTGRES_USER",
            "POSTGRES_PASSWORD",
            "POSTGRES_ENDPOINT",
            "POSTGRES_DB",
        ]:
            assert state.environment[env]
        postgres_db = PostgresDB(
            dsn=f"postgresql+asyncpg://{state.environment['POSTGRES_USER']}:{state.environment['POSTGRES_PASSWORD']}@{state.environment['POSTGRES_ENDPOINT']}/{state.environment['POSTGRES_DB']}"
        )

        engine = create_async_engine(
            f"{postgres_db.dsn}",
            connect_args={
                "server_settings": {
                    "application_name": "osparc-clusters-monitoring-script"
                }
            },
        )
        yield engine
    finally:
        if engine:
            await engine.dispose()


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
    formatted_time_diff = f"{time_diff.days} day(s), " if time_diff.days > 0 else ""
    formatted_time_diff += f"{time_diff.seconds // 3600:02}:{(time_diff.seconds // 60) % 60:02}:{time_diff.seconds % 60:02}"
    if time_diff.days and color_code:
        formatted_time_diff = f"[red]{formatted_time_diff}[/red]"
    elif (time_diff.seconds > 5 * HOUR) and color_code:
        formatted_time_diff = f"[orange]{formatted_time_diff}[/orange]"
    return formatted_time_diff


def _parse_computational(instance: Instance) -> ComputationalInstance | None:
    name = _get_instance_name(instance)
    if result := state.computational_parser.search(name):
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
            dask_ip="unknown",
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


def _parse_dynamic(instance: Instance) -> DynamicInstance | None:
    name = _get_instance_name(instance)
    if result := state.dynamic_parser.search(name):
        assert isinstance(result, parse.Result)

        return DynamicInstance(
            name=name,
            ec2_instance=instance,
            running_services=[],
            disk_space=UNDEFINED_BYTESIZE,
        )
    return None


def _ssh_and_get_dask_ip(
    instance: Instance, username: str, private_key_path: Path
) -> str:
    # Establish SSH connection with key-based authentication
    with paramiko.SSHClient() as client:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                instance.public_ip_address,
                username=username,
                key_filename=f"{private_key_path}",
                timeout=5,
            )
            # Command to get disk space for /docker partition
            dask_ip_command = "docker inspect -f '{{.NetworkSettings.Networks.dask_stack_default.IPAddress}}' $(docker ps --filter 'name=dask-sidecar|dask-scheduler' --format '{{.ID}}')"

            # Run the command on the remote machine
            _, stdout, _ = client.exec_command(dask_ip_command)
            exit_status = stdout.channel.recv_exit_status()

            if exit_status != 0:
                return "Not Found / Drained / Not Ready"

            # Available disk space will be captured here
            return stdout.read().decode("utf-8").strip()
        except (
            paramiko.AuthenticationException,
            paramiko.SSHException,
            TimeoutError,
        ):
            return "Not Ready"


def _ssh_and_get_available_disk_space(
    instance: Instance, username: str, private_key_path: Path
) -> ByteSize:
    # Establish SSH connection with key-based authentication
    with paramiko.SSHClient() as client:
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
            _, stdout, stderr = client.exec_command(disk_space_command)
            exit_status = stdout.channel.recv_exit_status()
            error = stderr.read().decode()

            if exit_status != 0:
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


def _ssh_and_list_running_dyn_services(
    instance: Instance, username: str, private_key_path: Path
) -> list[DynamicService]:
    # Establish SSH connection with key-based authentication
    with paramiko.SSHClient() as client:
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
            exit_status = stdout.channel.recv_exit_status()
            error = stderr.read().decode()
            if exit_status != 0:
                print(error)
                raise typer.Abort(error)

            output = stdout.read().decode("utf-8")
            # Extract containers that follow the naming convention
            running_service: dict[str, list[DockerContainer]] = defaultdict(list)
            for container in output.splitlines():
                if match := re.match(DYN_SERVICES_NAMING_CONVENTION, container):
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


def _print_dynamic_instances(
    instances: list[DynamicInstance],
    environment: dict[str, str | None],
    aws_region: str,
) -> None:
    time_now = arrow.utcnow()
    table = Table(
        Column("Instance"),
        Column(
            "Running services",
            footer="[red]Intervention detection might show false positive if in transient state, be careful and always double-check!![/red]",
        ),
        title=f"dynamic autoscaled instances: {aws_region}",
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
                expand=True,
                padding=(0, 0),
            )
            for service in instance.running_services:
                service_table.add_row(
                    f"{service.user_id}",
                    service.project_id,
                    service.node_id,
                    service.service_name,
                    service.service_version,
                    _timedelta_formatting(
                        time_now - service.created_at, color_code=True
                    ),
                    f"{'[red]' if service.needs_manual_intervention else ''}{service.needs_manual_intervention}{'[/red]' if service.needs_manual_intervention else ''}",
                )

        table.add_row(
            "\n".join(
                [
                    f"{_color_encode_with_state(instance.name, instance.ec2_instance)}",
                    f"ID: {instance.ec2_instance.instance_id}",
                    f"AMI: {instance.ec2_instance.image_id}",
                    f"AMI name: {instance.ec2_instance.image.name}",
                    f"Type: {instance.ec2_instance.instance_type}",
                    f"Up: {_timedelta_formatting(time_now - instance.ec2_instance.launch_time, color_code=True)}",
                    f"ExtIP: {instance.ec2_instance.public_ip_address}",
                    f"IntIP: {instance.ec2_instance.private_ip_address}",
                    f"/mnt/docker(free): {_color_encode_with_threshold(instance.disk_space.human_readable(), instance.disk_space,  TypeAdapter(ByteSize).validate_python('15Gib'))}",
                ]
            ),
            service_table,
        )
        table.add_row(
            "Graylog: ",
            f"{_create_graylog_permalinks(environment, instance.ec2_instance)}",
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
    clusters: list[ComputationalCluster],
    environment: dict[str, str | None],
    aws_region: str,
) -> None:
    time_now = arrow.utcnow()
    table = Table(
        Column("Instance", justify="left", overflow="ellipsis", ratio=1),
        Column("Computational details", overflow="fold", ratio=2),
        title=f"computational clusters: {aws_region}",
        padding=(0, 0),
        title_style=Style(color="red", encircle=True),
        expand=True,
    )

    for cluster in track(
        clusters, "Collecting information about computational clusters..."
    ):
        cluster_worker_metrics = _get_worker_metrics(cluster.scheduler_info)
        # first print primary machine info
        table.add_row(
            "\n".join(
                [
                    f"[bold]{_color_encode_with_state('Primary', cluster.primary.ec2_instance)}",
                    f"Name: {cluster.primary.name}",
                    f"ID: {cluster.primary.ec2_instance.id}",
                    f"AMI: {cluster.primary.ec2_instance.image_id}",
                    f"AMI name: {cluster.primary.ec2_instance.image.name}",
                    f"Type: {cluster.primary.ec2_instance.instance_type}",
                    f"Up: {_timedelta_formatting(time_now - cluster.primary.ec2_instance.launch_time, color_code=True)}",
                    f"ExtIP: {cluster.primary.ec2_instance.public_ip_address}",
                    f"IntIP: {cluster.primary.ec2_instance.private_ip_address}",
                    f"DaskSchedulerIP: {cluster.primary.dask_ip}",
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
                    f"Graylog UI: {_create_graylog_permalinks(environment, cluster.primary.ec2_instance)}",
                    f"Prometheus UI: http://{cluster.primary.ec2_instance.public_ip_address}:9090",
                    f"tasks: {json.dumps(cluster.task_states_to_tasks, indent=2)}",
                ]
            ),
        )

        # now add the workers
        for index, worker in enumerate(cluster.workers):
            worker_dask_metrics = next(
                (
                    worker_metrics
                    for worker_name, worker_metrics in cluster_worker_metrics.items()
                    if worker.dask_ip in worker_name
                ),
                "no metrics???",
            )
            worker_processing_jobs = [
                job_id
                for worker_name, job_id in cluster.processing_jobs.items()
                if worker.dask_ip in worker_name
            ]
            table.add_row()
            table.add_row(
                "\n".join(
                    [
                        f"[italic]{_color_encode_with_state(f'Worker {index+1}', worker.ec2_instance)}[/italic]",
                        f"Name: {worker.name}",
                        f"ID: {worker.ec2_instance.id}",
                        f"AMI: {worker.ec2_instance.image_id}",
                        f"AMI name: {worker.ec2_instance.image.name}",
                        f"Type: {worker.ec2_instance.instance_type}",
                        f"Up: {_timedelta_formatting(time_now - worker.ec2_instance.launch_time, color_code=True)}",
                        f"ExtIP: {worker.ec2_instance.public_ip_address}",
                        f"IntIP: {worker.ec2_instance.private_ip_address}",
                        f"DaskWorkerIP: {worker.dask_ip}",
                        f"/mnt/docker(free): {_color_encode_with_threshold(worker.disk_space.human_readable(), worker.disk_space,  TypeAdapter(ByteSize).validate_python('15Gib'))}",
                        "",
                    ]
                ),
                "\n".join(
                    [
                        f"Graylog: {_create_graylog_permalinks(environment, worker.ec2_instance)}",
                        f"Dask metrics: {json.dumps(worker_dask_metrics, indent=2)}",
                        f"Running tasks: {worker_processing_jobs}",
                    ]
                ),
            )
        table.add_row(end_section=True)
    print(table)


async def _fetch_instance_details(
    instance: DynamicInstance, ssh_key_path: Path
) -> tuple[list[DynamicService] | BaseException, ByteSize | BaseException]:
    # Run both SSH operations concurrently for this instance
    running_services, disk_space = await asyncio.gather(
        asyncio.get_event_loop().run_in_executor(
            None,
            _ssh_and_list_running_dyn_services,
            instance.ec2_instance,
            SSH_USER_NAME,
            ssh_key_path,
        ),
        asyncio.get_event_loop().run_in_executor(
            None,
            _ssh_and_get_available_disk_space,
            instance.ec2_instance,
            SSH_USER_NAME,
            ssh_key_path,
        ),
        return_exceptions=True,
    )
    return running_services, disk_space


async def _analyze_dynamic_instances_running_services_concurrently(
    dynamic_instances: list[DynamicInstance],
    ssh_key_path: Path,
    user_id: int | None,
) -> list[DynamicInstance]:
    details = await asyncio.gather(
        *(
            _fetch_instance_details(instance, ssh_key_path)
            for instance in dynamic_instances
        ),
        return_exceptions=True,
    )

    # Filter and update instances based on results and given criteria
    return [
        replace(
            instance,
            running_services=instance_details[0],
            disk_space=instance_details[1],
        )
        for instance, instance_details in zip(dynamic_instances, details, strict=True)
        if isinstance(instance_details, tuple)
        and isinstance(instance_details[0], list)
        and isinstance(instance_details[1], ByteSize)
        and (user_id is None or any(s.user_id == user_id for s in instance_details[0]))
    ]


async def _dask_list_tasks(
    dask_client: distributed.Client,
) -> dict[TaskState, list[TaskId]]:
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
        list_of_tasks: dict[
            TaskState, list[TaskId]
        ] = await dask_client.run_on_scheduler(
            _list_tasks
        )  # type: ignore
    except TypeError:
        print(f"ERROR while recoverring unrunnable tasks using {dask_client=}")
    return list_of_tasks


@contextlib.asynccontextmanager
async def _dask_client(ip_address: str) -> AsyncGenerator[distributed.Client, None]:
    security = distributed.Security()
    assert state.deploy_config
    dask_certificates = state.deploy_config / "assets" / "dask-certificates"
    if dask_certificates.exists():
        security = distributed.Security(
            tls_ca_file=f"{dask_certificates / 'dask-cert.pem'}",
            tls_client_cert=f"{dask_certificates / 'dask-cert.pem'}",
            tls_client_key=f"{dask_certificates / 'dask-key.pem'}",
            require_encryption=True,
        )
    try:

        async with distributed.Client(
            f"tls://{ip_address}:8786",
            security=security,
            timeout="5",
            asynchronous=True,
        ) as client:
            yield client
    finally:
        ...


async def _analyze_computational_instances(
    computational_instances: list[ComputationalInstance],
    ssh_key_path: Path | None,
) -> list[ComputationalCluster]:

    all_disk_spaces = [UNDEFINED_BYTESIZE] * len(computational_instances)
    if ssh_key_path is not None:
        all_disk_spaces = await asyncio.gather(
            *(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    _ssh_and_get_available_disk_space,
                    instance.ec2_instance,
                    SSH_USER_NAME,
                    ssh_key_path,
                )
                for instance in computational_instances
            ),
            return_exceptions=True,
        )

        all_dask_ips = await asyncio.gather(
            *(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    _ssh_and_get_dask_ip,
                    instance.ec2_instance,
                    SSH_USER_NAME,
                    ssh_key_path,
                )
                for instance in computational_instances
            ),
            return_exceptions=True,
        )

    computational_clusters = []
    for instance, disk_space, dask_ip in track(
        zip(computational_instances, all_disk_spaces, all_dask_ips, strict=True),
        description="Collecting computational clusters data...",
    ):
        if isinstance(disk_space, ByteSize):
            instance.disk_space = disk_space
        if isinstance(dask_ip, str):
            instance.dask_ip = dask_ip
        if instance.role is InstanceRole.manager:
            scheduler_info = {}
            datasets_on_cluster = ()
            processing_jobs = {}
            all_tasks = {}
            with contextlib.suppress(TimeoutError, OSError):
                async with _dask_client(
                    instance.ec2_instance.public_ip_address
                ) as client:
                    scheduler_info = client.scheduler_info()
                    datasets_on_cluster = await client.list_datasets()
                    processing_jobs = await client.processing()
                    all_tasks = await _dask_list_tasks(client)

            assert isinstance(datasets_on_cluster, tuple)
            assert isinstance(processing_jobs, dict)

            computational_clusters.append(
                ComputationalCluster(
                    primary=instance,
                    workers=[],
                    scheduler_info=scheduler_info,
                    datasets=datasets_on_cluster,
                    processing_jobs=processing_jobs,
                    task_states_to_tasks=all_tasks,
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


async def _parse_computational_clusters(
    instances: ServiceResourceInstancesCollection,
    ssh_key_path: Path | None,
    user_id: int | None,
    wallet_id: int | None,
) -> list[ComputationalCluster]:
    computational_instances = [
        comp_instance
        for instance in track(
            instances, description="Parsing computational instances..."
        )
        if (
            comp_instance := await asyncio.get_event_loop().run_in_executor(
                None, _parse_computational, instance
            )
        )
        and (user_id is None or comp_instance.user_id == user_id)
        and (wallet_id is None or comp_instance.wallet_id == wallet_id)
    ]
    return await _analyze_computational_instances(computational_instances, ssh_key_path)


async def _parse_dynamic_instances(
    instances: ServiceResourceInstancesCollection,
    ssh_key_path: Path | None,
    user_id: int | None,
    wallet_id: int | None,
) -> list[DynamicInstance]:
    dynamic_instances = [
        dyn_instance
        for instance in track(instances, description="Parsing dynamic instances...")
        if (dyn_instance := _parse_dynamic(instance))
    ]
    if dynamic_instances and ssh_key_path:
        dynamic_instances = (
            await _analyze_dynamic_instances_running_services_concurrently(
                dynamic_instances, ssh_key_path, user_id
            )
        )
    return dynamic_instances


def _list_running_ec2_instances(
    ec2_resource: EC2ServiceResource,
    key_name: str,
    custom_tags: dict[str, str],
    user_id: int | None,
    wallet_id: int | None,
) -> ServiceResourceInstancesCollection:
    # get all the running instances

    ec2_filters: list[FilterTypeDef] = [
        {"Name": "instance-state-name", "Values": ["running", "pending"]},
        {"Name": "key-name", "Values": [key_name]},
    ]
    if custom_tags:
        ec2_filters.extend(
            [
                {"Name": f"tag:{key}", "Values": [f"{value}"]}
                for key, value in custom_tags.items()
            ]
        )

    if user_id:
        ec2_filters.append({"Name": "tag:user_id", "Values": [f"{user_id}"]})
    if wallet_id:
        ec2_filters.append({"Name": "tag:wallet_id", "Values": [f"{wallet_id}"]})

    return ec2_resource.instances.filter(Filters=ec2_filters)


async def _list_dynamic_instances_from_ec2(
    user_id: int | None,
    wallet_id: int | None,
) -> ServiceResourceInstancesCollection:
    assert state.environment["EC2_INSTANCES_KEY_NAME"]
    custom_tags = {}
    if state.environment["EC2_INSTANCES_CUSTOM_TAGS"]:
        custom_tags = json.loads(state.environment["EC2_INSTANCES_CUSTOM_TAGS"])
    assert state.ec2_resource_autoscaling
    return await asyncio.get_event_loop().run_in_executor(
        None,
        _list_running_ec2_instances,
        state.ec2_resource_autoscaling,
        state.environment["EC2_INSTANCES_KEY_NAME"],
        custom_tags,
        user_id,
        wallet_id,
    )


async def _list_computational_instances_from_ec2(
    user_id: int | None,
    wallet_id: int | None,
) -> ServiceResourceInstancesCollection:
    assert state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"]
    assert state.environment["WORKERS_EC2_INSTANCES_KEY_NAME"]
    assert (
        state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"]
        == state.environment["WORKERS_EC2_INSTANCES_KEY_NAME"]
    ), "key name is different on primary and workers. TIP: adjust this code now"
    custom_tags = {}
    if state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"]:
        assert (
            state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"]
            == state.environment["WORKERS_EC2_INSTANCES_CUSTOM_TAGS"]
        ), "custom tags are different on primary and workers. TIP: adjust this code now"
        custom_tags = json.loads(state.environment["PRIMARY_EC2_INSTANCES_CUSTOM_TAGS"])
    assert state.ec2_resource_clusters_keeper
    return await asyncio.get_event_loop().run_in_executor(
        None,
        _list_running_ec2_instances,
        state.ec2_resource_clusters_keeper,
        state.environment["PRIMARY_EC2_INSTANCES_KEY_NAME"],
        custom_tags,
        user_id,
        wallet_id,
    )


def _parse_environment(deploy_config: Path) -> dict[str, str | None]:
    repo_config = deploy_config / "repo.config"
    assert repo_config.exists()
    environment = dotenv_values(repo_config)
    if environment["AUTOSCALING_EC2_ACCESS_KEY_ID"] == "":
        print(
            "Terraform variables detected, looking for repo.config.frozen as alternative."
            " TIP: you are responsible for them being up to date!!"
        )
        repo_config = deploy_config / "repo.config.frozen"
        assert repo_config.exists()
        environment = dotenv_values(repo_config)

        if environment["AUTOSCALING_EC2_ACCESS_KEY_ID"] == "":
            error_msg = (
                "Terraform is necessary in order to check into that deployment!\n"
                f"install terraform (check README.md in {state.deploy_config} for instructions)"
                "then run make repo.config.frozen, then re-run this code"
            )
            print(error_msg)
            raise typer.Abort(error_msg)
    assert environment
    return environment


@app.callback()
def main(
    deploy_config: Annotated[
        Path, typer.Option(help="path to the deploy configuration")
    ]
):
    """Manages external clusters"""

    state.deploy_config = deploy_config.expanduser()
    assert (
        deploy_config.is_dir()
    ), "deploy-config argument is not pointing to a directory!"

    state.environment = _parse_environment(deploy_config)

    # connect to ec2s
    state.ec2_resource_autoscaling = boto3.resource(
        "ec2",
        region_name=state.environment["AUTOSCALING_EC2_REGION_NAME"],
        aws_access_key_id=state.environment["AUTOSCALING_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=state.environment["AUTOSCALING_EC2_SECRET_ACCESS_KEY"],
    )

    state.ec2_resource_clusters_keeper = boto3.resource(
        "ec2",
        region_name=state.environment["CLUSTERS_KEEPER_EC2_REGION_NAME"],
        aws_access_key_id=state.environment["CLUSTERS_KEEPER_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=state.environment[
            "CLUSTERS_KEEPER_EC2_SECRET_ACCESS_KEY"
        ],
    )

    assert state.environment["EC2_INSTANCES_KEY_NAME"]
    state.dynamic_parser = parse.compile(
        f"{state.environment['EC2_INSTANCES_NAME_PREFIX']}-{{key_name}}"
    )
    if state.environment["CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX"]:
        state.computational_parser = parse.compile(
            f"{state.environment['CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX']}-{DEFAULT_COMPUTATIONAL_EC2_FORMAT}"
        )

    # locate ssh key path
    for file_path in deploy_config.glob("**/*.pem"):
        # very bad HACK
        if "sim4life.io" in f"{file_path}" and "openssh" not in f"{file_path}":
            continue

        if DEPLOY_SSH_KEY_PARSER.parse(f"{file_path.name}") is not None:
            print(
                f"will be using following ssh_key_path: {file_path}. "
                "TIP: if wrong adapt the code or manually remove some of them."
            )
            state.ssh_key_path = file_path
            break


async def _summary(user_id: int | None, wallet_id: int | None) -> None:
    # get all the running instances
    assert state.ec2_resource_autoscaling
    dynamic_instances = await _list_dynamic_instances_from_ec2(user_id, wallet_id)
    dynamic_autoscaled_instances = await _parse_dynamic_instances(
        dynamic_instances, state.ssh_key_path, user_id, wallet_id
    )
    _print_dynamic_instances(
        dynamic_autoscaled_instances,
        state.environment,
        state.ec2_resource_autoscaling.meta.client.meta.region_name,
    )

    assert state.ec2_resource_clusters_keeper
    computational_instances = await _list_computational_instances_from_ec2(
        user_id, wallet_id
    )
    computational_clusters = await _parse_computational_clusters(
        computational_instances, state.ssh_key_path, user_id, wallet_id
    )
    _print_computational_clusters(
        computational_clusters,
        state.environment,
        state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
    )


@app.command()
def summary(
    user_id: Annotated[int, typer.Option(help="filters by the user ID")] = 0,
    wallet_id: Annotated[int, typer.Option(help="filters by the wallet ID")] = 0,
) -> None:
    """Show a summary of the current situation of autoscaled EC2 instances.

    Gives a list of all the instances used for dynamic services, and optionally shows what runs in them.
    Gives alist of all the instances used for computational services (e.g. primary + worker(s) instances)

    Arguments:
        repo_config -- path that shall point to a repo.config type of file (see osparc-ops-deployment-configuration repository)

    """

    asyncio.run(_summary(user_id or None, wallet_id or None))


async def _abort_job_in_db(project_id: uuid.UUID, node_id: uuid.UUID) -> None:
    async with contextlib.AsyncExitStack() as stack:
        engine = await stack.enter_async_context(db_engine())
        db_connection = await stack.enter_async_context(engine.begin())

        await db_connection.execute(
            sa.text(
                f"UPDATE comp_tasks SET state = 'ABORTED' WHERE project_id='{project_id}' AND node_id='{node_id}'"
            )
        )
        print(f"set comp_tasks for {project_id=}/{node_id=} set to ABORTED")


async def _list_computational_tasks_from_db(user_id: int) -> list[ComputationalTask]:
    async with contextlib.AsyncExitStack() as stack:
        engine = await stack.enter_async_context(db_engine())
        db_connection = await stack.enter_async_context(engine.begin())

        # Get the list of running project UUIDs with a subquery
        subquery = (
            sa.select(sa.column("project_uuid"))
            .select_from(sa.table("comp_runs"))
            .where(
                sa.and_(
                    sa.column("user_id") == user_id,
                    sa.cast(sa.column("result"), sa.VARCHAR) != "SUCCESS",
                    sa.cast(sa.column("result"), sa.VARCHAR) != "FAILED",
                    sa.cast(sa.column("result"), sa.VARCHAR) != "ABORTED",
                )
            )
        )

        # Now select comp_tasks rows where project_id is one of the project_uuids
        query = (
            sa.select("*")
            .select_from(sa.table("comp_tasks"))
            .where(
                sa.column("project_id").in_(subquery)
                & (sa.cast(sa.column("state"), sa.VARCHAR) != "SUCCESS")
                & (sa.cast(sa.column("state"), sa.VARCHAR) != "FAILED")
                & (sa.cast(sa.column("state"), sa.VARCHAR) != "ABORTED")
            )
        )

        result = await db_connection.execute(query)
        comp_tasks_list = result.fetchall()
        return [
            TypeAdapter(ComputationalTask).validate_python(
                {
                    "project_id": row.project_id,
                    "node_id": row.node_id,
                    "job_id": row.job_id,
                    "service_name": row.image["name"].split("/")[-1],
                    "service_version": row.image["tag"],
                    "state": row.state,
                }
            )
            for row in comp_tasks_list
        ]
    msg = "unable to access database!"
    raise RuntimeError(msg)


def _print_computational_tasks(
    user_id: int,
    wallet_id: int,
    tasks: list[tuple[ComputationalTask | None, DaskTask | None]],
) -> None:
    table = Table(
        "index",
        "ProjectID",
        "NodeID",
        "ServiceName",
        "ServiceVersion",
        "State in DB",
        "State in Dask cluster",
        title=f"{len(tasks)} Tasks running for {user_id=}/{wallet_id=}",
        padding=(0, 0),
        title_style=Style(color="red", encircle=True),
    )

    for index, (db_task, dask_task) in enumerate(tasks):
        table.add_row(
            f"{index}",
            (
                f"{db_task.project_id}"
                if db_task
                else "[red][bold]intervention needed[/bold][/red]"
            ),
            f"{db_task.node_id}" if db_task else "",
            f"{db_task.service_name}" if db_task else "",
            f"{db_task.service_version}" if db_task else "",
            f"{db_task.state}" if db_task else "",
            (
                dask_task.state
                if dask_task
                else "[orange]task not yet in cluster[/orange]"
            ),
        )

    print(table)


async def _list_computational_clusters(
    user_id: int, wallet_id: int
) -> list[ComputationalCluster]:
    assert state.ec2_resource_clusters_keeper
    computational_instances = await _list_computational_instances_from_ec2(
        user_id, wallet_id
    )
    return await _parse_computational_clusters(
        computational_instances, state.ssh_key_path, user_id, wallet_id
    )


async def _trigger_job_cancellation_in_scheduler(
    cluster: ComputationalCluster, task_id: TaskId
) -> None:
    async with _dask_client(
        cluster.primary.ec2_instance.public_ip_address
    ) as dask_client:
        task_future = distributed.Future(task_id)
        cancel_event = distributed.Event(
            name=TASK_CANCEL_EVENT_NAME_TEMPLATE.format(task_future.key),
            client=dask_client,
        )
        await cancel_event.set()
        await task_future.cancel()
        print(f"cancelled {task_id} in scheduler/workers")


async def _remove_job_from_scheduler(
    cluster: ComputationalCluster, task_id: TaskId
) -> None:
    async with _dask_client(
        cluster.primary.ec2_instance.public_ip_address
    ) as dask_client:
        await dask_client.unpublish_dataset(task_id)
        print(f"unpublished {task_id} from scheduler")


async def _cancel_jobs(  # noqa: C901, PLR0912
    user_id: int, wallet_id: int, *, force: bool
) -> None:
    # get the theory
    computational_tasks = await _list_computational_tasks_from_db(user_id)

    # get the reality
    computational_clusters = await _list_computational_clusters(user_id, wallet_id)
    job_id_to_dask_state: dict[TaskId, TaskState] = {}
    if computational_clusters:
        assert (
            len(computational_clusters) == 1
        ), "too many clusters found! TIP: fix this code or something weird is playing out"

        the_cluster = computational_clusters[0]
        print(f"{the_cluster.task_states_to_tasks=}")

        for job_state, job_ids in the_cluster.task_states_to_tasks.items():
            for job_id in job_ids:
                job_id_to_dask_state[job_id] = job_state

    task_to_dask_job: list[tuple[ComputationalTask | None, DaskTask | None]] = []
    for task in computational_tasks:
        dask_task = None
        if task.job_id:
            dask_task = DaskTask(
                job_id=task.job_id,
                state=job_id_to_dask_state.pop(task.job_id, None) or "unknown",
            )
        task_to_dask_job.append((task, dask_task))
    # keep the jobs still in the cluster
    for job_id, dask_state in job_id_to_dask_state.items():
        task_to_dask_job.append((None, DaskTask(job_id=job_id, state=dask_state)))

    if not task_to_dask_job:
        print("[red]nothing found![/red]")
        raise typer.Exit

    _print_computational_tasks(user_id, wallet_id, task_to_dask_job)
    print(the_cluster.datasets)
    try:
        if response := typer.prompt(
            "[yellow]Which dataset to cancel? all for all of them.[/yellow]",
            default="none",
        ):
            if response == "none":
                print("[yellow]not cancelling anything[/yellow]")
            elif response == "all":
                for comp_task, dask_task in task_to_dask_job:
                    if dask_task is not None and dask_task.state != "unknown":
                        await _trigger_job_cancellation_in_scheduler(
                            the_cluster, dask_task.job_id
                        )
                        if comp_task is None:
                            # we need to clear it of the cluster
                            await _remove_job_from_scheduler(
                                the_cluster, dask_task.job_id
                            )
                    if comp_task is not None and force:
                        await _abort_job_in_db(comp_task.project_id, comp_task.node_id)

                print("cancelled all tasks")
            else:
                selected_index = TypeAdapter(int).validate_python(response)
                comp_task, dask_task = task_to_dask_job[selected_index]
                if dask_task is not None and dask_task.state != "unknown":
                    await _trigger_job_cancellation_in_scheduler(
                        the_cluster, dask_task.job_id
                    )
                    if comp_task is None:
                        # we need to clear it of the cluster
                        await _remove_job_from_scheduler(the_cluster, dask_task.job_id)

                if comp_task is not None and force:
                    await _abort_job_in_db(comp_task.project_id, comp_task.node_id)

    except ValidationError:
        print("[yellow]wrong index, not cancelling anything[/yellow]")


@app.command()
def cancel_jobs(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[int, typer.Option(help="the wallet ID")],
    *,
    force: Annotated[
        bool,
        typer.Option(
            help="will also force the job to abort in the database (use only if job is in WAITING FOR CLUSTER/WAITING FOR RESOURCE)"
        ),
    ] = False,
) -> None:
    """Cancel jobs from the cluster, this will rely on osparc platform to work properly
    The director-v2 should receive the cancellation and abort the concerned pipelines in the next 15 seconds.
    NOTE: This should be called prior to clearing jobs on the cluster.

    Keyword Arguments:
        user_id -- the user ID
        wallet_id -- the wallet ID
    """
    asyncio.run(_cancel_jobs(user_id, wallet_id, force=force))


async def _trigger_cluster_termination(user_id: int, wallet_id: int) -> None:
    assert state.ec2_resource_clusters_keeper
    computational_instances = await _list_computational_instances_from_ec2(
        user_id, wallet_id
    )
    computational_clusters = await _parse_computational_clusters(
        computational_instances, state.ssh_key_path, user_id, wallet_id
    )
    assert computational_clusters
    assert (
        len(computational_clusters) == 1
    ), "too many clusters found! TIP: fix this code"

    _print_computational_clusters(
        computational_clusters,
        state.environment,
        state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
    )
    if typer.confirm("Are you sure you want to trigger termination of that cluster?"):
        the_cluster = computational_clusters[0]
        new_heartbeat_tag: TagTypeDef = {
            "Key": "last_heartbeat",
            "Value": f"{arrow.utcnow().datetime - datetime.timedelta(hours=1)}",
        }
        the_cluster.primary.ec2_instance.create_tags(Tags=[new_heartbeat_tag])
        print(
            f"heartbeat tag on cluster of {user_id=}/{wallet_id=} changed, clusters-keeper will terminate that cluster soon."
        )
    else:
        print("not deleting anything")


@app.command()
def trigger_cluster_termination(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[int, typer.Option(help="the wallet ID")],
) -> None:
    """this will set the Heartbeat tag on the primary machine to 1 hour, thus ensuring the
    clusters-keeper will properly terminate that cluster.

    Keyword Arguments:
        user_id -- the user ID
        wallet_id -- the wallet ID
    """
    asyncio.run(_trigger_cluster_termination(user_id, wallet_id))


if __name__ == "__main__":
    app()

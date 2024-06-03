#! /usr/bin/env python3

import asyncio
import contextlib
import datetime
import json
import re
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

import arrow
import distributed
import paramiko
import parse
import rich
import typer
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from mypy_boto3_ec2.type_defs import TagTypeDef
from pydantic import ByteSize, TypeAdapter, ValidationError
from rich.progress import track
from rich.style import Style
from rich.table import Column, Table

from .dask import (
    dask_client,
    remove_job_from_scheduler,
    trigger_job_cancellation_in_scheduler,
)
from .db import abort_job_in_db, list_computational_tasks_from_db
from .ec2 import list_computational_instances_from_ec2, list_dynamic_instances_from_ec2
from .models import (
    AppState,
    ComputationalCluster,
    ComputationalInstance,
    ComputationalTask,
    DaskTask,
    DynamicInstance,
    DynamicService,
    InstanceRole,
    TaskId,
    TaskState,
)


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
    assert state.ssh_key_path
    with _ssh_tunnel(
        ssh_host=_BASTION_HOST,
        username=username,
        private_key_path=state.ssh_key_path,
        remote_bind_host=instance.private_ip_address,
        remote_bind_port=_DEFAULT_SSH_PORT,
    ) as tunnel:
        assert tunnel  # nosec
        host, port = tunnel.local_bind_address
        forward_url = f"tls://{host}:{port}"

        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(
                    forward_url,
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
    assert state.ssh_key_path
    with _ssh_tunnel(
        ssh_host=_BASTION_HOST,
        username=username,
        private_key_path=state.ssh_key_path,
        remote_bind_host=instance.private_ip_address,
        remote_bind_port=_DEFAULT_SSH_PORT,
    ) as tunnel:
        assert tunnel  # nosec
        host, port = tunnel.local_bind_address
        forward_url = f"tls://{host}:{port}"
        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(
                    forward_url,
                    username=username,
                    key_filename=f"{private_key_path}",
                    timeout=5,
                )
                # Command to get disk space for /docker partition
                disk_space_command = (
                    "df --block-size=1 /mnt/docker | awk 'NR==2{print $4}'"
                )

                # Run the command on the remote machine
                _, stdout, stderr = client.exec_command(disk_space_command)
                exit_status = stdout.channel.recv_exit_status()
                error = stderr.read().decode()

                if exit_status != 0:
                    rich.print(error)
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
    assert state.ssh_key_path
    with _ssh_tunnel(
        ssh_host=_BASTION_HOST,
        username=username,
        private_key_path=state.ssh_key_path,
        remote_bind_host=instance.private_ip_address,
        remote_bind_port=_DEFAULT_SSH_PORT,
    ) as tunnel:
        assert tunnel  # nosec
        host, port = tunnel.local_bind_address
        forward_url = f"tls://{host}:{port}"
        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(
                    forward_url,
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
                    rich.print(error)
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
                        needs_manual_intervention=_needs_manual_intervention(
                            containers
                        ),
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
    rich.print(table, flush=True)


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
                    f"Dask Scheduler TLS: tls://{cluster.primary.ec2_instance.public_ip_address}:8786",
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
    rich.print(table)


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
        rich.print(f"ERROR while recoverring unrunnable tasks using {dask_client=}")
    return list_of_tasks


_SCHEDULER_PORT: Final[int] = 8786


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
                assert ssh_key_path
                async with dask_client(
                    instance.ec2_instance.private_dns_name
                ) as client:
                    scheduler_info = client.scheduler_info()
                    datasets_on_cluster = await _wrap_dask_async_call(
                        client.list_datasets()
                    )
                    processing_jobs = await _wrap_dask_async_call(client.processing())
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


async def summary(state: AppState, user_id: int | None, wallet_id: int | None) -> None:
    # get all the running instances
    assert state.ec2_resource_autoscaling
    dynamic_instances = await list_dynamic_instances_from_ec2(state, user_id, wallet_id)
    dynamic_autoscaled_instances = await _parse_dynamic_instances(
        dynamic_instances, state.ssh_key_path, user_id, wallet_id
    )
    _print_dynamic_instances(
        dynamic_autoscaled_instances,
        state.environment,
        state.ec2_resource_autoscaling.meta.client.meta.region_name,
    )

    assert state.ec2_resource_clusters_keeper
    computational_instances = await list_computational_instances_from_ec2(
        state, user_id, wallet_id
    )
    computational_clusters = await _parse_computational_clusters(
        computational_instances, state.ssh_key_path, user_id, wallet_id
    )
    _print_computational_clusters(
        computational_clusters,
        state.environment,
        state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
    )


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

    rich.print(table)


async def _list_computational_clusters(
    state: AppState, user_id: int, wallet_id: int
) -> list[ComputationalCluster]:
    assert state.ec2_resource_clusters_keeper
    computational_instances = await _list_computational_instances_from_ec2(
        state, user_id, wallet_id
    )
    return await _parse_computational_clusters(
        computational_instances, state.ssh_key_path, user_id, wallet_id
    )


async def cancel_jobs(  # noqa: C901, PLR0912
    state: AppState, user_id: int, wallet_id: int, *, force: bool
) -> None:
    # get the theory
    computational_tasks = await list_computational_tasks_from_db(state, user_id)

    # get the reality
    computational_clusters = await _list_computational_clusters(
        state, user_id, wallet_id
    )
    job_id_to_dask_state: dict[TaskId, TaskState] = {}
    if computational_clusters:
        assert (
            len(computational_clusters) == 1
        ), "too many clusters found! TIP: fix this code or something weird is playing out"

        the_cluster = computational_clusters[0]
        rich.print(f"{the_cluster.task_states_to_tasks=}")

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
        rich.print("[red]nothing found![/red]")
        raise typer.Exit

    _print_computational_tasks(user_id, wallet_id, task_to_dask_job)
    rich.print(the_cluster.datasets)
    try:
        if response := typer.prompt(
            "[yellow]Which dataset to cancel? all for all of them.[/yellow]",
            default="none",
        ):
            if response == "none":
                rich.print("[yellow]not cancelling anything[/yellow]")
            elif response == "all":
                for comp_task, dask_task in task_to_dask_job:
                    if dask_task is not None and dask_task.state != "unknown":
                        await trigger_job_cancellation_in_scheduler(
                            state,
                            the_cluster,
                            dask_task.job_id,
                        )
                        if comp_task is None:
                            # we need to clear it of the cluster
                            await remove_job_from_scheduler(
                                state,
                                the_cluster,
                                dask_task.job_id,
                            )
                    if comp_task is not None and force:
                        await abort_job_in_db(
                            state, comp_task.project_id, comp_task.node_id
                        )

                rich.print("cancelled all tasks")
            else:
                selected_index = TypeAdapter(int).validate_python(response)
                comp_task, dask_task = task_to_dask_job[selected_index]
                if dask_task is not None and dask_task.state != "unknown":
                    await trigger_job_cancellation_in_scheduler(
                        state, the_cluster, dask_task.job_id
                    )
                    if comp_task is None:
                        # we need to clear it of the cluster
                        await remove_job_from_scheduler(
                            state, the_cluster, dask_task.job_id
                        )

                if comp_task is not None and force:
                    await abort_job_in_db(
                        state, comp_task.project_id, comp_task.node_id
                    )

    except ValidationError:
        rich.print("[yellow]wrong index, not cancelling anything[/yellow]")


async def trigger_cluster_termination(
    state: AppState, user_id: int, wallet_id: int
) -> None:
    assert state.ec2_resource_clusters_keeper
    computational_instances = await _list_computational_instances_from_ec2(
        state, user_id, wallet_id
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
        rich.print(
            f"heartbeat tag on cluster of {user_id=}/{wallet_id=} changed, clusters-keeper will terminate that cluster soon."
        )
    else:
        rich.print("not deleting anything")

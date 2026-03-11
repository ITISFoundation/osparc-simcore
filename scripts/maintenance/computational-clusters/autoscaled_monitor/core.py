#! /usr/bin/env python3

import asyncio
import contextlib
import datetime
from dataclasses import replace
from pathlib import Path
from typing import Any

import arrow
import orjson
import parse
import rich
import typer
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from mypy_boto3_ec2.type_defs import TagTypeDef
from pydantic import ByteSize, TypeAdapter, ValidationError
from rich.console import Group
from rich.progress import track
from rich.style import Style
from rich.table import Column, Table

from . import dask, db, ec2, ssh, utils
from .constants import SSH_USER_NAME, STALE_HEARTBEAT_THRESHOLD_MINUTES, UNDEFINED_BYTESIZE
from .models import (
    AppState,
    ComputationalCluster,
    ComputationalInstance,
    ComputationalTask,
    DaskTask,
    DynamicInstance,
    DynamicService,
    InstanceRole,
    ResourceTrackerServiceRun,
    TaskId,
    TaskReconciliationRow,
    TaskState,
    TrackerReconciliationEntry,
)


@utils.to_async
def _parse_computational(state: AppState, instance: Instance) -> ComputationalInstance | None:
    name = utils.get_instance_name(instance)
    if result := (state.computational_parser_workers.parse(name) or state.computational_parser_primary.parse(name)):
        assert isinstance(result, parse.Result)

        last_heartbeat = utils.get_last_heartbeat(instance)
        return ComputationalInstance(
            role=InstanceRole(result["role"]),
            user_id=result["user_id"],
            wallet_id=result["wallet_id"],
            name=name,
            last_heartbeat=last_heartbeat,
            ec2_instance=instance,
            disk_space=UNDEFINED_BYTESIZE,
            dask_ip="unknown",
            is_warm_buffer=utils.get_warm_buffer_tag(instance),
        )

    return None


def _create_graylog_permalinks(environment: dict[str, str | None], instance: Instance) -> str:
    # https://monitoring.sim4life.io/graylog/search/6552235211aee4262e7f9f21?q=source%3A%22ip-10-0-1-67%22&rangetype=relative&from=28800
    source_name = instance.private_ip_address.replace(".", "-")
    time_span = int((arrow.utcnow().datetime - instance.launch_time + datetime.timedelta(hours=1)).total_seconds())
    return f"https://monitoring.{environment['MACHINE_FQDN']}/graylog/search?q=source%3A%22ip-{source_name}%22&rangetype=relative&from={time_span}"


def _parse_dynamic(state: AppState, instance: Instance) -> DynamicInstance | None:
    name = utils.get_instance_name(instance)
    if result := state.dynamic_parser.search(name):
        assert isinstance(result, parse.Result)

        return DynamicInstance(
            name=name,
            ec2_instance=instance,
            running_services=[],
            disk_space=UNDEFINED_BYTESIZE,
            is_warm_buffer=utils.get_warm_buffer_tag(instance),
        )
    return None


def _print_dynamic_instances(
    instances: list[DynamicInstance],
    environment: dict[str, str | None],
    aws_region: str,
    output: Path | None,
) -> None:
    time_now = arrow.utcnow()
    table = Table(
        Column("Instance"),
        Column(
            "Running services",
            footer="[red]Intervention detection might show false positive"
            " if in transient state, be careful and always double-check!![/red]",
        ),
        title=f"dynamic autoscaled instances: {aws_region}",
        show_footer=True,
        padding=(0, 0),
        title_style=Style(color="red", encircle=True),
    )
    for instance in track(instances, description="Preparing dynamic autoscaled instances details..."):
        service_table = "[i]n/a[/i]"
        if instance.running_services:
            service_table = Table(
                "UserID",
                "ProjectID",
                "NodeID",
                "ServiceName",
                "ServiceVersion",
                "ProductName",
                "Created Since",
                "Need intervention",
                expand=True,
                padding=(0, 0),
            )
            for service in instance.running_services:
                # Add robot emoji if simcore_user_agent is present (automated testing)
                user_id_display = f"{service.user_id}"
                if service.simcore_user_agent and service.simcore_user_agent.lower() != "undefined":
                    user_id_display = f"🤖 {service.user_id}"
                service_table.add_row(
                    user_id_display,
                    service.project_id,
                    service.node_id,
                    service.service_name,
                    service.service_version,
                    service.product_name,
                    utils.timedelta_formatting(time_now - service.created_at, color_code=True),
                    f"{'[red]' if service.needs_manual_intervention else ''}"
                    f"{service.needs_manual_intervention}{'[/red]' if service.needs_manual_intervention else ''}",
                )
        elif instance.is_warm_buffer:
            service_table = "[dim]warm buffer - no services running[/dim]"

        color_encoded_free_space = utils.color_encode_with_threshold(
            instance.disk_space.human_readable(), instance.disk_space, TypeAdapter(ByteSize).validate_python("15Gib")
        )
        instance_info = "\n".join(
            [
                f"{utils.color_encode_with_state(instance.name, instance.ec2_instance)}",
                f"ID: {instance.ec2_instance.instance_id}",
                f"AMI: {instance.ec2_instance.image_id}",
                f"Type: {instance.ec2_instance.instance_type}",
                f"Up: {utils.timedelta_formatting(time_now - instance.ec2_instance.launch_time, color_code=True)}",
                f"ExtIP: {instance.ec2_instance.public_ip_address}",
                f"IntIP: {instance.ec2_instance.private_ip_address}",
                f"/mnt/docker(free): {color_encoded_free_space}",
            ]
        )
        if instance.is_warm_buffer:
            instance_info = f"[dim]{instance_info}[/dim]"
        table.add_row(
            instance_info,
            service_table,
        )
        table.add_row(
            "",
            f"Graylog: {_create_graylog_permalinks(environment, instance.ec2_instance)}",
            end_section=True,
        )
    if output:
        with output.open("w") as fp:
            rich.print(table, flush=True, file=fp)
    else:
        rich.print(table, flush=True)


def _format_cluster_identity(
    user_id: int,
    wallet_id: int | None,
    *,
    email: str | None = None,
    wallet_name: str | None = None,
    product_name: str | None = None,
) -> str:
    wid = str(wallet_id) if wallet_id is not None else "n/a"
    identity = f"Cluster details for [bold cyan]UserID: {user_id}[/bold cyan]"
    if email:
        identity += f" [dim]({email})[/dim]"
    identity += f", [bold yellow]WalletID: {wid}[/bold yellow]"
    if wallet_name:
        identity += f" [dim]({wallet_name})[/dim]"
    if product_name:
        identity += f" — [dim]Product: {product_name}[/dim]"
    return identity


def _format_resource_value(key: str, value: float) -> str:
    if key in {"RAM", "VRAM"} and isinstance(value, (int, float)):
        return TypeAdapter(ByteSize).validate_python(int(value)).human_readable()
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _format_comp_task_cell(row: "TaskReconciliationRow") -> str:
    if row.comp_task is None:
        return "[red]\u274c n/a[/red]"
    db_state = row.comp_task.state
    if row.dask_state == "processing" and db_state != "RUNNING":
        return f"[red]\u2705 {db_state}[/red]"
    if db_state == "RUNNING":
        return f"[green]\u2705 {db_state}[/green]"
    return f"\u2705 {db_state}"


def _format_tracker_cells(
    row: "TaskReconciliationRow",
    time_now: "arrow.Arrow",
    usd_per_credit: float | None,
) -> tuple[str, str, str, str, str, str]:
    """Returns (rut_text, rate_text, elapsed_str, total_text, usd_text, heartbeat_text)."""
    if row.tracker_run is None:
        rut = "[red]\u274c n/a[/red]" if row.dask_state == "processing" else "[dim]\u274c n/a[/dim]"
        return rut, "n/a", "n/a", "n/a", "n/a", "n/a"
    cost = row.tracker_run.pricing_unit_cost
    rate = f"{cost:.1f}" if cost is not None else "n/a"
    now_naive = time_now.datetime.replace(tzinfo=None)
    elapsed_hours = (now_naive - row.tracker_run.started_at.replace(tzinfo=None)).total_seconds() / 3600
    elapsed = f"{elapsed_hours:.1f}h"
    total_credits = cost * elapsed_hours if cost is not None else None
    total = f"{total_credits:.1f}" if total_credits is not None else "n/a"
    usd = f"{total_credits * usd_per_credit:.2f}" if total_credits is not None and usd_per_credit is not None else "n/a"
    heartbeat_age = utils.timedelta_formatting(
        now_naive - row.tracker_run.last_heartbeat_at.replace(tzinfo=None), color_code=True
    )
    return "[green]\u2705 RUNNING[/green]", rate, elapsed, total, usd, heartbeat_age


def _build_cluster_tasks_table(
    rows: list[TaskReconciliationRow],
    job_to_worker: dict[str, str] | None = None,
    usd_per_credit: float | None = None,
) -> Table | None:
    if not rows:
        return None

    time_now = arrow.utcnow()

    def _worker_sort_key(r: TaskReconciliationRow) -> tuple[int, str]:
        label = (job_to_worker or {}).get(r.job_id, "")
        try:
            return (int(label.rsplit(None, 1)[-1]), r.job_id)
        except (ValueError, IndexError):
            return (999, r.job_id)

    sorted_rows = sorted(rows, key=_worker_sort_key)

    table = Table(
        Column("Job ID", overflow="fold"),
        Column("Worker", justify="center"),
        Column("Dask State", justify="center"),
        Column("DB\ncomp_tasks", justify="center"),
        Column("DB\nRUT", justify="center"),
        Column("RUT\nHeartbeat", justify="right"),
        Column("Resources", overflow="fold"),
        Column("Rate\n(💶/h)", justify="right"),
        Column("Elapsed", justify="right"),
        Column("Total\n(💶)", justify="right"),
        Column("Total\n(💲)", justify="right"),
        Column("Issues"),
        padding=(0, 1),
        expand=True,
    )

    for row in sorted_rows:
        job_id_display = row.job_id[:36] + "\u2026" if len(row.job_id) > 37 else row.job_id  # noqa: PLR2004

        if row.dask_state == "processing":
            dask_state_text = f"[green]{row.dask_state}[/green]"
        elif row.dask_state in {"erred", "not-in-dask"}:
            dask_state_text = f"[red]{row.dask_state}[/red]"
        else:
            dask_state_text = row.dask_state

        db_comp_tasks_text = _format_comp_task_cell(row)

        resources_text = (
            "\n".join(f"{k}: {_format_resource_value(k, v)}" for k, v in sorted(row.required_resources.items()))
            if row.required_resources
            else "[dim]n/a[/dim]"
        )

        rut_text, rate_text, elapsed_str, total_text, usd_text, heartbeat_text = _format_tracker_cells(
            row, time_now, usd_per_credit
        )

        issue_text = "\n".join(f"[red]{i}[/red]" for i in row.issues) if row.issues else "[green]OK[/green]"
        worker_text = (job_to_worker or {}).get(row.job_id, "[dim]n/a[/dim]")

        table.add_row(
            job_id_display,
            worker_text,
            dask_state_text,
            db_comp_tasks_text,
            rut_text,
            heartbeat_text,
            resources_text,
            rate_text,
            elapsed_str,
            total_text,
            usd_text,
            issue_text,
        )

    return table


def _build_worker_metrics_table(
    metrics: dict[str, Any] | str,
    graylog_link: str,
) -> Table:
    table = Table(
        Column(""),
        Column(""),
        padding=(0, 1),
        show_header=False,
        box=None,
        expand=True,
    )
    table.add_row("Graylog", graylog_link)
    resources: dict[str, Any] = metrics.get("resources", {}) if isinstance(metrics, dict) else {}
    if resources:
        resources_str = " | ".join(f"{k}: {_format_resource_value(k, v)}" for k, v in sorted(resources.items()))
        table.add_row("Resources", resources_str)
    task_counts: dict[str, Any] = metrics.get("tasks", {}) if isinstance(metrics, dict) else {}
    if task_counts:
        table.add_row("", "", end_section=True)
        for state, count in task_counts.items():
            color = "green" if state in {"executing", "memory"} else "dim"
            table.add_row(f"[{color}]{state}[/{color}]", f"[{color}]{count}[/{color}]")
    return table


def _build_worker_tasks_table(
    processing_jobs: list[str],
    task_resources: dict[str, dict[str, Any]],
) -> Table | None:
    if not processing_jobs:
        return None
    table = Table(
        Column("Job ID", overflow="fold"),
        Column("Worker State", justify="center"),
        Column("Resources", overflow="fold"),
        padding=(0, 1),
        expand=True,
    )
    for job_id in processing_jobs:
        resources = task_resources.get(job_id, {})
        resources_text = (
            " | ".join(f"{k}: {_format_resource_value(k, v)}" for k, v in sorted(resources.items()))
            if resources
            else "[dim]n/a[/dim]"
        )
        table.add_row(job_id, "[green]executing[/green]", resources_text)
    return table


def _build_cluster_links_table(
    environment: dict[str, str | None],
    cluster: ComputationalCluster,
) -> Table:
    table = Table(
        Column(""),
        Column(""),
        padding=(0, 1),
        show_header=False,
        box=None,
        expand=True,
    )
    ip = cluster.primary.ec2_instance.public_ip_address
    table.add_row("Dask Scheduler", f"http://{ip}:8787")
    table.add_row("Graylog", _create_graylog_permalinks(environment, cluster.primary.ec2_instance))
    table.add_row("Prometheus", f"http://{ip}:9090")
    return table


def _build_job_to_worker(cluster: ComputationalCluster) -> dict[str, str]:
    """Build a reverse mapping from job_id to human-readable worker label."""
    job_to_worker: dict[str, str] = {}
    for worker_name, job_ids in cluster.processing_jobs.items():
        for i, w in enumerate(cluster.workers):
            if w.dask_ip in worker_name:
                for job_id in job_ids:
                    job_to_worker[job_id] = f"Worker {i + 1}"
                break
    return job_to_worker


def _print_computational_clusters(
    clusters: list[ComputationalCluster],
    environment: dict[str, str | None],
    aws_region: str,
    output: Path | None,
    cluster_task_rows: dict[tuple[int, int | None], list[TaskReconciliationRow]] | None = None,
    cluster_extra_info: dict[tuple[int, int | None], tuple[str | None, str | None, str | None, float | None]]
    | None = None,
) -> None:
    time_now = arrow.utcnow()

    for cluster in track(clusters, "Collecting information about computational clusters..."):
        cluster_worker_metrics = dask.get_worker_metrics(cluster.scheduler_info)
        job_to_worker = _build_job_to_worker(cluster)

        extra = (cluster_extra_info or {}).get((cluster.primary.user_id, cluster.primary.wallet_id))
        email, wallet_name, product_name, usd_per_credit = extra if extra else (None, None, None, None)

        table = Table(
            Column("Instance", justify="left", overflow="fold", ratio=1),
            Column(
                _format_cluster_identity(
                    cluster.primary.user_id,
                    cluster.primary.wallet_id,
                    email=email,
                    wallet_name=wallet_name,
                    product_name=product_name,
                ),
                overflow="fold",
                ratio=3,
            ),
            title=f"computational cluster: {aws_region}",
            padding=(0, 0),
            title_style=Style(color="red", encircle=True),
            expand=True,
        )

        color_encoded_up_time = utils.timedelta_formatting(
            time_now - cluster.primary.ec2_instance.launch_time, color_code=True
        )
        color_encoded_heartbeat = (
            utils.timedelta_formatting(time_now - cluster.primary.last_heartbeat)
            if cluster.primary.last_heartbeat
            else "n/a"
        )
        color_encoded_free_docker_space = utils.color_encode_with_threshold(
            cluster.primary.disk_space.human_readable(),
            cluster.primary.disk_space,
            TypeAdapter(ByteSize).validate_python("15Gib"),
        )
        primary_info = "\n".join(
            [
                f"[bold]{utils.color_encode_with_state('Primary', cluster.primary.ec2_instance)}",
                f"{cluster.primary.name}",
                f"ID: {cluster.primary.ec2_instance.id}",
                f"AMI: {cluster.primary.ec2_instance.image_id}",
                f"Type: {cluster.primary.ec2_instance.instance_type}",
                f"Up: {color_encoded_up_time}",
                f"ExtIP: {cluster.primary.ec2_instance.public_ip_address}",
                f"IntIP: {cluster.primary.ec2_instance.private_ip_address}",
                f"DaskSchedulerIP: {cluster.primary.dask_ip}",
                f"Heartbeat: {color_encoded_heartbeat}",
                f"/mnt/docker(free): {color_encoded_free_docker_space}",
            ]
        )
        if cluster.primary.is_warm_buffer:
            primary_info = f"[dim]{primary_info}[/dim]"

        _tasks_table: Table | None = None
        if not cluster.primary.is_warm_buffer and cluster_task_rows is not None:
            _task_rows = cluster_task_rows.get((cluster.primary.user_id, cluster.primary.wallet_id))
            if _task_rows:
                _tasks_table = _build_cluster_tasks_table(
                    _task_rows, job_to_worker=job_to_worker, usd_per_credit=usd_per_credit
                )
        cluster_links_table = _build_cluster_links_table(environment, cluster)
        # Links always first, tasks table right below in the same cell if present
        right_content: object = (
            Group(cluster_links_table, _tasks_table) if _tasks_table is not None else cluster_links_table
        )
        table.add_row(primary_info, right_content)

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
                for worker_name, job_ids in cluster.processing_jobs.items()
                if worker.dask_ip in worker_name
                for job_id in job_ids
            ]
            table.add_row()
            color_encoded_free_docker_space = utils.color_encode_with_threshold(
                worker.disk_space.human_readable(), worker.disk_space, TypeAdapter(ByteSize).validate_python("15Gib")
            )
            indent = "  "
            worker_label = utils.color_encode_with_state(f"Worker {index + 1}", worker.ec2_instance)
            worker_up = utils.timedelta_formatting(time_now - worker.ec2_instance.launch_time, color_code=True)
            worker_info = "\n".join(
                [
                    f"{indent}[italic]{worker_label}[/italic]",
                    f"{indent}{worker.name}",
                    f"{indent}ID: {worker.ec2_instance.id}",
                    f"{indent}AMI: {worker.ec2_instance.image_id}",
                    f"{indent}Type: {worker.ec2_instance.instance_type}",
                    f"{indent}Up: {worker_up}",
                    f"{indent}ExtIP: {worker.ec2_instance.public_ip_address}",
                    f"{indent}IntIP: {worker.ec2_instance.private_ip_address}",
                    f"{indent}DaskWorkerIP: {worker.dask_ip}",
                    f"{indent}/mnt/docker(free): {color_encoded_free_docker_space}",
                    "",
                ]
            )
            if worker.is_warm_buffer:
                worker_info = f"[dim]{worker_info}[/dim]"
            worker_graylog = _create_graylog_permalinks(environment, worker.ec2_instance)
            metrics_table = _build_worker_metrics_table(worker_dask_metrics, worker_graylog)
            worker_tasks = _build_worker_tasks_table(worker_processing_jobs, cluster.task_resources)
            worker_right: object = Group(metrics_table, worker_tasks) if worker_tasks is not None else metrics_table
            table.add_row(worker_info, worker_right)

        if output:
            with output.open("a") as fp:
                rich.print(table, file=fp)
        else:
            rich.print(table)


async def _fetch_instance_details(
    state: AppState, instance: DynamicInstance, ssh_key_path: Path
) -> tuple[list[DynamicService] | BaseException, ByteSize | BaseException]:
    # Run both SSH operations concurrently for this instance
    running_services, disk_space = await asyncio.gather(
        ssh.list_running_dyn_services(
            state,
            instance.ec2_instance,
            SSH_USER_NAME,
            ssh_key_path,
        ),
        ssh.get_available_disk_space(state, instance.ec2_instance, SSH_USER_NAME, ssh_key_path),
        return_exceptions=True,
    )
    return running_services, disk_space


async def _analyze_dynamic_instances_running_services_concurrently(
    state: AppState,
    dynamic_instances: list[DynamicInstance],
    ssh_key_path: Path,
    user_id: int | None,
) -> list[DynamicInstance]:
    details = await asyncio.gather(
        *(_fetch_instance_details(state, instance, ssh_key_path) for instance in dynamic_instances),
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


async def _analyze_computational_instances(
    state: AppState,
    computational_instances: list[ComputationalInstance],
    ssh_key_path: Path | None,
) -> list[ComputationalCluster]:
    all_disk_spaces = [UNDEFINED_BYTESIZE] * len(computational_instances)
    if ssh_key_path is not None:
        all_disk_spaces = await asyncio.gather(
            *(
                ssh.get_available_disk_space(state, instance.ec2_instance, SSH_USER_NAME, ssh_key_path)
                for instance in computational_instances
            ),
            return_exceptions=True,
        )

        all_dask_ips = await asyncio.gather(
            *(
                ssh.get_dask_ip(state, instance.ec2_instance, SSH_USER_NAME, ssh_key_path)
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
            (
                scheduler_info,
                datasets_on_cluster,
                processing_jobs,
                all_tasks,
                task_resources,
            ) = await dask.get_scheduler_details(
                state,
                instance.ec2_instance,
            )

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
                    task_resources=task_resources,
                )
            )

    for instance in computational_instances:
        if instance.role is InstanceRole.worker:
            # assign the worker to correct cluster
            for cluster in computational_clusters:
                if cluster.primary.user_id == instance.user_id and cluster.primary.wallet_id == instance.wallet_id:
                    cluster.workers.append(instance)

    return computational_clusters


async def _parse_computational_clusters(
    state: AppState,
    instances: ServiceResourceInstancesCollection,
    ssh_key_path: Path | None,
    user_id: int | None,
    wallet_id: int | None,
) -> list[ComputationalCluster]:
    computational_instances = [
        comp_instance
        for instance in track(instances, description="Parsing computational instances...")
        if (comp_instance := await _parse_computational(state, instance))
        and (user_id is None or comp_instance.user_id == user_id)
        and (wallet_id is None or comp_instance.wallet_id == wallet_id)
    ]
    return await _analyze_computational_instances(state, computational_instances, ssh_key_path)


async def _parse_dynamic_instances(
    state: AppState,
    instances: ServiceResourceInstancesCollection,
    ssh_key_path: Path | None,
    user_id: int | None,
    wallet_id: int | None,  # noqa: ARG001
) -> list[DynamicInstance]:
    dynamic_instances = [
        dyn_instance
        for instance in track(instances, description="Parsing dynamic instances...")
        if (dyn_instance := _parse_dynamic(state, instance))
    ]

    if dynamic_instances and ssh_key_path:
        dynamic_instances = await _analyze_dynamic_instances_running_services_concurrently(
            state, dynamic_instances, ssh_key_path, user_id
        )
    return dynamic_instances


def _reconcile_cluster_tasks(
    cluster: ComputationalCluster,
    comp_tasks: list[ComputationalTask],
    tracker_runs: list[ResourceTrackerServiceRun],
) -> list[TaskReconciliationRow]:
    """Cross-reference Dask scheduler tasks with comp_tasks and resource_tracker entries.

    Flags:
    - Dask task not found in comp_tasks (ghost task)
    - Task being processed but comp_tasks.state != RUNNING
    - Processing task with no resource_tracker entry (credits not tracked)
    - comp_task in RUNNING/PUBLISHED state not present in Dask (stuck/orphaned)
    """
    comp_tasks_by_job_id: dict[TaskId, ComputationalTask] = {t.job_id: t for t in comp_tasks if t.job_id is not None}
    tracker_runs_by_node_id: dict[str, ResourceTrackerServiceRun] = {r.node_id: r for r in tracker_runs}

    rows: list[TaskReconciliationRow] = []
    dask_job_ids_seen: set[TaskId] = set()

    for dask_state, job_ids in cluster.task_states_to_tasks.items():
        for job_id in job_ids:
            dask_job_ids_seen.add(job_id)
            comp_task = comp_tasks_by_job_id.get(job_id)
            issues: list[str] = []

            if comp_task is None:
                issues.append("not found in comp_tasks (ghost task in cluster)")
                tracker_run = None
                required_resources: dict[str, Any] = cluster.task_resources.get(job_id, {})
            else:
                if dask_state == "processing" and comp_task.state != "RUNNING":
                    issues.append(f"processing in Dask but comp_tasks.state={comp_task.state!r} (expected RUNNING)")
                tracker_run = tracker_runs_by_node_id.get(str(comp_task.node_id))
                if tracker_run is None and dask_state == "processing":
                    issues.append("no resource_tracker entry (credits not being tracked)")
                required_resources = cluster.task_resources.get(job_id, {})

            rows.append(
                TaskReconciliationRow(
                    job_id=job_id,
                    dask_state=dask_state,
                    comp_task=comp_task,
                    tracker_run=tracker_run,
                    required_resources=required_resources,
                    issues=issues,
                )
            )

    # Orphaned DB tasks: RUNNING but absent from the Dask scheduler
    # (PUBLISHED is expected to not be in Dask yet — it is waiting to be picked up)
    for comp_task in comp_tasks:
        if comp_task.job_id not in dask_job_ids_seen and comp_task.state == "RUNNING":
            tracker_run = tracker_runs_by_node_id.get(str(comp_task.node_id))
            rows.append(
                TaskReconciliationRow(
                    job_id=comp_task.job_id or "n/a",
                    dask_state="not-in-dask",
                    comp_task=comp_task,
                    tracker_run=tracker_run,
                    required_resources=cluster.task_resources.get(comp_task.job_id or "", {}),
                    issues=["comp_tasks.state=RUNNING but job absent from Dask scheduler (stuck?)"],
                )
            )

    return rows


def _reconcile_clusters_with_tracker(
    clusters: list[ComputationalCluster],
    tracker_runs: list[ResourceTrackerServiceRun],
) -> list[TrackerReconciliationEntry]:
    """Cross-reference EC2 computational clusters with resource tracker DB entries.

    Groups both sides by (user_id, wallet_id) and flags:
    - EC2 cluster present but no RUNNING tracker entry (billing failure risk)
    - RUNNING tracker entries with no active EC2 cluster (ghost entries)
    - Stale heartbeat on a tracked-and-running cluster
    """
    stale_threshold = arrow.utcnow().shift(minutes=-STALE_HEARTBEAT_THRESHOLD_MINUTES).datetime

    cluster_map: dict[tuple[int, int | None], ComputationalCluster] = {
        (c.primary.user_id, c.primary.wallet_id): c for c in clusters
    }
    tracker_map: dict[tuple[int, int | None], list[ResourceTrackerServiceRun]] = {}
    for run in tracker_runs:
        key = (run.user_id, run.wallet_id)
        tracker_map.setdefault(key, []).append(run)

    all_keys = set(cluster_map) | set(tracker_map)
    entries: list[TrackerReconciliationEntry] = []
    for key in sorted(all_keys):
        user_id, wallet_id = key
        cluster = cluster_map.get(key)
        runs = tracker_map.get(key, [])
        issues: list[str] = []

        if cluster is not None and not runs:
            # Warm-buffer clusters do not run services, so tracker absence is expected
            if not cluster.primary.is_warm_buffer:
                issues.append("EC2 cluster not tracked in resource_tracker (potential billing failure)")
        elif not cluster and runs:
            issues.append("RUNNING tracker entries with no matching EC2 cluster (ghost entries)")
        elif cluster and runs:
            stale = [
                r
                for r in runs
                if r.last_heartbeat_at.replace(tzinfo=None) < stale_threshold.replace(tzinfo=None)
                or (
                    r.last_heartbeat_at.tzinfo is not None
                    and stale_threshold.tzinfo is not None
                    and r.last_heartbeat_at < stale_threshold
                )
            ]
            if stale:
                issues.append(
                    f"{len(stale)} tracker run(s) have stale heartbeat (>{STALE_HEARTBEAT_THRESHOLD_MINUTES} min)"
                )
            missed = [r for r in runs if r.missed_heartbeat_counter > 0]
            if missed:
                issues.append(f"{len(missed)} tracker run(s) have missed_heartbeat_counter > 0")

        entries.append(
            TrackerReconciliationEntry(
                user_id=user_id,
                wallet_id=wallet_id,
                ec2_cluster=cluster,
                tracker_runs=runs,
                issues=issues,
            )
        )
    return entries


def _print_tracker_reconciliation(
    entries: list[TrackerReconciliationEntry],
    output: Path | None,
) -> None:
    time_now = arrow.utcnow()
    table = Table(
        Column("Status", justify="center"),
        Column("UserID"),
        Column("WalletID"),
        Column("EC2 cluster", justify="center"),
        Column("Tracker RUNNING", justify="center"),
        Column("Last Heartbeat (newest)"),
        Column("Max Missed Heartbeats", justify="center"),
        Column("Issues"),
        title="Resource tracker reconciliation (computational clusters)",
        padding=(0, 1),
        title_style=Style(color="cyan", encircle=True),
    )

    for entry in entries:
        if entry.issues:
            status = "[red]\u274c[/red]"
            issue_text = "\n".join(f"[red]{i}[/red]" for i in entry.issues)
        else:
            status = "[green]\u2705[/green]"
            issue_text = "[green]OK[/green]"

        ec2_text = "[green]yes[/green]" if entry.ec2_cluster else "[red]no[/red]"
        tracker_count = f"{len(entry.tracker_runs)}"

        if entry.tracker_runs:
            newest_heartbeat = max(r.last_heartbeat_at for r in entry.tracker_runs)
            # strip tz for timedelta computation to avoid mixed-aware comparison issues
            newest_naive = newest_heartbeat.replace(tzinfo=None)
            now_naive = time_now.datetime.replace(tzinfo=None)
            heartbeat_age = utils.timedelta_formatting(now_naive - newest_naive, color_code=True)
            max_missed = max(r.missed_heartbeat_counter for r in entry.tracker_runs)
            missed_text = f"[red]{max_missed}[/red]" if max_missed > 0 else f"[green]{max_missed}[/green]"
        else:
            heartbeat_age = "n/a"
            missed_text = "n/a"

        table.add_row(
            status,
            f"{entry.user_id}",
            f"{entry.wallet_id}" if entry.wallet_id is not None else "n/a",
            ec2_text,
            tracker_count,
            heartbeat_age,
            missed_text,
            issue_text,
        )

    if output:
        with output.open("a") as fp:
            rich.print(table, file=fp)
    else:
        rich.print(table)


def _print_summary_as_json(
    dynamic_instances: list[DynamicInstance],
    computational_clusters: list[ComputationalCluster],
    output: Path | None,
    tracker_reconciliation: list[TrackerReconciliationEntry] | None = None,
    cluster_task_rows: list[tuple[ComputationalCluster, list[TaskReconciliationRow]]] | None = None,
) -> None:
    result = {
        "dynamic_instances": [
            {
                "name": instance.name,
                "ec2_instance_id": instance.ec2_instance.instance_id,
                "is_warm_buffer": instance.is_warm_buffer,
                "running_services": [
                    {
                        "user_id": service.user_id,
                        "project_id": service.project_id,
                        "node_id": service.node_id,
                        "service_name": service.service_name,
                        "service_version": service.service_version,
                        "product_name": service.product_name,
                        "simcore_user_agent": service.simcore_user_agent,
                        "created_at": service.created_at.isoformat(),
                        "needs_manual_intervention": service.needs_manual_intervention,
                    }
                    for service in instance.running_services
                ],
                "disk_space": instance.disk_space.human_readable(),
            }
            for instance in dynamic_instances
        ],
        "computational_clusters": [
            {
                "primary": {
                    "name": cluster.primary.name,
                    "ec2_instance_id": cluster.primary.ec2_instance.instance_id,
                    "is_warm_buffer": cluster.primary.is_warm_buffer,
                    "user_id": cluster.primary.user_id,
                    "wallet_id": cluster.primary.wallet_id,
                    "disk_space": cluster.primary.disk_space.human_readable(),
                    "last_heartbeat": (
                        cluster.primary.last_heartbeat.isoformat() if cluster.primary.last_heartbeat else "n/a"
                    ),
                },
                "workers": [
                    {
                        "name": worker.name,
                        "ec2_instance_id": worker.ec2_instance.instance_id,
                        "is_warm_buffer": worker.is_warm_buffer,
                        "disk_space": worker.disk_space.human_readable(),
                    }
                    for worker in cluster.workers
                ],
                "datasets": cluster.datasets,
                "tasks": cluster.task_states_to_tasks,
            }
            for cluster in computational_clusters
        ],
        "cluster_task_reconciliation": [
            {
                "user_id": cluster.primary.user_id,
                "wallet_id": cluster.primary.wallet_id,
                "tasks": [
                    {
                        "job_id": row.job_id,
                        "dask_state": row.dask_state,
                        "in_comp_tasks": row.comp_task is not None,
                        "db_state": row.comp_task.state if row.comp_task else None,
                        "project_id": str(row.comp_task.project_id) if row.comp_task else None,
                        "node_id": str(row.comp_task.node_id) if row.comp_task else None,
                        "service_name": row.comp_task.service_name if row.comp_task else None,
                        "service_version": row.comp_task.service_version if row.comp_task else None,
                        "in_tracker": row.tracker_run is not None,
                        "pricing_unit_cost": row.tracker_run.pricing_unit_cost if row.tracker_run else None,
                        "issues": row.issues,
                    }
                    for row in task_rows
                ],
            }
            for cluster, task_rows in (cluster_task_rows or [])
        ],
        "tracker_reconciliation": [
            {
                "user_id": entry.user_id,
                "wallet_id": entry.wallet_id,
                "has_ec2_cluster": entry.ec2_cluster is not None,
                "tracker_running_count": len(entry.tracker_runs),
                "tracker_runs": [
                    {
                        "service_run_id": r.service_run_id,
                        "product_name": r.product_name,
                        "project_id": r.project_id,
                        "node_id": r.node_id,
                        "service_key": r.service_key,
                        "service_version": r.service_version,
                        "started_at": r.started_at.isoformat(),
                        "last_heartbeat_at": r.last_heartbeat_at.isoformat(),
                        "missed_heartbeat_counter": r.missed_heartbeat_counter,
                    }
                    for r in entry.tracker_runs
                ],
                "issues": entry.issues,
            }
            for entry in (tracker_reconciliation or [])
        ],
    }

    if output:
        output.write_text(orjson.dumps(result).decode())
    else:
        rich.print_json(orjson.dumps(result).decode())


async def summary(
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
    *,
    output_json: bool,
    output: Path | None,
) -> bool:
    # get all the running instances
    assert state.ec2_resource_autoscaling
    dynamic_instances = await ec2.list_dynamic_instances_from_ec2(
        state,
        filter_by_user_id=user_id,
        filter_by_wallet_id=wallet_id,
        filter_by_instance_id=None,
    )
    dynamic_autoscaled_instances = await _parse_dynamic_instances(
        state, dynamic_instances, state.ssh_key_path, user_id, wallet_id
    )

    assert state.ec2_resource_clusters_keeper
    computational_instances = await ec2.list_computational_instances_from_ec2(state, user_id, wallet_id)
    computational_clusters = await _parse_computational_clusters(
        state, computational_instances, state.ssh_key_path, user_id, wallet_id
    )

    # --- Resource tracker reconciliation (read-only, graceful on DB failure) ---
    try:
        tracker_runs = await db.list_resource_tracker_running_computational_services(state)
    except Exception:  # pylint: disable=broad-exception-caught
        rich.print(
            "[yellow]Warning: could not query resource_tracker_service_runs "
            "(DB unreachable?). Skipping tracker reconciliation.[/yellow]"
        )
        tracker_runs = []

    # --- Per-cluster task reconciliation ---
    # tracker_runs grouped by user_id to pass only relevant runs per cluster
    tracker_runs_by_user_id: dict[int, list[ResourceTrackerServiceRun]] = {}
    for _run in tracker_runs:
        tracker_runs_by_user_id.setdefault(_run.user_id, []).append(_run)

    cluster_task_rows: list[tuple[ComputationalCluster, list[TaskReconciliationRow]]] = []
    for cluster in computational_clusters:
        try:
            comp_tasks = await db.list_computational_tasks_from_db(state, cluster.primary.user_id)
        except Exception:  # pylint: disable=broad-exception-caught
            rich.print(f"[yellow]Warning: could not fetch comp_tasks for user_id={cluster.primary.user_id}.[/yellow]")
            comp_tasks = []
        cluster_tracker_runs = tracker_runs_by_user_id.get(cluster.primary.user_id, [])
        task_rows = _reconcile_cluster_tasks(cluster, comp_tasks, cluster_tracker_runs)
        cluster_task_rows.append((cluster, task_rows))

    reconciliation_entries = _reconcile_clusters_with_tracker(computational_clusters, tracker_runs)

    # Fetch display info (email, wallet name, product, usd/credit) for each cluster
    cluster_extra_info: dict[tuple[int, int | None], tuple[str | None, str | None, str | None, float | None]] = {}
    for _cluster in computational_clusters:
        try:
            _email, _wallet_name = await db.get_user_and_wallet_info(
                state, _cluster.primary.user_id, _cluster.primary.wallet_id
            )
        except Exception:  # pylint: disable=broad-exception-caught
            _email, _wallet_name = None, None
        _cluster_tracker = tracker_runs_by_user_id.get(_cluster.primary.user_id, [])
        _product_name = next((r.product_name for r in _cluster_tracker), None)
        _usd_per_credit: float | None = None
        if _product_name:
            with contextlib.suppress(Exception):
                _usd_per_credit = await db.get_product_usd_per_credit(state, _product_name)
        cluster_extra_info[(_cluster.primary.user_id, _cluster.primary.wallet_id)] = (
            _email,
            _wallet_name,
            _product_name,
            _usd_per_credit,
        )

    if output_json:
        _print_summary_as_json(
            dynamic_autoscaled_instances,
            computational_clusters,
            output=output,
            tracker_reconciliation=reconciliation_entries,
            cluster_task_rows=cluster_task_rows,
        )

    if not output_json:
        _print_dynamic_instances(
            dynamic_autoscaled_instances,
            state.environment,
            state.ec2_resource_autoscaling.meta.client.meta.region_name,
            output=output,
        )
        _print_computational_clusters(
            computational_clusters,
            state.environment,
            state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
            output=output,
            cluster_task_rows={(c.primary.user_id, c.primary.wallet_id): rows for c, rows in cluster_task_rows},
            cluster_extra_info=cluster_extra_info,
        )

    time_threshold = arrow.utcnow().shift(minutes=-30).datetime
    dynamic_services_in_error = any(
        service.needs_manual_intervention and service.created_at < time_threshold
        for instance in dynamic_autoscaled_instances
        for service in instance.running_services
    )
    tracker_issues_found = any(
        entry.issues
        for entry in reconciliation_entries
        if entry.ec2_cluster is None or not entry.ec2_cluster.primary.is_warm_buffer
    )
    task_issues_found = any(row.issues for _, task_rows in cluster_task_rows for row in task_rows)

    return not dynamic_services_in_error and not tracker_issues_found and not task_issues_found


def _print_computational_tasks(
    user_id: int,
    wallet_id: int | None,
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
            (f"{db_task.project_id}" if db_task else "[red][bold]intervention needed[/bold][/red]"),
            f"{db_task.node_id}" if db_task else "",
            f"{db_task.service_name}" if db_task else "",
            f"{db_task.service_version}" if db_task else "",
            f"{db_task.state}" if db_task else "",
            (dask_task.state if dask_task else "[orange]task not yet in cluster[/orange]"),
        )

    rich.print(table)


async def _list_computational_clusters(
    state: AppState, user_id: int, wallet_id: int | None
) -> list[ComputationalCluster]:
    assert state.ec2_resource_clusters_keeper
    computational_instances = await ec2.list_computational_instances_from_ec2(state, user_id, wallet_id)
    return await _parse_computational_clusters(state, computational_instances, state.ssh_key_path, user_id, wallet_id)


async def _cancel_all_jobs(
    state: AppState,
    the_cluster: ComputationalCluster,
    *,
    task_to_dask_job: list[tuple[ComputationalTask | None, DaskTask | None]],
    abort_in_db: bool,
) -> None:
    rich.print("cancelling all tasks")
    for comp_task, dask_task in task_to_dask_job:
        if dask_task is not None and dask_task.state != "unknown":
            await dask.trigger_job_cancellation_in_scheduler(
                state,
                the_cluster,
                dask_task.job_id,
            )
            if comp_task is None:
                # we need to clear it of the cluster
                await dask.remove_job_from_scheduler(
                    state,
                    the_cluster,
                    dask_task.job_id,
                )
        if comp_task is not None and comp_task.state not in ["FAILED", "SUCCESS", "ABORTED"] and abort_in_db:
            await db.abort_job_in_db(state, comp_task.project_id, comp_task.node_id)

        rich.print("cancelled all tasks")


async def _get_job_id_to_dask_state_from_cluster(
    cluster: ComputationalCluster,
) -> dict[TaskId, TaskState]:
    job_id_to_dask_state: dict[TaskId, TaskState] = {}
    for job_state, job_ids in cluster.task_states_to_tasks.items():
        for job_id in job_ids:
            job_id_to_dask_state[job_id] = job_state
    return job_id_to_dask_state


async def _get_db_task_to_dask_job(
    computational_tasks: list[ComputationalTask],
    job_id_to_dask_state: dict[TaskId, TaskState],
) -> list[tuple[ComputationalTask | None, DaskTask | None]]:
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
    return task_to_dask_job


async def cancel_jobs(  # noqa: C901, PLR0912
    state: AppState, user_id: int, wallet_id: int | None, *, abort_in_db: bool
) -> None:
    # get the theory
    computational_tasks = await db.list_computational_tasks_from_db(state, user_id)

    # get the reality
    computational_clusters = await _list_computational_clusters(state, user_id, wallet_id)

    if computational_clusters:
        assert len(computational_clusters) == 1, (
            "too many clusters found! TIP: fix this code or something weird is playing out"
        )

        the_cluster = computational_clusters[0]
        rich.print(f"{the_cluster.task_states_to_tasks=}")

    job_id_to_dask_state = await _get_job_id_to_dask_state_from_cluster(the_cluster)
    task_to_dask_job: list[tuple[ComputationalTask | None, DaskTask | None]] = await _get_db_task_to_dask_job(
        computational_tasks, job_id_to_dask_state
    )

    if not task_to_dask_job:
        rich.print("[red]nothing found![/red]")
        raise typer.Exit

    _print_computational_tasks(user_id, wallet_id, task_to_dask_job)
    rich.print(the_cluster.datasets)
    try:
        if response := typer.prompt(
            "Which dataset to cancel? (all: will cancel everything, 1-5: "
            "will cancel jobs 1-5, or 4: will cancel job #4)",
            default="none",
        ):
            if response == "none":
                rich.print("[yellow]not cancelling anything[/yellow]")
            elif response == "all":
                await _cancel_all_jobs(
                    state,
                    the_cluster,
                    task_to_dask_job=task_to_dask_job,
                    abort_in_db=abort_in_db,
                )
            else:
                try:
                    # Split the response and handle ranges
                    indices = response.split("-")
                    if len(indices) == 2:  # noqa: PLR2004
                        start_index, end_index = map(int, indices)
                        selected_indices = range(start_index, end_index + 1)
                    else:
                        selected_indices = [int(indices[0])]

                    for selected_index in selected_indices:
                        comp_task, dask_task = task_to_dask_job[selected_index]
                        if dask_task is not None and dask_task.state != "unknown":
                            await dask.trigger_job_cancellation_in_scheduler(state, the_cluster, dask_task.job_id)
                            if comp_task is None:
                                # we need to clear it of the cluster
                                await dask.remove_job_from_scheduler(state, the_cluster, dask_task.job_id)

                        if comp_task is not None and abort_in_db:
                            await db.abort_job_in_db(state, comp_task.project_id, comp_task.node_id)
                    rich.print(f"Cancelled selected tasks: {response}")

                except ValidationError:
                    rich.print("[yellow]wrong index format, not cancelling anything[/yellow]")
                except IndexError:
                    rich.print("[yellow]index out of range, not cancelling anything[/yellow]")
    except ValidationError:
        rich.print("[yellow]wrong input, not cancelling anything[/yellow]")


async def trigger_cluster_termination(state: AppState, user_id: int, wallet_id: int | None, *, force: bool) -> None:
    assert state.ec2_resource_clusters_keeper
    computational_instances = await ec2.list_computational_instances_from_ec2(state, user_id, wallet_id)
    computational_clusters = await _parse_computational_clusters(
        state, computational_instances, state.ssh_key_path, user_id, wallet_id
    )
    assert computational_clusters
    assert len(computational_clusters) == 1, "too many clusters found! TIP: fix this code"

    _print_computational_clusters(
        computational_clusters,
        state.environment,
        state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
        output=None,
    )
    if (force is True) or typer.confirm("Are you sure you want to trigger termination of that cluster?"):
        the_cluster = computational_clusters[0]

        computational_tasks = await db.list_computational_tasks_from_db(state, user_id)
        job_id_to_dask_state = await _get_job_id_to_dask_state_from_cluster(the_cluster)
        task_to_dask_job: list[tuple[ComputationalTask | None, DaskTask | None]] = await _get_db_task_to_dask_job(
            computational_tasks, job_id_to_dask_state
        )
        await _cancel_all_jobs(state, the_cluster, task_to_dask_job=task_to_dask_job, abort_in_db=force)

        new_heartbeat_tag: TagTypeDef = {
            "Key": "last_heartbeat",
            "Value": f"{arrow.utcnow().datetime - datetime.timedelta(hours=1)}",
        }
        the_cluster.primary.ec2_instance.create_tags(Tags=[new_heartbeat_tag])
        rich.print(
            f"heartbeat tag on cluster of {user_id=}/{wallet_id=} changed,"
            " clusters-keeper will terminate that cluster soon."
        )
    else:
        rich.print("not deleting anything")


async def check_database_connection(state: AppState) -> None:
    await db.check_db_connection(state)


async def terminate_dynamic_instances(
    state: AppState,
    user_id: int | None,
    instance_id: str | None,
    *,
    force: bool,
) -> None:
    if not user_id and not instance_id:
        rich.print("either define user_id or instance_id!")
        raise typer.Exit(2)
    dynamic_instances = await ec2.list_dynamic_instances_from_ec2(
        state,
        filter_by_user_id=None,
        filter_by_wallet_id=None,
        filter_by_instance_id=instance_id,
    )

    dynamic_autoscaled_instances = await _parse_dynamic_instances(
        state, dynamic_instances, state.ssh_key_path, user_id, None
    )

    if not dynamic_autoscaled_instances:
        rich.print("no instances found")
        raise typer.Exit(1)

    assert state.ec2_resource_autoscaling  # nosec
    _print_dynamic_instances(
        dynamic_autoscaled_instances,
        state.environment,
        state.ec2_resource_autoscaling.meta.client.meta.region_name,
        output=None,
    )

    for instance in dynamic_autoscaled_instances:
        rich.print(
            f"terminating instance {instance.ec2_instance.instance_id} "
            f"with name {utils.get_instance_name(instance.ec2_instance)}"
        )
        if force is True or typer.confirm(
            f"Are you sure you want to terminate instance {instance.ec2_instance.instance_id}?"
        ):
            instance.ec2_instance.terminate()
            rich.print(f"terminated instance {instance.ec2_instance.instance_id}")
        else:
            rich.print("not terminating anything")

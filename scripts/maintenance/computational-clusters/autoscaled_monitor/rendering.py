"""Rich table rendering and JSON output for autoscaled-monitor."""

import datetime
from pathlib import Path
from typing import Any, Final

import arrow
import orjson
import rich
from mypy_boto3_ec2.service_resource import Instance
from pydantic import ByteSize, TypeAdapter
from rich.console import Group
from rich.progress import track
from rich.style import Style
from rich.table import Column, Table

from . import dask, utils
from .models import (
    ComputationalCluster,
    ComputationalTask,
    DaskTask,
    DynamicInstance,
    TaskReconciliationRow,
)


def create_graylog_permalinks(environment: dict[str, str | None], instance: Instance) -> str:
    source_name = instance.private_ip_address.replace(".", "-")
    time_span = int((arrow.utcnow().datetime - instance.launch_time + datetime.timedelta(hours=1)).total_seconds())
    return f"https://monitoring.{environment['MACHINE_FQDN']}/graylog/search?q=source%3A%22ip-{source_name}%22&rangetype=relative&from={time_span}"


def format_cluster_identity(
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


def format_resource_value(key: str, value: float | str | None) -> str:
    if key in {"RAM", "VRAM"} and isinstance(value, (int, float)):
        return TypeAdapter(ByteSize).validate_python(int(value)).human_readable()
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def format_comp_task_cell(row: TaskReconciliationRow) -> str:
    if row.comp_task is None:
        return "[red]\u274c n/a[/red]"
    db_state = row.comp_task.state
    if row.is_actively_executing and db_state != "RUNNING":
        return f"[red]\u2705 {db_state}[/red]"
    if db_state == "RUNNING":
        return f"[green]\u2705 {db_state}[/green]"
    return f"\u2705 {db_state}"


def format_tracker_cells(
    row: TaskReconciliationRow,
    time_now: arrow.Arrow,
    usd_per_credit: float | None,
) -> tuple[str, str, str, str, str, str]:
    """Returns (rut_text, rate_text, elapsed_str, total_text, usd_text, heartbeat_text)."""
    if row.tracker_run is None:
        rut = "[red]\u274c n/a[/red]" if row.is_actively_executing else "[dim]\u274c n/a[/dim]"
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


STATE_STYLES: Final[dict[str, str]] = {
    "executing": "green",
    "long-running": "green",
    "memory": "green",
    "constrained": "yellow",
    "queued": "cyan",
    "ready": "cyan",
    "waiting": "cyan",
    "fetch": "dim",
    "flight": "dim",
    "cancelled": "red",
    "error": "red",
    "missing": "red",
    "resumed": "yellow",
}


def build_cluster_tasks_table(
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
        Column("Rate\n(\U0001f4b6/h)", justify="right"),
        Column("Elapsed", justify="right"),
        Column("Total\n(\U0001f4b6)", justify="right"),
        Column("Total\n(\U0001f4b2)", justify="right"),
        Column("Issues"),
        padding=(0, 1),
        expand=True,
    )

    for row in sorted_rows:
        job_id_display = row.job_id[:36] + "\u2026" if len(row.job_id) > 37 else row.job_id  # noqa: PLR2004

        if row.worker_state and row.worker_state != row.dask_state:
            combined = f"{row.dask_state}\n{row.worker_state}"
        else:
            combined = row.dask_state

        if row.is_actively_executing:
            dask_state_text = f"[green]{combined}[/green]"
        elif row.dask_state == "processing":
            dask_state_text = f"[yellow]{combined}[/yellow]"
        elif row.dask_state in {"erred", "not-in-dask"}:
            dask_state_text = f"[red]{combined}[/red]"
        else:
            dask_state_text = combined

        db_comp_tasks_text = format_comp_task_cell(row)

        resources_text = (
            "\n".join(f"{k}: {format_resource_value(k, v)}" for k, v in sorted(row.required_resources.items()))
            if row.required_resources
            else "[dim]n/a[/dim]"
        )

        rut_text, rate_text, elapsed_str, total_text, usd_text, heartbeat_text = format_tracker_cells(
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


def build_worker_metrics_table(
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
        resources_str = " | ".join(f"{k}: {format_resource_value(k, v)}" for k, v in sorted(resources.items()))
        table.add_row("Resources", resources_str)
    return table


def build_worker_tasks_table(
    processing_jobs: list[str],
    task_resources: dict[str, dict[str, Any]],
    task_worker_states: dict[str, str],
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
            " | ".join(f"{k}: {format_resource_value(k, v)}" for k, v in sorted(resources.items()))
            if resources
            else "[dim]n/a[/dim]"
        )
        state = task_worker_states.get(job_id, "processing")
        color = STATE_STYLES.get(state, "dim")
        table.add_row(job_id, f"[{color}]{state}[/{color}]", resources_text)
    return table


def build_cluster_links_table(
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
    table.add_row("Graylog", create_graylog_permalinks(environment, cluster.primary.ec2_instance))
    table.add_row("Prometheus", f"http://{ip}:9090")
    return table


def build_job_to_worker(cluster: ComputationalCluster) -> dict[str, str]:
    """Build a reverse mapping from job_id to human-readable worker label."""
    job_to_worker: dict[str, str] = {}
    for worker_name, job_ids in cluster.processing_jobs.items():
        for i, w in enumerate(cluster.workers):
            if w.dask_ip in worker_name:
                for job_id in job_ids:
                    job_to_worker[job_id] = f"Worker {i + 1}"
                break
    return job_to_worker


def print_dynamic_instances(
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
                user_id_display = f"{service.user_id}"
                if service.simcore_user_agent and service.simcore_user_agent.lower() != "undefined":
                    user_id_display = f"\U0001f916 {service.user_id}"
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
            f"Graylog: {create_graylog_permalinks(environment, instance.ec2_instance)}",
            end_section=True,
        )
    if output:
        with output.open("w") as fp:
            rich.print(table, flush=True, file=fp)
    else:
        rich.print(table, flush=True)


def print_computational_clusters(  # noqa: C901
    clusters: list[ComputationalCluster],
    environment: dict[str, str | None],
    aws_region: str,
    output: Path | None,
    cluster_task_rows: dict[tuple[int, int | None], list[TaskReconciliationRow]] | None = None,
    cluster_extra_info: dict[tuple[int, int | None], tuple[str | None, str | None, str | None, float | None]]
    | None = None,
    *,
    compact: bool = False,
) -> None:
    """Print computational clusters.

    When compact=True, worker machine details (AMI, IPs, disk) are omitted —
    only worker count and task-level info are shown. Used by the top-level summary.
    """
    time_now = arrow.utcnow()

    for cluster in clusters:
        cluster_worker_metrics = dask.get_worker_metrics(cluster.scheduler_info)
        job_to_worker = build_job_to_worker(cluster)

        extra = (cluster_extra_info or {}).get((cluster.primary.user_id, cluster.primary.wallet_id))
        email, wallet_name, product_name, usd_per_credit = extra if extra else (None, None, None, None)

        table = Table(
            Column("Instance", justify="left", overflow="fold", ratio=1),
            Column(
                format_cluster_identity(
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
        dask_ip_display = cluster.primary.dask_ip
        if "Not Ready" in dask_ip_display:
            dask_ip_display = f"[red]{dask_ip_display}[/red]"
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
                f"DaskSchedulerIP: {dask_ip_display}",
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
                _tasks_table = build_cluster_tasks_table(
                    _task_rows, job_to_worker=job_to_worker, usd_per_credit=usd_per_credit
                )
        cluster_links_table = build_cluster_links_table(environment, cluster)
        right_content: object = (
            Group(cluster_links_table, _tasks_table) if _tasks_table is not None else cluster_links_table
        )
        table.add_row(primary_info, right_content)

        if compact:
            # In compact mode, just show worker count summary
            if cluster.workers:
                table.add_row()
                table.add_row(
                    f"  [italic]{len(cluster.workers)} worker(s)[/italic]",
                    "",
                )
        else:
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
                    worker.disk_space.human_readable(),
                    worker.disk_space,
                    TypeAdapter(ByteSize).validate_python("15Gib"),
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
                worker_graylog = create_graylog_permalinks(environment, worker.ec2_instance)
                metrics_table = build_worker_metrics_table(worker_dask_metrics, worker_graylog)
                worker_tasks = build_worker_tasks_table(
                    worker_processing_jobs, cluster.task_resources, cluster.task_worker_states
                )
                worker_right: object = Group(metrics_table, worker_tasks) if worker_tasks is not None else metrics_table
                table.add_row(worker_info, worker_right)

        if output:
            with output.open("a") as fp:
                rich.print(table, file=fp)
        else:
            rich.print(table)


def print_computational_tasks(
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


def print_summary_as_json(
    dynamic_instances: list[DynamicInstance],
    computational_clusters: list[ComputationalCluster],
    output: Path | None,
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
    }

    if output:
        output.write_text(orjson.dumps(result).decode())
    else:
        rich.print_json(orjson.dumps(result).decode())

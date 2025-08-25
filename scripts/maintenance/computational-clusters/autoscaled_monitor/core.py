#! /usr/bin/env python3

import asyncio
import datetime
import json
from dataclasses import replace
from pathlib import Path

import arrow
import parse
import rich
import typer
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from mypy_boto3_ec2.type_defs import TagTypeDef
from pydantic import ByteSize, TypeAdapter, ValidationError
from rich.progress import track
from rich.style import Style
from rich.table import Column, Table

from . import dask, db, ec2, ssh, utils
from .constants import SSH_USER_NAME, UNDEFINED_BYTESIZE
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


@utils.to_async
def _parse_computational(
    state: AppState, instance: Instance
) -> ComputationalInstance | None:
    name = utils.get_instance_name(instance)
    if result := (
        state.computational_parser_workers.parse(name)
        or state.computational_parser_primary.parse(name)
    ):
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


def _parse_dynamic(state: AppState, instance: Instance) -> DynamicInstance | None:
    name = utils.get_instance_name(instance)
    if result := state.dynamic_parser.search(name):
        assert isinstance(result, parse.Result)

        return DynamicInstance(
            name=name,
            ec2_instance=instance,
            running_services=[],
            disk_space=UNDEFINED_BYTESIZE,
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
                    utils.timedelta_formatting(
                        time_now - service.created_at, color_code=True
                    ),
                    f"{'[red]' if service.needs_manual_intervention else ''}{service.needs_manual_intervention}{'[/red]' if service.needs_manual_intervention else ''}",
                )

        table.add_row(
            "\n".join(
                [
                    f"{utils.color_encode_with_state(instance.name, instance.ec2_instance)}",
                    f"ID: {instance.ec2_instance.instance_id}",
                    f"AMI: {instance.ec2_instance.image_id}",
                    f"Type: {instance.ec2_instance.instance_type}",
                    f"Up: {utils.timedelta_formatting(time_now - instance.ec2_instance.launch_time, color_code=True)}",
                    f"ExtIP: {instance.ec2_instance.public_ip_address}",
                    f"IntIP: {instance.ec2_instance.private_ip_address}",
                    f"/mnt/docker(free): {utils.color_encode_with_threshold(instance.disk_space.human_readable(), instance.disk_space, TypeAdapter(ByteSize).validate_python('15Gib'))}",
                ]
            ),
            service_table,
        )
        table.add_row(
            "Graylog: ",
            f"{_create_graylog_permalinks(environment, instance.ec2_instance)}",
            end_section=True,
        )
    if output:
        with output.open("w") as fp:
            rich.print(table, flush=True, file=fp)
    else:
        rich.print(table, flush=True)


def _print_computational_clusters(
    clusters: list[ComputationalCluster],
    environment: dict[str, str | None],
    aws_region: str,
    output: Path | None,
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
        cluster_worker_metrics = dask.get_worker_metrics(cluster.scheduler_info)
        # first print primary machine info
        table.add_row(
            "\n".join(
                [
                    f"[bold]{utils.color_encode_with_state('Primary', cluster.primary.ec2_instance)}",
                    f"Name: {cluster.primary.name}",
                    f"ID: {cluster.primary.ec2_instance.id}",
                    f"AMI: {cluster.primary.ec2_instance.image_id}",
                    f"Type: {cluster.primary.ec2_instance.instance_type}",
                    f"Up: {utils.timedelta_formatting(time_now - cluster.primary.ec2_instance.launch_time, color_code=True)}",
                    f"ExtIP: {cluster.primary.ec2_instance.public_ip_address}",
                    f"IntIP: {cluster.primary.ec2_instance.private_ip_address}",
                    f"DaskSchedulerIP: {cluster.primary.dask_ip}",
                    f"UserID: {cluster.primary.user_id}",
                    f"WalletID: {cluster.primary.wallet_id}",
                    f"Heartbeat: {utils.timedelta_formatting(time_now - cluster.primary.last_heartbeat) if cluster.primary.last_heartbeat else 'n/a'}",
                    f"/mnt/docker(free): {utils.color_encode_with_threshold(cluster.primary.disk_space.human_readable(), cluster.primary.disk_space, TypeAdapter(ByteSize).validate_python('15Gib'))}",
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
                        f"[italic]{utils.color_encode_with_state(f'Worker {index + 1}', worker.ec2_instance)}[/italic]",
                        f"Name: {worker.name}",
                        f"ID: {worker.ec2_instance.id}",
                        f"AMI: {worker.ec2_instance.image_id}",
                        f"Type: {worker.ec2_instance.instance_type}",
                        f"Up: {utils.timedelta_formatting(time_now - worker.ec2_instance.launch_time, color_code=True)}",
                        f"ExtIP: {worker.ec2_instance.public_ip_address}",
                        f"IntIP: {worker.ec2_instance.private_ip_address}",
                        f"DaskWorkerIP: {worker.dask_ip}",
                        f"/mnt/docker(free): {utils.color_encode_with_threshold(worker.disk_space.human_readable(), worker.disk_space, TypeAdapter(ByteSize).validate_python('15Gib'))}",
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
        ssh.get_available_disk_space(
            state, instance.ec2_instance, SSH_USER_NAME, ssh_key_path
        ),
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
        *(
            _fetch_instance_details(state, instance, ssh_key_path)
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


async def _analyze_computational_instances(
    state: AppState,
    computational_instances: list[ComputationalInstance],
    ssh_key_path: Path | None,
) -> list[ComputationalCluster]:
    all_disk_spaces = [UNDEFINED_BYTESIZE] * len(computational_instances)
    if ssh_key_path is not None:
        all_disk_spaces = await asyncio.gather(
            *(
                ssh.get_available_disk_space(
                    state, instance.ec2_instance, SSH_USER_NAME, ssh_key_path
                )
                for instance in computational_instances
            ),
            return_exceptions=True,
        )

        all_dask_ips = await asyncio.gather(
            *(
                ssh.get_dask_ip(
                    state, instance.ec2_instance, SSH_USER_NAME, ssh_key_path
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
            (
                scheduler_info,
                datasets_on_cluster,
                processing_jobs,
                all_tasks,
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
    state: AppState,
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
        if (comp_instance := await _parse_computational(state, instance))
        and (user_id is None or comp_instance.user_id == user_id)
        and (wallet_id is None or comp_instance.wallet_id == wallet_id)
    ]
    return await _analyze_computational_instances(
        state, computational_instances, ssh_key_path
    )


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
        dynamic_instances = (
            await _analyze_dynamic_instances_running_services_concurrently(
                state, dynamic_instances, ssh_key_path, user_id
            )
        )
    return dynamic_instances


def _print_summary_as_json(
    dynamic_instances: list[DynamicInstance],
    computational_clusters: list[ComputationalCluster],
    output: Path | None,
) -> None:
    result = {
        "dynamic_instances": [
            {
                "name": instance.name,
                "ec2_instance_id": instance.ec2_instance.instance_id,
                "running_services": [
                    {
                        "user_id": service.user_id,
                        "project_id": service.project_id,
                        "node_id": service.node_id,
                        "service_name": service.service_name,
                        "service_version": service.service_version,
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
                    "user_id": cluster.primary.user_id,
                    "wallet_id": cluster.primary.wallet_id,
                    "disk_space": cluster.primary.disk_space.human_readable(),
                    "last_heartbeat": (
                        cluster.primary.last_heartbeat.isoformat()
                        if cluster.primary.last_heartbeat
                        else "n/a"
                    ),
                },
                "workers": [
                    {
                        "name": worker.name,
                        "ec2_instance_id": worker.ec2_instance.instance_id,
                        "disk_space": worker.disk_space.human_readable(),
                    }
                    for worker in cluster.workers
                ],
                "datasets": cluster.datasets,
                "tasks": cluster.task_states_to_tasks,
            }
            for cluster in computational_clusters
        ],
    }

    if output:
        output.write_text(json.dumps(result))
    else:
        rich.print_json(json.dumps(result))


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
    computational_instances = await ec2.list_computational_instances_from_ec2(
        state, user_id, wallet_id
    )
    computational_clusters = await _parse_computational_clusters(
        state, computational_instances, state.ssh_key_path, user_id, wallet_id
    )

    if output_json:
        _print_summary_as_json(
            dynamic_autoscaled_instances, computational_clusters, output=output
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
        )

    time_threshold = arrow.utcnow().shift(minutes=-30).datetime
    dynamic_services_in_error = any(
        service.needs_manual_intervention and service.created_at < time_threshold
        for instance in dynamic_autoscaled_instances
        for service in instance.running_services
    )

    return not dynamic_services_in_error


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
    state: AppState, user_id: int, wallet_id: int | None
) -> list[ComputationalCluster]:
    assert state.ec2_resource_clusters_keeper
    computational_instances = await ec2.list_computational_instances_from_ec2(
        state, user_id, wallet_id
    )
    return await _parse_computational_clusters(
        state, computational_instances, state.ssh_key_path, user_id, wallet_id
    )


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
        if (
            comp_task is not None
            and comp_task.state not in ["FAILED", "SUCCESS", "ABORTED"]
            and abort_in_db
        ):
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
    computational_clusters = await _list_computational_clusters(
        state, user_id, wallet_id
    )

    if computational_clusters:
        assert (
            len(computational_clusters) == 1
        ), "too many clusters found! TIP: fix this code or something weird is playing out"

        the_cluster = computational_clusters[0]
        rich.print(f"{the_cluster.task_states_to_tasks=}")

    job_id_to_dask_state = await _get_job_id_to_dask_state_from_cluster(the_cluster)
    task_to_dask_job: list[tuple[ComputationalTask | None, DaskTask | None]] = (
        await _get_db_task_to_dask_job(computational_tasks, job_id_to_dask_state)
    )

    if not task_to_dask_job:
        rich.print("[red]nothing found![/red]")
        raise typer.Exit

    _print_computational_tasks(user_id, wallet_id, task_to_dask_job)
    rich.print(the_cluster.datasets)
    try:
        if response := typer.prompt(
            "Which dataset to cancel? (all: will cancel everything, 1-5: will cancel jobs 1-5, or 4: will cancel job #4)",
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
                    if len(indices) == 2:
                        start_index, end_index = map(int, indices)
                        selected_indices = range(start_index, end_index + 1)
                    else:
                        selected_indices = [int(indices[0])]

                    for selected_index in selected_indices:
                        comp_task, dask_task = task_to_dask_job[selected_index]
                        if dask_task is not None and dask_task.state != "unknown":
                            await dask.trigger_job_cancellation_in_scheduler(
                                state, the_cluster, dask_task.job_id
                            )
                            if comp_task is None:
                                # we need to clear it of the cluster
                                await dask.remove_job_from_scheduler(
                                    state, the_cluster, dask_task.job_id
                                )

                        if comp_task is not None and abort_in_db:
                            await db.abort_job_in_db(
                                state, comp_task.project_id, comp_task.node_id
                            )
                    rich.print(f"Cancelled selected tasks: {response}")

                except ValidationError:
                    rich.print(
                        "[yellow]wrong index format, not cancelling anything[/yellow]"
                    )
                except IndexError:
                    rich.print(
                        "[yellow]index out of range, not cancelling anything[/yellow]"
                    )
    except ValidationError:
        rich.print("[yellow]wrong input, not cancelling anything[/yellow]")


async def trigger_cluster_termination(
    state: AppState, user_id: int, wallet_id: int | None, *, force: bool
) -> None:
    assert state.ec2_resource_clusters_keeper
    computational_instances = await ec2.list_computational_instances_from_ec2(
        state, user_id, wallet_id
    )
    computational_clusters = await _parse_computational_clusters(
        state, computational_instances, state.ssh_key_path, user_id, wallet_id
    )
    assert computational_clusters
    assert (
        len(computational_clusters) == 1
    ), "too many clusters found! TIP: fix this code"

    _print_computational_clusters(
        computational_clusters,
        state.environment,
        state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
        output=None,
    )
    if (force is True) or typer.confirm(
        "Are you sure you want to trigger termination of that cluster?"
    ):
        the_cluster = computational_clusters[0]

        computational_tasks = await db.list_computational_tasks_from_db(state, user_id)
        job_id_to_dask_state = await _get_job_id_to_dask_state_from_cluster(the_cluster)
        task_to_dask_job: list[tuple[ComputationalTask | None, DaskTask | None]] = (
            await _get_db_task_to_dask_job(computational_tasks, job_id_to_dask_state)
        )
        await _cancel_all_jobs(
            state, the_cluster, task_to_dask_job=task_to_dask_job, abort_in_db=force
        )

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
            f"terminating instance {instance.ec2_instance.instance_id} with name {utils.get_instance_name(instance.ec2_instance)}"
        )
        if force is True or typer.confirm(
            f"Are you sure you want to terminate instance {instance.ec2_instance.instance_id}?"
        ):
            instance.ec2_instance.terminate()
            rich.print(f"terminated instance {instance.ec2_instance.instance_id}")
        else:
            rich.print("not terminating anything")

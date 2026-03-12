"""Instance parsing, SSH introspection, and Dask data collection."""

import asyncio
import contextlib
from dataclasses import replace
from pathlib import Path

import asyncssh
import parse
import rich
from mypy_boto3_ec2.service_resource import Instance, ServiceResourceInstancesCollection
from pydantic import ByteSize
from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncEngine

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

console = Console()


@utils.to_async
def parse_computational(state: AppState, instance: Instance) -> ComputationalInstance | None:
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


def parse_dynamic(state: AppState, instance: Instance) -> DynamicInstance | None:
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


async def _fetch_instance_details(
    state: AppState,
    instance: DynamicInstance,
    ssh_key_path: Path,
    *,
    bastion_conn: asyncssh.SSHClientConnection | None,
) -> tuple[list[DynamicService] | BaseException, ByteSize | BaseException]:
    running_services, disk_space = await asyncio.gather(
        ssh.list_running_dyn_services(
            state,
            instance.ec2_instance,
            SSH_USER_NAME,
            ssh_key_path,
            bastion_conn=bastion_conn,
        ),
        ssh.get_available_disk_space(
            state,
            instance.ec2_instance,
            SSH_USER_NAME,
            ssh_key_path,
            bastion_conn=bastion_conn,
        ),
        return_exceptions=True,
    )
    return running_services, disk_space


async def analyze_dynamic_instances(
    state: AppState,
    dynamic_instances: list[DynamicInstance],
    ssh_key_path: Path,
    user_id: int | None,
) -> list[DynamicInstance]:
    bastion_conn: asyncssh.SSHClientConnection | None = None
    async with contextlib.AsyncExitStack() as stack:
        try:
            bastion_instance = await ec2.get_dynamic_bastion_instance(state)
            bastion_conn = await stack.enter_async_context(
                ssh.connect_bastion(
                    bastion_instance,
                    username=SSH_USER_NAME,
                    private_key_path=ssh_key_path,
                )
            )
        except (AssertionError, asyncssh.Error, OSError):
            console.log("[yellow]No dynamic bastion available, SSH operations will use per-instance fallback[/yellow]")

        with console.status(
            f"[bold]Fetching details for {len(dynamic_instances)} dynamic instance(s) via SSH...[/bold]"
        ):
            details = await asyncio.gather(
                *(
                    _fetch_instance_details(state, instance, ssh_key_path, bastion_conn=bastion_conn)
                    for instance in dynamic_instances
                ),
                return_exceptions=True,
            )
        console.log(f"Fetched details for {len(dynamic_instances)} dynamic instance(s) via SSH")

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


async def analyze_computational_instances(  # noqa: C901
    state: AppState,
    computational_instances: list[ComputationalInstance],
    ssh_key_path: Path | None,
) -> list[ComputationalCluster]:
    all_disk_spaces: list[ByteSize | BaseException] = [UNDEFINED_BYTESIZE] * len(computational_instances)
    all_dask_ips: list[str | BaseException] = [""] * len(computational_instances)

    async with contextlib.AsyncExitStack() as stack:
        bastion_conn: asyncssh.SSHClientConnection | None = None
        if ssh_key_path is not None:
            try:
                bastion_instance = await ec2.get_computational_bastion_instance(state)
                bastion_conn = await stack.enter_async_context(
                    ssh.connect_bastion(
                        bastion_instance,
                        username=SSH_USER_NAME,
                        private_key_path=ssh_key_path,
                    )
                )
            except (AssertionError, asyncssh.Error, OSError):
                console.log(
                    "[yellow]No computational bastion available, SSH operations will use per-instance fallback[/yellow]"
                )

            if computational_instances:
                with console.status(
                    f"[bold]Fetching disk space for {len(computational_instances)} computational instance(s)...[/bold]"
                ):
                    all_disk_spaces = await asyncio.gather(
                        *(
                            ssh.get_available_disk_space(
                                state,
                                instance.ec2_instance,
                                SSH_USER_NAME,
                                ssh_key_path,
                                bastion_conn=bastion_conn,
                            )
                            for instance in computational_instances
                        ),
                        return_exceptions=True,
                    )

                with console.status(
                    f"[bold]Fetching Dask IPs for {len(computational_instances)} computational instance(s)...[/bold]"
                ):
                    all_dask_ips = await asyncio.gather(
                        *(
                            ssh.get_dask_ip(
                                state,
                                instance.ec2_instance,
                                SSH_USER_NAME,
                                ssh_key_path,
                                bastion_conn=bastion_conn,
                            )
                            for instance in computational_instances
                        ),
                        return_exceptions=True,
                    )
                console.log(f"Fetched SSH details for {len(computational_instances)} computational instance(s)")

        computational_clusters = []
        for instance, disk_space, dask_ip in zip(computational_instances, all_disk_spaces, all_dask_ips, strict=True):
            if isinstance(disk_space, ByteSize):
                instance.disk_space = disk_space
            if isinstance(dask_ip, str):
                instance.dask_ip = dask_ip
            if instance.role is InstanceRole.manager:
                with console.status(f"[bold]Fetching Dask scheduler details for {instance.name}...[/bold]"):
                    (
                        scheduler_info,
                        datasets_on_cluster,
                        processing_jobs,
                        all_tasks,
                        task_resources,
                        task_worker_states,
                    ) = await dask.get_scheduler_details(
                        state,
                        instance.ec2_instance,
                        bastion_conn,
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
                        task_worker_states=task_worker_states,
                    )
                )

    for instance in computational_instances:
        if instance.role is InstanceRole.worker:
            for cluster in computational_clusters:
                if cluster.primary.user_id == instance.user_id and cluster.primary.wallet_id == instance.wallet_id:
                    cluster.workers.append(instance)

    console.log(f"Found {len(computational_clusters)} computational cluster(s)")
    return computational_clusters


async def parse_computational_clusters(
    state: AppState,
    instances: ServiceResourceInstancesCollection,
    ssh_key_path: Path | None,
    user_id: int | None,
    wallet_id: int | None,
) -> list[ComputationalCluster]:
    computational_instances = [
        comp_instance
        for instance in instances
        if (comp_instance := await parse_computational(state, instance))
        and (user_id is None or comp_instance.user_id == user_id)
        and (wallet_id is None or comp_instance.wallet_id == wallet_id)
    ]
    console.log(f"Parsed {len(computational_instances)} computational instance(s)")
    return await analyze_computational_instances(state, computational_instances, ssh_key_path)


async def parse_dynamic_instances(
    state: AppState,
    instances: ServiceResourceInstancesCollection,
    ssh_key_path: Path | None,
    user_id: int | None,
    wallet_id: int | None,  # noqa: ARG001
) -> list[DynamicInstance]:
    dynamic_instances = [dyn_instance for instance in instances if (dyn_instance := parse_dynamic(state, instance))]
    console.log(f"Parsed {len(dynamic_instances)} dynamic instance(s)")

    if dynamic_instances and ssh_key_path:
        dynamic_instances = await analyze_dynamic_instances(state, dynamic_instances, ssh_key_path, user_id)
    return dynamic_instances


async def list_computational_clusters(
    state: AppState, user_id: int, wallet_id: int | None
) -> list[ComputationalCluster]:
    assert state.ec2_resource_clusters_keeper
    computational_instances = await ec2.list_computational_instances_from_ec2(state, user_id, wallet_id)
    return await parse_computational_clusters(state, computational_instances, state.ssh_key_path, user_id, wallet_id)


async def get_job_id_to_dask_state_from_cluster(
    cluster: ComputationalCluster,
) -> dict[TaskId, TaskState]:
    job_id_to_dask_state: dict[TaskId, TaskState] = {}
    for job_state, job_ids in cluster.task_states_to_tasks.items():
        for job_id in job_ids:
            job_id_to_dask_state[job_id] = job_state
    return job_id_to_dask_state


async def get_db_task_to_dask_job(
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
    for job_id, dask_state in job_id_to_dask_state.items():
        task_to_dask_job.append((None, DaskTask(job_id=job_id, state=dask_state)))
    return task_to_dask_job


async def cancel_all_jobs(
    state: AppState,
    the_cluster: ComputationalCluster,
    *,
    task_to_dask_job: list[tuple[ComputationalTask | None, DaskTask | None]],
    abort_in_db: bool,
    engine: AsyncEngine | None = None,
    bastion_conn: asyncssh.SSHClientConnection | None,
) -> None:
    rich.print("cancelling all tasks")
    for comp_task, dask_task in task_to_dask_job:
        if dask_task is not None and dask_task.state != "unknown":
            await dask.trigger_job_cancellation_in_scheduler(
                state,
                the_cluster,
                dask_task.job_id,
                bastion_conn,
            )
            if comp_task is None:
                await dask.remove_job_from_scheduler(
                    state,
                    the_cluster,
                    dask_task.job_id,
                    bastion_conn,
                )
        if comp_task is not None and comp_task.state not in ["FAILED", "SUCCESS", "ABORTED"] and abort_in_db:
            assert engine is not None  # nosec
            await db.abort_job_in_db(engine, comp_task.project_id, comp_task.node_id)

        rich.print("cancelled all tasks")

"""Reconciliation logic between Dask scheduler, comp_tasks DB, and resource tracker."""

import contextlib
import dataclasses
from typing import Any

import rich
from sqlalchemy.ext.asyncio import AsyncEngine

from . import db
from .models import (
    AppState,
    ComputationalCluster,
    ComputationalTask,
    ResourceTrackerServiceRun,
    TaskId,
    TaskReconciliationRow,
)


def reconcile_cluster_tasks(  # noqa: C901, PLR0912
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

            worker_state = cluster.task_worker_states.get(job_id, dask_state)
            actively_executing = worker_state in {"executing", "long-running"}

            if comp_task is None:
                issues.append("not found in comp_tasks (ghost task in cluster)")
                tracker_run = None
                required_resources: dict[str, Any] = cluster.task_resources.get(job_id, {})
            else:
                worker_state = cluster.task_worker_states.get(job_id, dask_state)
                actively_executing = worker_state in {"executing", "long-running"}
                if actively_executing and comp_task.state != "RUNNING":
                    issues.append(f"executing in Dask but comp_tasks.state={comp_task.state!r} (expected RUNNING)")
                tracker_run = tracker_runs_by_node_id.get(str(comp_task.node_id))
                if tracker_run is None and actively_executing:
                    issues.append("no resource_tracker entry (credits not being tracked)")
                required_resources = cluster.task_resources.get(job_id, {})

            rows.append(
                TaskReconciliationRow(
                    job_id=job_id,
                    dask_state=dask_state,
                    worker_state=cluster.task_worker_states.get(job_id, dask_state),
                    comp_task=comp_task,
                    tracker_run=tracker_run,
                    required_resources=required_resources,
                    issues=issues,
                )
            )

    # Orphaned DB tasks: RUNNING but absent from the Dask scheduler
    for comp_task in comp_tasks:
        if comp_task.job_id not in dask_job_ids_seen and comp_task.state == "RUNNING":
            tracker_run = tracker_runs_by_node_id.get(str(comp_task.node_id))
            rows.append(
                TaskReconciliationRow(
                    job_id=comp_task.job_id or "n/a",
                    dask_state="not-in-dask",
                    worker_state="not-in-dask",
                    comp_task=comp_task,
                    tracker_run=tracker_run,
                    required_resources=cluster.task_resources.get(comp_task.job_id or "", {}),
                    issues=["comp_tasks.state=RUNNING but job absent from Dask scheduler (stuck?)"],
                )
            )

    # Detect load imbalance: all processing tasks on one worker while others are idle
    num_workers = len(cluster.workers)
    if num_workers > 1:
        tasks_per_worker: dict[str, int] = {}
        for worker_name, job_ids in cluster.processing_jobs.items():
            if job_ids:
                tasks_per_worker[worker_name] = len(job_ids)
        total_processing = sum(tasks_per_worker.values())
        workers_with_tasks = len(tasks_per_worker)
        if total_processing > 1 and workers_with_tasks == 1:
            busy_worker_name = next(iter(tasks_per_worker))
            busy_label = busy_worker_name
            for i, w in enumerate(cluster.workers):
                if w.dask_ip in busy_worker_name:
                    busy_label = f"Worker {i + 1}"
                    break
            imbalance_msg = (
                f"load imbalance: all {total_processing} tasks on {busy_label}, {num_workers - 1} idle worker(s)"
            )
            for row in rows:
                if row.job_id in cluster.processing_jobs.get(busy_worker_name, []):
                    row.issues.append(imbalance_msg)

    return rows


@dataclasses.dataclass
class ReconciliationResult:
    tracker_runs: list[ResourceTrackerServiceRun] = dataclasses.field(default_factory=list)
    cluster_task_rows: list[tuple[ComputationalCluster, list[TaskReconciliationRow]]] = dataclasses.field(
        default_factory=list
    )
    cluster_extra_info: dict[tuple[int, int | None], tuple[str | None, str | None, str | None, float | None]] = (
        dataclasses.field(default_factory=dict)
    )


async def reconcile_computational_clusters(
    state: AppState,
    computational_clusters: list[ComputationalCluster],
    engine: AsyncEngine | None = None,
) -> ReconciliationResult:
    """Reconcile computational clusters with resource tracker and DB data."""
    result = ReconciliationResult()
    try:
        async with contextlib.AsyncExitStack() as stack:
            if engine is None:
                engine = await stack.enter_async_context(db.db_engine(state))
            result.tracker_runs = await db.list_resource_tracker_running_computational_services(engine)

            tracker_runs_by_key: dict[tuple[int, int | None], list[ResourceTrackerServiceRun]] = {}
            for _run in result.tracker_runs:
                tracker_runs_by_key.setdefault((_run.user_id, _run.wallet_id), []).append(_run)

            for cluster in computational_clusters:
                try:
                    comp_tasks = await db.list_computational_tasks_from_db(engine, cluster.primary.user_id)
                except Exception:  # pylint: disable=broad-exception-caught
                    rich.print(
                        f"[yellow]Warning: could not fetch comp_tasks for user_id={cluster.primary.user_id}.[/yellow]"
                    )
                    comp_tasks = []
                _cluster_key = (cluster.primary.user_id, cluster.primary.wallet_id)
                cluster_tracker_runs = tracker_runs_by_key.get(_cluster_key, [])
                task_rows = reconcile_cluster_tasks(cluster, comp_tasks, cluster_tracker_runs)
                result.cluster_task_rows.append((cluster, task_rows))

            for _cluster in computational_clusters:
                try:
                    _email, _wallet_name, _product_name = await db.get_user_and_wallet_info(
                        engine, _cluster.primary.user_id, _cluster.primary.wallet_id
                    )
                except Exception:  # pylint: disable=broad-exception-caught
                    _email, _wallet_name, _product_name = None, None, None
                _cluster_key = (_cluster.primary.user_id, _cluster.primary.wallet_id)
                _cluster_tracker = tracker_runs_by_key.get(_cluster_key, [])
                if _product_name is None:
                    _product_name = next((r.product_name for r in _cluster_tracker), None)
                _usd_per_credit: float | None = None
                if _product_name:
                    with contextlib.suppress(Exception):
                        _usd_per_credit = await db.get_product_usd_per_credit(engine, _product_name)
                result.cluster_extra_info[(_cluster.primary.user_id, _cluster.primary.wallet_id)] = (
                    _email,
                    _wallet_name,
                    _product_name,
                    _usd_per_credit,
                )
    except Exception:  # pylint: disable=broad-exception-caught
        rich.print("[yellow]Warning: could not query database (DB unreachable?). Skipping DB reconciliation.[/yellow]")
    return result

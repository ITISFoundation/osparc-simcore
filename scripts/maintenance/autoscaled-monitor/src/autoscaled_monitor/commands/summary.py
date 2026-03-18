"""Top-level ``summary`` command — compact overview of both dynamic and computational."""

import asyncio
import contextlib
import time
from pathlib import Path
from typing import Annotated

import arrow
import rich
import typer
from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncEngine

from .. import db, rendering
from .._helpers import collect_services, load_computational_clusters, load_dynamic_instances
from .._state import state
from ..models import AppState, ComputationalCluster, DynamicInstance, DynamicServiceExtraInfo
from ..reconciliation import ReconciliationResult, reconcile_computational_clusters

_console = Console()


async def _run(  # noqa: C901, PLR0915
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
    *,
    output_json: bool,
    output: Path | None,
) -> bool:
    dynamic_autoscaled_instances: list[DynamicInstance] = []
    computational_clusters: list[ComputationalCluster] = []

    t0 = time.monotonic()

    # --- Phase 1: EC2 listing + SSH/Dask analysis + DB tunnel (all in parallel) ---
    async def _dynamic_phase() -> list[DynamicInstance]:
        if not state.ec2_resource_autoscaling:
            return []
        return await load_dynamic_instances(state, user_id, wallet_id, instance_id=None)

    async def _computational_phase() -> list[ComputationalCluster]:
        if not state.ec2_resource_clusters_keeper:
            return []
        return await load_computational_clusters(state, user_id, wallet_id)

    # DB engine — opened in parallel, cleaned up in finally block
    db_stack = contextlib.AsyncExitStack()
    db_engine: AsyncEngine | None = None

    async def _db_phase() -> AsyncEngine | None:
        """Open DB engine early so it overlaps with SSH work."""
        try:
            t1 = time.monotonic()
            engine = await db_stack.enter_async_context(db.db_engine(state))
            _console.log(f"[dim]  DB engine ready (SSH tunnel): {time.monotonic() - t1:.1f}s[/dim]")
            return engine
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    # Run SSH phases and DB tunnel setup concurrently
    dyn_result, comp_result, db_engine = await asyncio.gather(
        _dynamic_phase(),
        _computational_phase(),
        _db_phase(),
    )
    dynamic_autoscaled_instances = dyn_result
    computational_clusters = comp_result

    # --- Phase 2: DB queries using shared engine ---
    recon = ReconciliationResult()
    service_extra_info: dict[tuple[str, str], DynamicServiceExtraInfo] = {}
    services = collect_services(dynamic_autoscaled_instances)
    try:
        if db_engine is not None:
            with _console.status("[bold]Querying database...[/bold]"):
                if computational_clusters:
                    t2 = time.monotonic()
                    recon = await reconcile_computational_clusters(computational_clusters, engine=db_engine)
                    _console.log(f"[dim]  Reconciliation queries: {time.monotonic() - t2:.1f}s[/dim]")
                if services:
                    t2 = time.monotonic()
                    service_extra_info = await db.get_dynamic_service_extra_info(db_engine, services=services)
                    _console.log(f"[dim]  Dynamic extra info queries: {time.monotonic() - t2:.1f}s[/dim]")
        elif bool(computational_clusters) or bool(services):
            rich.print("[yellow]Warning: could not query DB.[/yellow]")
    except Exception as _exc:  # pylint: disable=broad-exception-caught
        rich.print(f"[yellow]Warning: could not query DB: {_exc!r}[/yellow]")
    finally:
        await db_stack.aclose()

    _console.log(f"[dim]Total elapsed: {time.monotonic() - t0:.1f}s[/dim]")

    if output_json:
        rendering.print_summary_as_json(
            dynamic_autoscaled_instances,
            computational_clusters,
            output=output,
            cluster_task_rows=recon.cluster_task_rows,
        )
    else:
        if state.ec2_resource_autoscaling:
            rendering.print_dynamic_instances(
                dynamic_autoscaled_instances,
                state.environment,
                state.ec2_resource_autoscaling.meta.client.meta.region_name,
                output=output,
                service_extra_info=service_extra_info,
            )
        if state.ec2_resource_clusters_keeper:
            rendering.print_computational_clusters(
                computational_clusters,
                state.environment,
                state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
                output=output,
                cluster_task_rows={
                    (c.primary.user_id, c.primary.wallet_id): rows for c, rows in recon.cluster_task_rows
                },
                cluster_extra_info=recon.cluster_extra_info,
                compact=True,
            )

        rich.print()
        rich.print("[dim]For more details, run:[/dim]")
        if state.ec2_resource_autoscaling:
            rich.print("[dim]  autoscaled-monitor ... dynamic summary[/dim]")
        if state.ec2_resource_clusters_keeper:
            rich.print("[dim]  autoscaled-monitor ... computational summary[/dim]")
        rich.print("[dim]  autoscaled-monitor ... db check[/dim]")

    time_threshold = arrow.utcnow().shift(minutes=-30).datetime
    dynamic_services_in_error = any(
        service.needs_manual_intervention and service.created_at < time_threshold
        for instance in dynamic_autoscaled_instances
        for service in instance.running_services
    )
    task_issues_found = any(row.issues for _, task_rows in recon.cluster_task_rows for row in task_rows)

    return not dynamic_services_in_error and not task_issues_found


def summary(
    *,
    user_id: Annotated[int, typer.Option(help="filters by the user ID")] = 0,
    wallet_id: Annotated[int, typer.Option(help="filters by the wallet ID")] = 0,
    as_json: Annotated[bool, typer.Option(help="outputs as json")] = False,
    output: Annotated[Path | None, typer.Option(help="outputs to a file")] = None,
) -> None:
    """Compact overview of all dynamic and computational instances.

    Shows dynamic instances with their services and computational clusters
    with task-level details but without per-worker machine info.
    """

    if not asyncio.run(
        _run(
            state,
            user_id or None,
            wallet_id or None,
            output_json=as_json,
            output=output,
        )
    ):
        raise typer.Exit(1)

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


async def _run(  # noqa: C901, PLR0912, PLR0915
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
    *,
    output_json: bool,
    output: Path | None,
    show_buffers: bool,
    use_profile: str | None,
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

    # Run SSH phases first; DB tunnel setup is deferred until needed
    dynamic_autoscaled_instances, computational_clusters = await asyncio.gather(
        _dynamic_phase(),
        _computational_phase(),
    )

    # DB engine — opened lazily and cleaned up in finally block
    db_stack = contextlib.AsyncExitStack()
    db_engine: AsyncEngine | None = None

    async def _db_phase() -> AsyncEngine | None:
        """Open DB engine only when DB queries are required."""
        try:
            t1 = time.monotonic()
            engine = await db_stack.enter_async_context(db.db_engine(state))
            _console.log(f"[dim]  DB engine ready (SSH tunnel): {time.monotonic() - t1:.1f}s[/dim]")
            return engine
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    # --- Phase 2: DB queries using shared engine ---
    recon = ReconciliationResult()
    service_extra_info: dict[tuple[str, str], DynamicServiceExtraInfo] = {}
    services = collect_services(dynamic_autoscaled_instances)
    try:
        if computational_clusters or services:
            db_engine = await _db_phase()
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
        dynamic_to_render = dynamic_autoscaled_instances
        hidden_warm_count = 0
        hidden_hot_count = 0
        if not show_buffers:
            dynamic_to_render = [inst for inst in dynamic_autoscaled_instances if inst.running_services]
            hidden_dynamic_instances = [inst for inst in dynamic_autoscaled_instances if not inst.running_services]
            hidden_warm_count = sum(1 for inst in hidden_dynamic_instances if inst.is_warm_buffer)
            # untagged idle instances are potential/actual hot-buffer candidates, so count them as hot-buffer too
            hidden_hot_count = len(hidden_dynamic_instances) - hidden_warm_count

        computational_to_render = computational_clusters
        hidden_computational_count = 0
        if not show_buffers:
            computational_to_render = [c for c in computational_clusters if not c.primary.is_warm_buffer]
            hidden_computational_count = len(computational_clusters) - len(computational_to_render)

        if state.ec2_resource_autoscaling:
            await rendering.print_dynamic_instances(
                dynamic_to_render,
                state.environment,
                state.ec2_resource_autoscaling.meta.client.meta.region_name,
                output=output,
                service_extra_info=service_extra_info,
                pricing_profile=use_profile,
            )
            hidden_dynamic_parts = [
                f"{count} {label}"
                for count, label in (
                    (hidden_warm_count, "warm buffer"),
                    (hidden_hot_count, "hot-buffer"),
                )
                if count
            ]
            if hidden_dynamic_parts:
                rich.print(
                    f"[dim]  {', '.join(hidden_dynamic_parts)} dynamic instance(s) hidden "
                    "— use --show-buffers to display them[/dim]"
                )
        if state.ec2_resource_clusters_keeper:
            await rendering.print_computational_clusters(
                computational_to_render,
                state.environment,
                state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
                output=output,
                cluster_task_rows={
                    (c.primary.user_id, c.primary.wallet_id): rows for c, rows in recon.cluster_task_rows
                },
                cluster_extra_info=recon.cluster_extra_info,
                compact=True,
                pricing_profile=use_profile,
            )
            if hidden_computational_count:
                rich.print(
                    f"[dim]  {hidden_computational_count} warm buffer computational cluster(s) hidden "
                    "— use --show-buffers to display them[/dim]"
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
    show_buffers: Annotated[
        bool, typer.Option(help="also show warm/hot buffer machines individually, instead of just a count")
    ] = False,
    use_profile: Annotated[
        str | None,
        typer.Option(
            help="AWS profile (e.g. from ~/.aws/credentials) to use for AWS cost lookups "
            "(pricing:GetProducts, ec2:DescribeVolumes), in case the deploy-config credentials lack access"
        ),
    ] = None,
) -> None:
    """Compact overview of all dynamic and computational instances.

    Shows dynamic instances with their services and computational clusters
    with task-level details but without per-worker machine info.
    Warm/hot buffer machines are hidden by default (shown as a count only);
    use --show-buffers to display them individually.
    """

    if not asyncio.run(
        _run(
            state,
            user_id or None,
            wallet_id or None,
            output_json=as_json,
            output=output,
            show_buffers=show_buffers,
            use_profile=use_profile,
        )
    ):
        raise typer.Exit(1)

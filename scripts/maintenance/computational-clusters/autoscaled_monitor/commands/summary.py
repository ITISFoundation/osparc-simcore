"""Top-level ``summary`` command — compact overview of both dynamic and computational."""

import asyncio
from pathlib import Path
from typing import Annotated

import arrow
import rich
import typer

from .. import analysis, ec2, rendering
from .._state import state
from ..models import AppState, ComputationalCluster, DynamicInstance
from ..reconciliation import ReconciliationResult, reconcile_computational_clusters


async def _run(
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
    *,
    output_json: bool,
    output: Path | None,
) -> bool:
    dynamic_autoscaled_instances: list[DynamicInstance] = []
    computational_clusters: list[ComputationalCluster] = []

    if state.ec2_resource_autoscaling:
        dynamic_instances = await ec2.list_dynamic_instances_from_ec2(
            state,
            filter_by_user_id=user_id,
            filter_by_wallet_id=wallet_id,
            filter_by_instance_id=None,
        )
        dynamic_autoscaled_instances = await analysis.parse_dynamic_instances(
            state, dynamic_instances, state.ssh_key_path, user_id, wallet_id
        )

    if state.ec2_resource_clusters_keeper:
        computational_instances = await ec2.list_computational_instances_from_ec2(state, user_id, wallet_id)
        computational_clusters = await analysis.parse_computational_clusters(
            state, computational_instances, state.ssh_key_path, user_id, wallet_id
        )

    recon = ReconciliationResult()
    if computational_clusters:
        recon = await reconcile_computational_clusters(state, computational_clusters)

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

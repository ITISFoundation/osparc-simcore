"""``computational summary`` — verbose computational-cluster details with worker info."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from ... import analysis, ec2, rendering
from ..._state import state
from ...models import AppState, ComputationalCluster
from ...reconciliation import ReconciliationResult, reconcile_computational_clusters


async def _run(
    state: AppState,
    user_id: int | None,
    wallet_id: int | None,
    *,
    output_json: bool,
    output: Path | None,
) -> bool:
    assert state.ec2_resource_clusters_keeper

    computational_instances = await ec2.list_computational_instances_from_ec2(state, user_id, wallet_id)
    computational_clusters: list[ComputationalCluster] = await analysis.parse_computational_clusters(
        state, computational_instances, state.ssh_key_path, user_id, wallet_id
    )

    recon = ReconciliationResult()
    if computational_clusters:
        recon = await reconcile_computational_clusters(state, computational_clusters)

    if output_json:
        rendering.print_summary_as_json(
            [],
            computational_clusters,
            output=output,
            cluster_task_rows=recon.cluster_task_rows,
        )
    else:
        rendering.print_computational_clusters(
            computational_clusters,
            state.environment,
            state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
            output=output,
            cluster_task_rows={(c.primary.user_id, c.primary.wallet_id): rows for c, rows in recon.cluster_task_rows},
            cluster_extra_info=recon.cluster_extra_info,
        )

    task_issues_found = any(row.issues for _, task_rows in recon.cluster_task_rows for row in task_rows)

    return not task_issues_found


def summary(
    *,
    user_id: Annotated[int, typer.Option(help="filters by the user ID")] = 0,
    wallet_id: Annotated[int, typer.Option(help="filters by the wallet ID")] = 0,
    as_json: Annotated[bool, typer.Option(help="outputs as json")] = False,
    output: Annotated[Path | None, typer.Option(help="outputs to a file")] = None,
) -> None:
    """Verbose view of computational clusters with full worker details."""

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

"""``computational terminate`` — trigger cluster termination via heartbeat tag."""

import asyncio
import datetime
import time
from typing import Annotated

import arrow
import rich
import typer
from mypy_boto3_ec2.type_defs import TagTypeDef

from ... import analysis, db, ec2, rendering, ssh
from ..._helpers import load_computational_clusters
from ..._state import state
from ...models import AppState


async def _run(  # noqa: PLR0915
    state: AppState,
    user_id: int,
    wallet_id: int | None,
    *,
    force: bool,
    intervals_to_wait: int,
    skip_wait: bool,
) -> None:
    assert state.ec2_resource_clusters_keeper
    computational_clusters = await load_computational_clusters(state, user_id, wallet_id)
    assert computational_clusters
    assert len(computational_clusters) == 1, "too many clusters found! TIP: fix this code"

    rendering.print_computational_clusters(
        computational_clusters,
        state.environment,
        state.ec2_resource_clusters_keeper.meta.client.meta.region_name,
        output=None,
        cluster_task_rows=None,
        cluster_extra_info=None,
        compact=False,
    )
    if (force is True) or typer.confirm("Are you sure you want to trigger termination of that cluster?"):
        the_cluster = computational_clusters[0]

        # ===== PHASE 1: Graceful termination - cancel jobs and set stale heartbeat =====
        rich.print("\n[bold]Phase 1: Graceful termination[/bold]")
        rich.print("Canceling running jobs...")

        async with db.db_engine(state) as engine:
            task_to_dask_job = await analysis.resolve_cluster_tasks(engine, the_cluster)
            assert state.ssh_key_path  # nosec
            async with ssh.computational_bastion_connection(state) as bastion_conn:
                await analysis.cancel_all_jobs(
                    state,
                    the_cluster,
                    task_to_dask_job=task_to_dask_job,
                    abort_in_db=force,
                    engine=engine,
                    bastion_conn=bastion_conn,
                )

        rich.print("[green]✓ Jobs cancelled[/green]")

        # Set heartbeat tag to trigger clusters-keeper termination
        new_heartbeat_tag: TagTypeDef = {
            "Key": "io.simcore.clusters-keeper.last_heartbeat",
            "Value": f"{arrow.utcnow().datetime - datetime.timedelta(hours=1)}",
        }
        the_cluster.primary.ec2_instance.create_tags(Tags=[new_heartbeat_tag])
        rich.print("[green]✓ Stale heartbeat tag set[/green]")

        original_primary_id = the_cluster.primary.ec2_instance.id
        original_worker_ids = {w.ec2_instance.id for w in the_cluster.workers}

        if skip_wait:
            # Skip Phase 2 and go directly to fallback
            rich.print("\n[yellow]Skipping wait phase, proceeding to direct EC2 termination...[/yellow]")
            assert state.ec2_resource_clusters_keeper
            await ec2.terminate_cluster_instances_forcefully(
                state.ec2_resource_clusters_keeper,
                original_primary_id,
                original_worker_ids,
            )
            rich.print("[bold green]✓ Cluster termination complete (direct EC2 termination)[/bold green]")
        else:
            # ===== PHASE 2: Wait for clusters-keeper to remove the cluster =====
            rich.print("\n[bold]Phase 2: Waiting for clusters-keeper termination[/bold]")
            task_interval = ec2.get_clusters_keeper_task_interval(state)
            wait_budget_seconds = int(task_interval.total_seconds() * intervals_to_wait)
            rich.print(f"Waiting up to {wait_budget_seconds} seconds for clusters-keeper to terminate the cluster...")

            start_time = time.time()
            poll_interval = 5  # seconds between checks
            cluster_removed = False

            while time.time() - start_time < wait_budget_seconds:
                cluster_still_up = await ec2.cluster_is_running(
                    state,
                    user_id,
                    wallet_id,
                    original_primary_id,
                    original_worker_ids,
                )

                if not cluster_still_up:
                    cluster_removed = True
                    break

                elapsed = int(time.time() - start_time)
                remaining = wait_budget_seconds - elapsed
                rich.print(f"  Cluster still present... {remaining}s remaining", end="\r")
                await asyncio.sleep(poll_interval)

            if cluster_removed:
                rich.print("\n[green]✓ Cluster removed by clusters-keeper (termination successful)[/green]")
            else:
                # ===== PHASE 3: Fallback to direct EC2 termination =====
                rich.print(f"\n[yellow]Graceful termination window ({wait_budget_seconds}s) expired.[/yellow]")
                assert state.ec2_resource_clusters_keeper
                await ec2.terminate_cluster_instances_forcefully(
                    state.ec2_resource_clusters_keeper,
                    original_primary_id,
                    original_worker_ids,
                )
                rich.print("[bold green]✓ Cluster termination complete (direct EC2 fallback)[/bold green]")
    else:
        rich.print("not deleting anything")


def terminate(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[int | None, typer.Option(help="the wallet ID")] = None,
    *,
    force: Annotated[bool, typer.Option(help="will not ask for confirmation (VERY RISKY!)")] = False,
    intervals_to_wait: Annotated[
        int, typer.Option(help="number of CLUSTERS_KEEPER_TASK_INTERVAL periods to wait")
    ] = 10,
    skip_wait: Annotated[bool, typer.Option(help="skip wait phase and go directly to EC2 termination")] = False,
) -> None:
    """Trigger termination of a computational cluster.

    The command follows three phases (unless --skip-wait is used):
    1. Cancel all running jobs and set stale heartbeat tag
    2. Wait up to N x CLUSTERS_KEEPER_TASK_INTERVAL for graceful removal
    3. If still present, directly terminate EC2 instances as fallback
    """

    asyncio.run(_run(state, user_id, wallet_id, force=force, intervals_to_wait=intervals_to_wait, skip_wait=skip_wait))

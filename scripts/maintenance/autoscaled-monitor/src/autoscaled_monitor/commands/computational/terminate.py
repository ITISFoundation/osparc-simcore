"""``computational terminate`` — trigger cluster termination via heartbeat tag."""

import asyncio
import datetime
from typing import Annotated

import arrow
import rich
import typer
from mypy_boto3_ec2.type_defs import TagTypeDef

from ... import analysis, db, rendering, ssh
from ..._helpers import load_computational_clusters
from ..._state import state
from ...models import AppState, ComputationalTask, DaskTask


async def _run(
    state: AppState,
    user_id: int,
    wallet_id: int | None,
    *,
    force: bool,
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

        # Extract job_ids from cluster to fetch only relevant tasks
        job_ids = [job_id for job_ids in the_cluster.task_states_to_tasks.values() for job_id in job_ids]

        async with db.db_engine(state) as engine:
            computational_tasks = await db.list_computational_tasks_by_job_ids(engine, job_ids=job_ids)
            job_id_to_dask_state = analysis.get_job_id_to_dask_state_from_cluster(the_cluster)
            task_to_dask_job: list[tuple[ComputationalTask | None, DaskTask | None]] = analysis.get_db_task_to_dask_job(
                computational_tasks, job_id_to_dask_state
            )
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


def terminate(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[int | None, typer.Option(help="the wallet ID")] = None,
    *,
    force: Annotated[bool, typer.Option(help="will not ask for confirmation (VERY RISKY!)")] = False,
) -> None:
    """Trigger termination of a computational cluster.

    Sets the heartbeat tag on the primary machine to 1 hour ago,
    ensuring the clusters-keeper will properly terminate it.
    """

    asyncio.run(_run(state, user_id, wallet_id, force=force))

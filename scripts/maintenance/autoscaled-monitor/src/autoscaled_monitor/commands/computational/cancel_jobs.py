"""``computational cancel-jobs`` — cancel running jobs on a computational cluster."""

import asyncio
from typing import Annotated

import rich
import typer
from pydantic import ValidationError

from ... import analysis, dask, db, rendering, ssh
from ..._helpers import load_computational_clusters
from ..._state import state
from ...models import AppState, ComputationalTask, DaskTask


async def _run(  # noqa: C901, PLR0912
    run_state: AppState,
    user_id: int,
    wallet_id: int | None,
    *,
    abort_in_db: bool,
) -> None:
    # Load cluster first to extract job IDs for targeted lookup
    computational_clusters = await load_computational_clusters(run_state, user_id, wallet_id)

    if not computational_clusters:
        rich.print("[red]no computational cluster found for this user/wallet[/red]")
        raise typer.Exit(1)

    assert len(computational_clusters) == 1, (
        "too many clusters found! TIP: fix this code or something weird is playing out"
    )
    the_cluster = computational_clusters[0]
    rich.print(f"{the_cluster.task_states_to_tasks=}")

    # Extract job_ids from cluster to fetch only relevant tasks
    job_ids = [job_id for job_ids in the_cluster.task_states_to_tasks.values() for job_id in job_ids]

    async with db.db_engine(run_state) as engine:
        # Fetch only the computational tasks that are actually on the cluster
        computational_tasks = await db.list_computational_tasks_by_job_ids(engine, job_ids=job_ids)

        job_id_to_dask_state = await analysis.get_job_id_to_dask_state_from_cluster(the_cluster)
        task_to_dask_job: list[
            tuple[ComputationalTask | None, DaskTask | None]
        ] = await analysis.get_db_task_to_dask_job(computational_tasks, job_id_to_dask_state)

        if not task_to_dask_job:
            rich.print("[red]nothing found![/red]")
            raise typer.Exit

        rendering.print_computational_tasks(user_id, wallet_id, task_to_dask_job)
        rich.print(the_cluster.datasets)

        assert run_state.ssh_key_path  # nosec
        async with ssh.computational_bastion_connection(run_state) as bastion_conn:
            try:
                if response := typer.prompt(
                    "Which dataset to cancel? (all: will cancel everything, 1-5: "
                    "will cancel jobs 1-5, or 4: will cancel job #4)",
                    default="none",
                ):
                    if response == "none":
                        rich.print("[yellow]not cancelling anything[/yellow]")
                    elif response == "all":
                        await analysis.cancel_all_jobs(
                            run_state,
                            the_cluster,
                            task_to_dask_job=task_to_dask_job,
                            abort_in_db=abort_in_db,
                            engine=engine,
                            bastion_conn=bastion_conn,
                        )
                    else:
                        try:
                            indices = response.split("-")
                            if len(indices) == 2:  # noqa: PLR2004
                                start_index, end_index = map(int, indices)
                                selected_indices = range(start_index, end_index + 1)
                            else:
                                selected_indices = [int(indices[0])]

                            for selected_index in selected_indices:
                                comp_task, dask_task = task_to_dask_job[selected_index]
                                if dask_task is not None and dask_task.state != "unknown":
                                    await dask.trigger_job_cancellation_in_scheduler(
                                        run_state, the_cluster, dask_task.job_id, bastion_conn
                                    )
                                    if comp_task is None:
                                        await dask.remove_job_from_scheduler(
                                            run_state, the_cluster, dask_task.job_id, bastion_conn
                                        )

                                if comp_task is not None and abort_in_db:
                                    await db.abort_job_in_db(engine, comp_task.project_id, comp_task.node_id)
                            rich.print(f"Cancelled selected tasks: {response}")

                        except ValidationError:
                            rich.print("[yellow]wrong index format, not cancelling anything[/yellow]")
                        except IndexError:
                            rich.print("[yellow]index out of range, not cancelling anything[/yellow]")
            except ValidationError:
                rich.print("[yellow]wrong input, not cancelling anything[/yellow]")


def cancel_jobs(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[int | None, typer.Option(help="the wallet ID")] = None,
    *,
    abort_in_db: Annotated[
        bool,
        typer.Option(
            help="will also force the job to abort in the database "
            "(use only if job is in WAITING FOR CLUSTER/WAITING FOR RESOURCE)"
        ),
    ] = False,
) -> None:
    """Cancel jobs from the cluster.

    The director-v2 should receive the cancellation and abort the concerned
    pipelines in the next 15 seconds.
    """

    asyncio.run(_run(state, user_id, wallet_id, abort_in_db=abort_in_db))

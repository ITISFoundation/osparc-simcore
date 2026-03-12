"""``dynamic summary`` — verbose dynamic-instance details."""

import asyncio
from pathlib import Path
from typing import Annotated

import arrow
import rich
import typer
from rich.console import Console

from ... import db, rendering
from ..._helpers import collect_services, load_dynamic_instances
from ..._state import state
from ...models import AppState, DynamicInstance, DynamicServiceExtraInfo


async def _run(
    state: AppState,
    user_id: int | None,
    *,
    output_json: bool,
    output: Path | None,
) -> bool:
    assert state.ec2_resource_autoscaling

    dynamic_autoscaled_instances: list[DynamicInstance] = await load_dynamic_instances(
        state, user_id, wallet_id=None, instance_id=None
    )

    # Resolve user emails and wallet info from DB
    service_extra_info: dict[tuple[str, str], DynamicServiceExtraInfo] = {}
    services = collect_services(dynamic_autoscaled_instances)
    if services:
        try:
            with Console().status("[bold]Querying database for user/wallet info...[/bold]"):
                async with db.db_engine(state) as engine:
                    service_extra_info = await db.get_dynamic_service_extra_info(engine, services)
        except Exception:  # pylint: disable=broad-exception-caught
            rich.print("[yellow]Warning: could not query DB for user/wallet info.[/yellow]")

    if output_json:
        rendering.print_summary_as_json(
            dynamic_autoscaled_instances,
            [],
            output=output,
            cluster_task_rows=None,
        )
    else:
        rendering.print_dynamic_instances(
            dynamic_autoscaled_instances,
            state.environment,
            state.ec2_resource_autoscaling.meta.client.meta.region_name,
            output=output,
            service_extra_info=service_extra_info,
        )

    time_threshold = arrow.utcnow().shift(minutes=-30).datetime
    return not any(
        service.needs_manual_intervention and service.created_at < time_threshold
        for instance in dynamic_autoscaled_instances
        for service in instance.running_services
    )


def summary(
    *,
    user_id: Annotated[int, typer.Option(help="filters by the user ID")] = 0,
    as_json: Annotated[bool, typer.Option(help="outputs as json")] = False,
    output: Annotated[Path | None, typer.Option(help="outputs to a file")] = None,
) -> None:
    """Verbose view of dynamic autoscaled instances and their running services."""

    if not asyncio.run(
        _run(
            state,
            user_id or None,
            output_json=as_json,
            output=output,
        )
    ):
        raise typer.Exit(1)
